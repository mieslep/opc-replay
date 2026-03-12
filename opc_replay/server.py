#!/usr/bin/env python3
"""
OPC UA Replay Server

Replays timestamped OPC UA tag data from CSV or Parquet files at configurable speeds.
Includes HTTP REST API for real-time tag value injection.

Features:
- Import NodeSet2 XML files or auto-generate from data
- Replay at real-time speed or accelerated (e.g., 10x faster)
- Real-time tag injection via HTTP API (default port 8080)
- Loop mode for continuous replay
- Automatic namespace remapping

Usage:
  opc-replay --data mydata.csv --ts-col TS --auto-nodeset
  opc-replay --nodeset nodeset.xml --data mydata.parquet --ts-col TIMESTAMP --speed 10 --loop

For detailed options, run: opc-replay --help
"""

import argparse
import time
import re
import tempfile
import os
import json
import threading
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

import pandas as pd
from opcua import ua, Server

# Map DATATYPE strings to python-opcua VariantTypes
VARIANT_TYPE = {
    "Boolean": ua.VariantType.Boolean,
    "SByte": ua.VariantType.SByte,
    "Byte": ua.VariantType.Byte,
    "Int16": ua.VariantType.Int16,
    "UInt16": ua.VariantType.UInt16,
    "Int32": ua.VariantType.Int32,
    "UInt32": ua.VariantType.UInt32,
    "Int64": ua.VariantType.Int64,
    "UInt64": ua.VariantType.UInt64,
    "Float": ua.VariantType.Float,
    "Double": ua.VariantType.Double,
    "String": ua.VariantType.String,
    "DateTime": ua.VariantType.DateTime,
}

UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
NS = {"ua": UA_NS}


def is_canonical_nodeid(s: str) -> bool:
    """
    Accept common canonical NodeId string forms:
      ns=2;s=Some.String.Id
      ns=0;i=85
      ns=1;g=...
      ns=2;b=...
    """
    s = (s or "").strip()
    return bool(re.match(r"^ns=\d+;[isgb]=.+$", s))


def build_namespace_map(server, nodeset_path: str) -> dict[int, int]:
    """
    Build a mapping from namespace indices in the nodeset XML to actual server indices.
    Returns dict {xml_ns_idx: server_ns_idx}
    """
    # Parse the nodeset XML to get namespace URIs and their declared indices
    tree = ET.parse(nodeset_path)
    root = tree.getroot()
    
    xml_namespaces = {}
    ns_uris_elem = root.find(".//ua:NamespaceUris", NS)
    if ns_uris_elem is not None:
        for idx, uri_elem in enumerate(ns_uris_elem.findall("ua:Uri", NS), start=1):
            uri = uri_elem.text
            if uri:
                xml_namespaces[idx] = uri
    
    # Get actual namespace array from server
    server_namespaces = server.get_namespace_array()
    
    # Build mapping
    ns_map = {0: 0}  # ns=0 is always the same
    for xml_idx, uri in xml_namespaces.items():
        try:
            server_idx = server_namespaces.index(uri)
            ns_map[xml_idx] = server_idx
        except ValueError:
            # URI not found in server namespaces, keep original
            ns_map[xml_idx] = xml_idx
    
    # Add identity mappings for indices that already match
    for i in range(len(server_namespaces)):
        if i not in ns_map:
            ns_map[i] = i
    
    return ns_map


def remap_nodeid(nodeid: str, ns_map: dict[int, int]) -> str:
    """
    Remap a NodeId from CSV namespace index to server namespace index.
    E.g., 'ns=2;s=Tag.Name' -> 'ns=3;s=Tag.Name' if ns_map[2]=3
    """
    match = re.match(r"^ns=(\d+);([isgb]=.+)$", nodeid)
    if not match:
        return nodeid
    
    old_ns = int(match.group(1))
    identifier = match.group(2)
    
    new_ns = ns_map.get(old_ns, old_ns)
    return f"ns={new_ns};{identifier}"


def cast_value(raw, dtype: str):
    if raw is None:
        return None
    if pd.isna(raw):
        return None
    dtype = (dtype or "String").strip()
    if dtype in ("Float", "Double"):
        return float(raw)
    if dtype in ("Int16", "UInt16", "Int32", "UInt32", "Int64", "UInt64", "SByte", "Byte"):
        return int(float(raw))
    if dtype == "Boolean":
        s = str(raw).strip().lower()
        return s in ("1", "true", "t", "yes", "y")
    if dtype == "DateTime":
        return pd.to_datetime(raw, errors="coerce").to_pydatetime()
    return str(raw)


# ---------------------------------------------------------------------------
# Tag-injection override store (thread-safe)
# ---------------------------------------------------------------------------

class OverrideStore:
    """
    Thread-safe store of tag overrides.
    Each override is:
        tagname        – canonical OPC UA NodeId string (ns=2;s=...)
        value          – raw value (will be cast using cast_value at write time)
        activate_at    – epoch when the override becomes active
        expire_at      – epoch when the override expires
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._overrides: dict[str, list[dict]] = {}  # tagname -> [override, ...]

    def add(self, tagname: str, value, time_offset_s: float, duration_s: float, dtype: str | None = None):
        now = time.time()
        entry = {
            "tagname": tagname,
            "value": value,
            "dtype": dtype,
            "activate_at": now + time_offset_s,
            "expire_at": now + time_offset_s + duration_s,
            "created": now,
        }
        with self._lock:
            self._overrides.setdefault(tagname, []).append(entry)
        return entry

    def get_active(self, tagname: str):
        """Return the active override value for *tagname*, or None."""
        now = time.time()
        with self._lock:
            entries = self._overrides.get(tagname)
            if not entries:
                return None
            alive = [e for e in entries if e["expire_at"] > now]
            if len(alive) != len(entries):
                if alive:
                    self._overrides[tagname] = alive
                else:
                    del self._overrides[tagname]
                    return None
            for e in reversed(alive):
                if e["activate_at"] <= now:
                    return e["value"]
        return None

    def is_overridden(self, tagname: str, remapped: str) -> bool:
        """Return True if tagname or remapped has an active override.
        Acquires the lock exactly once for both names.
        """
        if not self._overrides:  # fast-path: empty store (GIL-safe dict bool check)
            return False
        now = time.time()
        # Deduplicate: when there is no namespace remapping, both names are identical
        names = (tagname,) if tagname == remapped else (tagname, remapped)
        with self._lock:
            for tag in names:
                entries = self._overrides.get(tag)
                if not entries:
                    continue
                alive = [e for e in entries if e["expire_at"] > now]
                if len(alive) != len(entries):
                    if alive:
                        self._overrides[tag] = alive
                    else:
                        del self._overrides[tag]
                        continue
                for e in reversed(alive):
                    if e["activate_at"] <= now:
                        return True
        return False

    def get_all_active(self) -> dict[str, dict]:
        """Return {tagname: entry} for every currently active override.
        Used by the background applier thread to push values without waiting
        for the replay loop to visit each tag's next CSV row.
        """
        now = time.time()
        result: dict[str, dict] = {}
        with self._lock:
            dead_keys: list[str] = []
            for tag, entries in self._overrides.items():
                alive = [e for e in entries if e["expire_at"] > now]
                if len(alive) != len(entries):
                    if alive:
                        self._overrides[tag] = alive  # replace value — safe during iteration
                    else:
                        dead_keys.append(tag)  # key deletion deferred until after loop
                        continue
                for e in reversed(alive):
                    if e["activate_at"] <= now:
                        result[tag] = e
                        break
            for k in dead_keys:
                del self._overrides[k]
        return result

    def list_all(self):
        now = time.time()
        with self._lock:
            result = []
            for tag, entries in self._overrides.items():
                for e in entries:
                    if e["expire_at"] <= now:
                        continue  # skip already-expired entries
                    result.append({
                        "tagname": e["tagname"],
                        "value": e["value"],
                        "remaining_s": round(e["expire_at"] - now, 2),
                        "active": e["activate_at"] <= now,
                        "pending": now < e["activate_at"],
                    })
            return result

    def clear(self):
        with self._lock:
            self._overrides.clear()


# ---------------------------------------------------------------------------
# HTTP API for tag injection
# ---------------------------------------------------------------------------

class InjectionHandler(BaseHTTPRequestHandler):
    """
    Endpoints:
        POST /inject   – add one or more overrides (JSON body)
        GET  /inject   – list all active / pending overrides
        DELETE /inject – clear all overrides
    """

    override_store: OverrideStore | None = None  # set before server starts

    def log_message(self, format, *args):
        # Prefix with [API] for clarity in combined log
        print(f"[API] {self.address_string()} - {format % args}")

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        assert self.override_store is not None
        if self.path.rstrip("/") == "/inject":
            overrides = self.override_store.list_all()
            self._send_json({"overrides": overrides})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        assert self.override_store is not None
        if self.path.rstrip("/") == "/inject":
            self.override_store.clear()
            self._send_json({"status": "cleared"})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        assert self.override_store is not None
        if self.path.rstrip("/") != "/inject":
            self._send_json({"error": "Not found"}, 404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json({"error": "Empty body"}, 400)
            return

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            self._send_json({"error": f"Invalid JSON: {e}"}, 400)
            return

        # Accept either a single object or {"injections": [...]}
        if isinstance(payload, dict) and "injections" in payload:
            items = payload["injections"]
        elif isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = [payload]
        else:
            self._send_json({"error": "Expected JSON object or array"}, 400)
            return

        results = []
        for item in items:
            tagname = item.get("tagname")
            value = item.get("value")
            time_offset_s = float(item.get("time_offset_s", 0))
            duration_s = float(item.get("duration_s", 60))
            dtype = item.get("dtype")  # optional OPC UA type hint, e.g. "Float"
            if not tagname:
                results.append({"error": "Missing tagname"})
                continue
            entry = self.override_store.add(tagname, value, time_offset_s, duration_s, dtype=dtype)
            results.append({
                "tagname": tagname,
                "value": value,
                "activate_at": datetime.fromtimestamp(entry["activate_at"], tz=timezone.utc).isoformat(),
                "expire_at": datetime.fromtimestamp(entry["expire_at"], tz=timezone.utc).isoformat(),
                "status": "scheduled",
            })

        self._send_json({"results": results})


def _infer_variant(value, dtype: str | None = None):
    """Build a ua.Variant from an injected value.
    Uses the OPC UA dtype name if provided (e.g. 'Float', 'Int32'),
    otherwise infers from the Python type of *value*.
    """
    if dtype and dtype in VARIANT_TYPE:
        return ua.Variant(cast_value(value, dtype), VARIANT_TYPE[dtype])
    if isinstance(value, bool):
        return ua.Variant(value, ua.VariantType.Boolean)
    if isinstance(value, int):
        return ua.Variant(value, ua.VariantType.Int64)
    if isinstance(value, float):
        return ua.Variant(value, ua.VariantType.Double)
    return ua.Variant(str(value), ua.VariantType.String)


def run_override_applier(
    store: OverrideStore,
    server,
    ns_map: dict,
    quiet: bool,
    stop_event: threading.Event,
    poll_interval_s: float = 0.1,
):
    """
    Background thread: writes all currently-active overrides to OPC UA nodes
    every *poll_interval_s* seconds (default 100 ms).

    This eliminates the latency caused by waiting for the replay loop to visit
    the next CSV/parquet row for a given tag.  The replay loop still suppresses
    writing the CSV value when an override is active, avoiding value flicker.
    """
    node_cache: dict = {}
    while not stop_event.is_set():
        time.sleep(poll_interval_s)
        active = store.get_all_active()
        for tagname, entry in active.items():
            try:
                remapped = remap_nodeid(tagname, ns_map)
                node = node_cache.get(remapped)
                if node is None:
                    node = server.get_node(remapped)
                    node_cache[remapped] = node
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                dv = ua.DataValue(_infer_variant(entry["value"], entry.get("dtype")))
                dv.SourceTimestamp = now
                dv.ServerTimestamp = now
                node.set_value(dv)
            except Exception as ex:
                if not quiet:
                    print(f"[OVERRIDE applier error] {tagname}: {ex}")


def start_injection_api(store: OverrideStore, port: int, quiet: bool = False):
    """Launch the injection HTTP API on a daemon thread."""
    InjectionHandler.override_store = store
    httpd = HTTPServer(("0.0.0.0", port), InjectionHandler)
    httpd.timeout = 0.5
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    if not quiet:
        print(f"[API] Injection API listening on http://0.0.0.0:{port}/inject")
    return httpd


def load_and_prepare_data(data_path: str, ts_col: str, offset: float = 0.0, max_rows: int | None = None):
    """
    Load data from CSV or Parquet file and prepare for replay.
    Automatically detects file type and normalizes column names.
    
    Expected columns (flexible naming):
    - TAGNAME or TAG_NAME: Node identifier
    - TAGVALUE or VALUE: Tag value
    - DATATYPE: OPC UA data type
    - Timestamp column specified by ts_col
    
    Process order:
    1. Load data file
    2. Sort by timestamp
    3. Apply offset (skip first N seconds from start)
    4. Apply max_rows limit (take first N rows after offset)
    
    Returns dataframe with normalized column names: TAGNAME, TAGVALUE, DATATYPE, and timestamp column.
    """
    # Detect file type and load
    if data_path.lower().endswith('.parquet'):
        df = pd.read_parquet(data_path)
    elif data_path.lower().endswith('.csv'):
        df = pd.read_csv(data_path, low_memory=False)
    else:
        raise ValueError(f"Unsupported file type. Must be .csv or .parquet: {data_path}")
    
    # Normalize column names - support both formats
    column_mapping = {}
    if 'TAG_NAME' in df.columns and 'TAGNAME' not in df.columns:
        column_mapping['TAG_NAME'] = 'TAGNAME'
    if 'VALUE' in df.columns and 'TAGVALUE' not in df.columns:
        column_mapping['VALUE'] = 'TAGVALUE'
    
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    # Verify required columns exist
    required = {"TAGNAME", "TAGVALUE", "DATATYPE"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Data file is missing required columns: {sorted(missing)}. Available: {list(df.columns)}")

    if ts_col not in df.columns:
        raise ValueError(f"Data file missing timestamp column '{ts_col}'. Available: {list(df.columns)}")

    # Parse and sort by timestamp - CRITICAL for proper replay order
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    df = df.dropna(subset=[ts_col]).sort_values(ts_col)
    
    # Apply offset BEFORE max_rows
    if offset > 0:
        first_ts = df[ts_col].iloc[0]
        offset_ts = first_ts + pd.Timedelta(seconds=offset)
        df = df[df[ts_col] >= offset_ts].copy()
        if df.empty:
            raise ValueError(f"Offset of {offset}s exceeds data duration. No rows remain.")
    
    # Apply max_rows limit AFTER offset
    if max_rows is not None:
        df = df.head(max_rows)

    # Normalize TAGNAME to string
    df["TAGNAME"] = df["TAGNAME"].astype(str).str.strip()

    return df


def load_and_prepare_csv(csv_path: str, ts_col: str, max_rows: int | None):
    """Legacy function - redirects to load_and_prepare_data for backwards compatibility"""
    return load_and_prepare_data(csv_path, ts_col, offset=0.0, max_rows=max_rows)


def drop_bad_nodeset_nodes(nodeset_in: str) -> tuple[str, int, int]:
    """
    Remove any UA node element that has a non-canonical NodeId (e.g. PET001CalcAlarm).
    Also remove <Reference> entries whose target is non-canonical or references a removed NodeId token.

    Returns: (temp_xml_path, dropped_nodes_count, dropped_refs_count)
    """
    tree = ET.parse(nodeset_in)
    root = tree.getroot()

    # Collect all UA node elements that carry NodeId attributes
    # This catches UAObject, UAVariable, UAObjectType, etc.
    to_remove = []
    removed_ids = set()

    for elem in root.iter():
        nid = elem.attrib.get("NodeId")
        if nid is not None and not is_canonical_nodeid(nid):
            to_remove.append(elem)
            removed_ids.add(nid.strip())

    dropped_nodes = 0
    if to_remove:
        # Need parent pointers; ElementTree doesn't provide them, so build a map
        parent_map = {c: p for p in root.iter() for c in p}
        for elem in to_remove:
            parent = parent_map.get(elem)
            if parent is not None:
                parent.remove(elem)
                dropped_nodes += 1

    # Drop bad references
    dropped_refs = 0
    for refs in root.findall(".//ua:References", NS):
        # iterate over a copy to safely remove
        for ref in list(refs.findall("ua:Reference", NS)):
            txt = (ref.text or "").strip()
            if (not txt) or (txt in removed_ids) or (not is_canonical_nodeid(txt)):
                refs.remove(ref)
                dropped_refs += 1

    fd, tmp_path = tempfile.mkstemp(prefix="nodeset_dropbad_", suffix=".xml")
    os.close(fd)
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    return tmp_path, dropped_nodes, dropped_refs


def main():
    ap = argparse.ArgumentParser(description="OPC UA replay server supporting CSV and Parquet data files")
    ap.add_argument("--endpoint", default="opc.tcp://0.0.0.0:4840/", help="OPC UA endpoint URL")
    ap.add_argument("--server-name", default="ReplayServer", help="Server name")
    ap.add_argument("--nodeset", default=None, help="NodeSet2 XML file (optional if --auto-nodeset is used)")
    ap.add_argument("--data", required=True, help="Data file (.csv or .parquet) with TAGNAME/TAG_NAME, TAGVALUE/VALUE, DATATYPE columns and timestamp column")
    ap.add_argument("--csv", help="(Deprecated: use --data) CSV with TAGNAME,TAGVALUE,DATATYPE and timestamp column")
    ap.add_argument("--ts-col", default="TS", help="Timestamp column name (default: TS, common: TIMESTAMP)")
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speedup (1=real-time, 10=10x faster)")
    ap.add_argument("--offset", type=float, default=0.0, help="Skip ahead by N seconds from the first timestamp (e.g., 3600 skips first hour)")
    ap.add_argument("--loop", action="store_true", help="Loop playback forever")
    ap.add_argument("--max-rows", type=int, default=None, help="Limit number of rows for quick testing")
    ap.add_argument("--warmup", type=float, default=0.0, help="Seconds to wait before replay begins")
    ap.add_argument("--quiet", action="store_true", help="Reduce per-update logging")

    # NodeSet auto-generation:
    ap.add_argument("--auto-nodeset", action="store_true",
                    help="Auto-generate NodeSet from data file (extracts unique TAGNAME+DATATYPE). Saves generated NodeSet for reuse.")
    ap.add_argument("--root-name", default=None,
                    help="Root object name for auto-generated NodeSet (default: derived from data filename)")
    ap.add_argument("--namespace-uri", default=None,
                    help="Namespace URI for auto-generated NodeSet (default: urn:<root-name>:tags)")

    # New "skip, don't fix" behaviors:
    ap.add_argument("--drop-bad-nodeset-nodeids", action="store_true",
                    help="Drop nodes from the imported NodeSet that have non-canonical NodeIds (prevents import crash).")
    ap.add_argument("--skip-bad-csv", action="store_true",
                    help="Skip/log data rows with non-canonical TAGNAMEs, or writes that fail (BadNodeIdUnknown, etc.).")
    
    # Namespace mapping control:
    ap.add_argument("--allow-ns-mismatch", action="store_true",
                    help="Allow namespace index mismatch between data file and server. Automatically maps data namespace indices to server indices. Use this when nodeset was generated with different --namespace-index than data file.")

    # Injection API:
    ap.add_argument("--api-port", type=int, default=8080,
                    help="HTTP port for the tag-injection REST API (default: 8080, 0 to disable)")

    args = ap.parse_args()
    
    # Support legacy --csv argument
    data_file = args.data if args.data else args.csv
    if not data_file:
        ap.error("Either --data or --csv is required")

    # Check NodeSet requirement
    if not args.nodeset and not args.auto_nodeset:
        ap.error("Either --nodeset or --auto-nodeset is required")

    if args.speed <= 0:
        raise ValueError("--speed must be > 0")

    # Load and prepare data (load -> sort -> offset -> max_rows)
    df = load_and_prepare_data(data_file, args.ts_col, offset=args.offset, max_rows=args.max_rows)
    if df.empty:
        raise ValueError("No valid rows found after parsing timestamps.")
    
    if not args.quiet:
        print(f"[Data] Loaded {len(df)} rows from {data_file}")
        if args.offset > 0:
            print(f"[Data] Offset: Skipped first {args.offset}s")
        print(f"[Data] Time range: {df[args.ts_col].min()} to {df[args.ts_col].max()}")
        duration = (df[args.ts_col].max() - df[args.ts_col].min()).total_seconds()
        print(f"[Data] Duration: {duration:.1f}s ({duration/60:.1f} min)")
        print(f"[Data] Unique tags: {df['TAGNAME'].nunique()}")

    # Auto-generate NodeSet if requested
    if args.auto_nodeset:
        # Import here to avoid circular dependency
        from .csv_to_nodeset import generate_nodeset_from_dataframe
        
        # Determine root name
        if args.root_name:
            root_name = args.root_name
        else:
            # Derive from filename
            import os
            basename = os.path.basename(data_file)
            root_name = os.path.splitext(basename)[0].replace("-", "_").replace(" ", "_")
        
        # Generate output path
        data_dir = os.path.dirname(os.path.abspath(data_file))
        auto_nodeset_path = os.path.join(data_dir, f"{root_name}_auto_nodeset.xml")
        
        if not args.quiet:
            print(f"[Auto-NodeSet] Generating from {len(df['TAGNAME'].unique())} unique tags...")
        
        # Extract unique tag definitions from data
        tag_defs = df[['TAGNAME', 'DATATYPE', 'TAGVALUE']].drop_duplicates(subset=['TAGNAME'])
        
        # Generate NodeSet XML
        xml_content = generate_nodeset_from_dataframe(
            df=tag_defs,
            root_name=root_name,
            namespace_index=1,  # Always generate as ns=1 (becomes ns=2 on server)
            namespace_uri=args.namespace_uri,
            split_regex=r"\.",
            no_folders=False,
        )
        
        # Save to file
        with open(auto_nodeset_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        
        if not args.quiet:
            print(f"[Auto-NodeSet] ✓ Generated: {auto_nodeset_path}")
            print(f"[Auto-NodeSet] Tip: Reuse with --nodeset {auto_nodeset_path} for faster startup")
        
        args.nodeset = auto_nodeset_path

    server = Server()
    server.set_endpoint(args.endpoint)
    server.set_server_name(args.server_name)
    
    nodeset_path = args.nodeset
    tmp_nodeset = None

    if args.drop_bad_nodeset_nodeids:
        tmp_nodeset, dropped_nodes, dropped_refs = drop_bad_nodeset_nodes(args.nodeset)
        nodeset_path = tmp_nodeset
        if not args.quiet:
            print(f"[NodeSet] Dropped {dropped_nodes} nodes with non-canonical NodeIds; dropped {dropped_refs} bad references")

    # Import NodeSet
    server.import_xml(nodeset_path)

    server.start()
    
    # Build namespace mapping and check for mismatches
    ns_map = build_namespace_map(server, nodeset_path)
    ns_array = server.get_namespace_array()
    
    if not args.quiet:
        print(f"[Server namespaces]")
        for i, ns in enumerate(ns_array):
            print(f"  ns={i}: {ns}")
    
    # Check CSV for namespace indices and detect mismatches
    df_sample = df.head(100)  # Check first 100 rows for CSV namespace indices
    csv_ns_indices = set()
    for tagname in df_sample["TAGNAME"]:
        match = re.match(r"^ns=(\d+);", str(tagname))
        if match:
            csv_ns_indices.add(int(match.group(1)))
    
    # Check if CSV namespace indices map correctly
    # We only care about mismatches for namespaces actually used in the CSV
    needs_mapping = False
    mismatched_indices = []
    for csv_idx in csv_ns_indices:
        server_idx = ns_map[csv_idx] if csv_idx in ns_map else csv_idx
        # Check if CSV namespace doesn't exist on server
        if server_idx >= len(ns_array):
            needs_mapping = True
            mismatched_indices.append((csv_idx, server_idx, "not found"))
        # Check if the mapping points to a different URI than expected
        # (This would be a real problem - same index but different namespace)
        elif csv_idx < len(ns_array) and csv_idx != server_idx:
            # There's remapping happening - this is OK if it's intentional
            needs_mapping = True
            mismatched_indices.append((csv_idx, server_idx, "remapped"))
    
    if needs_mapping and not args.allow_ns_mismatch:
        print(f"\n⚠️  ERROR: Namespace index mismatch detected!")
        print(f"   CSV uses namespace indices: {sorted(csv_ns_indices)}")
        print(f"   Namespace mapping: {ns_map}")
        print(f"\n   Mismatches detected:")
        for csv_idx, srv_idx, reason in mismatched_indices:
            if reason == "not found":
                print(f"   - CSV ns={csv_idx} has no corresponding server namespace")
            else:
                print(f"   - CSV ns={csv_idx} maps to server ns={srv_idx}")
        print(f"\n   Solutions:")
        print(f"   1) Regenerate nodeset to match CSV namespace indices")
        print(f"   2) Use --allow-ns-mismatch flag to enable automatic namespace remapping")
        server.stop()
        return
    
    if not args.quiet:
        if needs_mapping:
            print(f"[Namespace remapping] CSV → Server: {dict((c, s) for c, s, _ in mismatched_indices)}")
            print(f"[Using automatic namespace remapping (--allow-ns-mismatch enabled)]")
        else:
            print(f"[Namespace validation] CSV indices {sorted(csv_ns_indices)} align with server ✓")

    # Pre-compute: if ns_map is identity (all indices unchanged), skip regex on every row
    _ns_identity = all(k == v for k, v in ns_map.items())
    
    # Start the tag-injection HTTP API + background override applier
    override_store = OverrideStore()
    httpd = None
    if args.api_port > 0:
        httpd = start_injection_api(override_store, args.api_port, quiet=args.quiet)

    _applier_stop = threading.Event()
    _applier_thread = threading.Thread(
        target=run_override_applier,
        args=(override_store, server, ns_map, args.quiet, _applier_stop),
        daemon=True,
    )
    _applier_thread.start()
    if not args.quiet:
        print("[Override applier] Background thread started (polls every 100 ms)")

    try:
        if args.warmup > 0:
            time.sleep(args.warmup)

        while True:
            prev = df[args.ts_col].iloc[0]
            node_cache: dict = {}
            skipped = 0
            written = 0

            for i, row in enumerate(df.itertuples(index=False), start=1):
                ts = getattr(row, args.ts_col)
                tagname = str(getattr(row, "TAGNAME"))
                dtype = str(getattr(row, "DATATYPE", "String"))
                raw_val = getattr(row, "TAGVALUE", None)

                delta = (ts - prev).total_seconds()
                if delta > 0:
                    time.sleep(delta / args.speed)
                prev = ts

                if args.skip_bad_csv and not is_canonical_nodeid(tagname):
                    skipped += 1
                    if not args.quiet:
                        print(f"[SKIP CSV non-canonical TAGNAME] {tagname} @ {ts.isoformat()}")
                    continue

                # Remap namespace index from CSV to actual server index
                remapped_tagname = tagname if _ns_identity else remap_nodeid(tagname, ns_map)

                # If an active injection override exists for this tag, skip the CSV
                # write entirely — the background applier thread already owns this tag.
                if override_store.is_overridden(tagname, remapped_tagname):
                    continue

                try:
                    node = node_cache.get(remapped_tagname)
                    if node is None:
                        node = server.get_node(remapped_tagname)
                        node_cache[remapped_tagname] = node

                    py_val = cast_value(raw_val, dtype)
                    vtype = VARIANT_TYPE.get(dtype, ua.VariantType.String)
                    dv = ua.DataValue(ua.Variant(py_val, vtype))
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    dv.SourceTimestamp = now
                    dv.ServerTimestamp = now
                    node.set_value(dv)
                    written += 1

                except Exception as ex:
                    skipped += 1
                    if args.skip_bad_csv:
                        if not args.quiet:
                            print(f"[SKIP write failure] {tagname} @ {ts.isoformat()} ({ex})")
                        continue
                    raise

                if not args.quiet and (i % 2000 == 0):
                    print(f"{ts.isoformat()} | processed={i} written={written} skipped={skipped}")

            if not args.loop:
                break

    finally:
        _applier_stop.set()
        if httpd:
            httpd.shutdown()
        server.stop()
        if tmp_nodeset:
            try:
                os.remove(tmp_nodeset)
            except OSError:
                pass


if __name__ == "__main__":
    main()
