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
import json
import logging
import os
import re
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
from opcua import Server, ua

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

# Module logger
logger = logging.getLogger(__name__)


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


def canonicalize_nodeid(s: str, default_ns: int = 2) -> str:
    """
    Convert a possibly non-canonical NodeId string to canonical form.

    If already canonical (ns=X;Y=...), returns unchanged.
    Otherwise, wraps the string as ns={default_ns};s={string}.

    Examples:
        canonicalize_nodeid("ns=2;s=Temperature") -> "ns=2;s=Temperature"
        canonicalize_nodeid("PET001CalcAlarm") -> "ns=2;s=PET001CalcAlarm"
        canonicalize_nodeid("Tank.Level") -> "ns=2;s=Tank.Level"

    Args:
        s: NodeId string (may or may not be canonical)
        default_ns: Namespace index to use for non-canonical NodeIds (default: 2)

    Returns:
        Canonical NodeId string

    Raises:
        ValueError: If input is None, empty, or whitespace-only
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("NodeId cannot be empty or whitespace-only")

    # Already canonical - return as-is
    if is_canonical_nodeid(s):
        return s

    # Non-canonical - wrap as string identifier
    return f"ns={default_ns};s={s}"


def count_variables_in_nodeset(xml_path: str) -> int:
    """
    Count the number of UAVariable elements in a NodeSet XML file.
    This is much faster than scanning DataFrame for unique tags.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Count UAVariable elements (namespace-aware)
    ns = {"ua": "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"}
    variables = root.findall(".//ua:UAVariable", ns)
    return len(variables)


def load_namespace_cache(nodeset_path: str) -> dict | None:
    """
    Load namespace mapping from .nsmeta sidecar file if it exists.
    Returns dict with 'namespaces' list and 'generated' timestamp, or None if not found.
    """
    import json

    cache_path = f"{nodeset_path}.nsmeta"
    try:
        with open(cache_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_namespace_cache(nodeset_path: str, namespaces: list[str]):
    """
    Save namespace mapping to .nsmeta sidecar file for faster loading.
    """
    import json
    from datetime import datetime

    cache_path = f"{nodeset_path}.nsmeta"
    cache_data = {"namespaces": namespaces, "generated": datetime.now().isoformat()}
    with open(cache_path, "w") as f:
        json.dump(cache_data, f, indent=2)


def build_namespace_map(server, nodeset_path: str) -> dict[int, int]:
    """
    Build a mapping from namespace indices in the nodeset XML to actual server indices.
    Returns dict {xml_ns_idx: server_ns_idx}

    Uses .nsmeta cache file if available to skip XML parsing.
    """
    # Try to load from cache first
    cache = load_namespace_cache(nodeset_path)
    xml_namespaces = {}

    if cache and "namespaces" in cache:
        # Use cached namespace data
        for idx, uri in enumerate(cache["namespaces"], start=1):
            if uri:
                xml_namespaces[idx] = uri
    else:
        # Parse the nodeset XML to get namespace URIs and their declared indices
        tree = ET.parse(nodeset_path)
        root = tree.getroot()

        ns_uris_elem = root.find(".//ua:NamespaceUris", NS)
        if ns_uris_elem is not None:
            for idx, uri_elem in enumerate(ns_uris_elem.findall("ua:Uri", NS), start=1):
                uri = uri_elem.text
                if uri:
                    xml_namespaces[idx] = uri

        # Save cache for next time
        namespace_list = (
            [xml_namespaces.get(i, "") for i in range(1, max(xml_namespaces.keys()) + 1)]
            if xml_namespaces
            else []
        )
        if namespace_list:
            save_namespace_cache(nodeset_path, namespace_list)

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

    def add(
        self, tagname: str, value, time_offset_s: float, duration_s: float, dtype: str | None = None
    ):
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
            for _tag, entries in self._overrides.items():
                for e in entries:
                    if e["expire_at"] <= now:
                        continue  # skip already-expired entries
                    result.append(
                        {
                            "tagname": e["tagname"],
                            "value": e["value"],
                            "remaining_s": round(e["expire_at"] - now, 2),
                            "active": e["activate_at"] <= now,
                            "pending": now < e["activate_at"],
                        }
                    )
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
        logger.info("[API] %s - %s", self.address_string(), format % args)

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
            results.append(
                {
                    "tagname": tagname,
                    "value": value,
                    "activate_at": datetime.fromtimestamp(entry["activate_at"], tz=UTC).isoformat(),
                    "expire_at": datetime.fromtimestamp(entry["expire_at"], tz=UTC).isoformat(),
                    "status": "scheduled",
                }
            )

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
                now = datetime.now(UTC).replace(tzinfo=None)
                dv = ua.DataValue(_infer_variant(entry["value"], entry.get("dtype")))
                dv.SourceTimestamp = now
                dv.ServerTimestamp = now
                node.set_value(dv)
            except Exception as ex:
                logger.error("[OVERRIDE applier error] %s: %s", tagname, ex)


def start_injection_api(store: OverrideStore, port: int):
    """Launch the injection HTTP API on a daemon thread."""
    InjectionHandler.override_store = store
    httpd = HTTPServer(("0.0.0.0", port), InjectionHandler)
    httpd.timeout = 0.5
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    # Give the thread a moment to start listening
    time.sleep(0.5)
    logger.info("[API] Injection API listening on http://0.0.0.0:%d/inject", port)
    return httpd


def load_and_prepare_data(
    data_path: str,
    ts_col: str,
    offset: float = 0.0,
    max_rows: int | None = None,
    sort_and_save: bool = False,
):
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
    2. Parse timestamps (if sort_and_save=True, also sort and save)
    3. Apply offset (skip first N seconds from start)
    4. Apply max_rows limit (take first N rows after offset)

    By default, assumes data is already sorted by timestamp for performance.
    Use sort_and_save=True to explicitly sort and save sorted file.

    Returns dataframe with normalized column names: TAGNAME, TAGVALUE, DATATYPE, and timestamp column.
    """
    # Detect file type and load
    if data_path.lower().endswith(".parquet"):
        df = pd.read_parquet(data_path)
    elif data_path.lower().endswith(".csv"):
        df = pd.read_csv(data_path, low_memory=False)
    else:
        raise ValueError(f"Unsupported file type. Must be .csv or .parquet: {data_path}")

    # Normalize column names - support both formats
    column_mapping = {}
    if "TAG_NAME" in df.columns and "TAGNAME" not in df.columns:
        column_mapping["TAG_NAME"] = "TAGNAME"
    if "VALUE" in df.columns and "TAGVALUE" not in df.columns:
        column_mapping["VALUE"] = "TAGVALUE"

    if column_mapping:
        df = df.rename(columns=column_mapping)

    # Verify required columns exist
    required = {"TAGNAME", "TAGVALUE", "DATATYPE"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Data file is missing required columns: {sorted(missing)}. Available: {list(df.columns)}"
        )

    if ts_col not in df.columns:
        raise ValueError(
            f"Data file missing timestamp column '{ts_col}'. Available: {list(df.columns)}"
        )

    # Parse timestamp column
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    df = df.dropna(subset=[ts_col])

    # Sort and save if requested (preprocessing step for faster subsequent runs)
    if sort_and_save:
        logger.info("[Data] Sorting %d rows by %s...", len(df), ts_col)
        df = df.sort_values(ts_col)

        # Generate sorted filename
        import os

        base, ext = os.path.splitext(data_path)
        sorted_path = f"{base}_sorted{ext}"

        # Write sorted file
        logger.info("[Data] Writing sorted data to %s...", sorted_path)
        if sorted_path.lower().endswith(".parquet"):
            df.to_parquet(sorted_path, index=False)
        else:
            df.to_csv(sorted_path, index=False)

        logger.info("[Data] Sorted file saved: %s", sorted_path)
        logger.info("[Data] Use --data %s for faster startup next time", sorted_path)
    # Otherwise assume data is already sorted (skip expensive sort operation)

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
    ap = argparse.ArgumentParser(
        description="OPC UA replay server supporting CSV and Parquet data files"
    )
    ap.add_argument("--endpoint", default="opc.tcp://0.0.0.0:4840/", help="OPC UA endpoint URL")
    ap.add_argument("--server-name", default="ReplayServer", help="Server name")
    ap.add_argument(
        "--nodeset", default=None, help="NodeSet2 XML file (optional if --auto-nodeset is used)"
    )
    ap.add_argument(
        "--data",
        required=True,
        help="Data file (.csv or .parquet) with TAGNAME/TAG_NAME, TAGVALUE/VALUE, DATATYPE columns and timestamp column",
    )
    ap.add_argument(
        "--csv",
        help="(Deprecated: use --data) CSV with TAGNAME,TAGVALUE,DATATYPE and timestamp column",
    )
    ap.add_argument(
        "--ts-col", default="TS", help="Timestamp column name (default: TS, common: TIMESTAMP)"
    )
    ap.add_argument(
        "--speed", type=float, default=1.0, help="Playback speedup (1=real-time, 10=10x faster)"
    )
    ap.add_argument(
        "--offset",
        type=float,
        default=0.0,
        help="Skip ahead by N seconds from the first timestamp (e.g., 3600 skips first hour)",
    )
    ap.add_argument("--loop", action="store_true", help="Loop playback forever")
    ap.add_argument(
        "--max-rows", type=int, default=None, help="Limit number of rows for quick testing"
    )
    ap.add_argument(
        "--warmup", type=float, default=0.0, help="Seconds to wait before replay begins"
    )
    ap.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)",
    )

    # NodeSet auto-generation:
    ap.add_argument(
        "--auto-nodeset",
        action="store_true",
        help="Auto-generate NodeSet from data file (extracts unique TAGNAME+DATATYPE). Saves generated NodeSet for reuse.",
    )
    ap.add_argument(
        "--root-name",
        default=None,
        help="Root object name for auto-generated NodeSet (default: derived from data filename)",
    )
    ap.add_argument(
        "--namespace-uri",
        default=None,
        help="Namespace URI for auto-generated NodeSet (default: urn:<root-name>:tags)",
    )

    # New "skip, don't fix" behaviors:
    ap.add_argument(
        "--allow-non-canonical",
        action="store_true",
        help="Allow non-canonical NodeIds without auto-conversion (may violate OPC UA spec). By default, non-canonical TAGNAMEs like 'PET001' are auto-converted to 'ns=2;s=PET001'.",
    )

    # Namespace mapping control:
    ap.add_argument(
        "--allow-ns-mismatch",
        action="store_true",
        help="Allow namespace index mismatch between data file and server. Automatically maps data namespace indices to server indices. Use this when nodeset was generated with different --namespace-index than data file.",
    )

    # Injection API:
    ap.add_argument(
        "--api-port",
        type=int,
        default=8080,
        help="HTTP port for the tag-injection REST API (default: 8080, 0 to disable)",
    )

    # Performance optimization:
    ap.add_argument(
        "--sort-by-ts",
        action="store_true",
        help="Sort data by timestamp and save sorted file (creates <filename>_sorted.csv or .parquet). Use once to preprocess data for faster subsequent runs. Assumes data is already sorted by default.",
    )

    args = ap.parse_args()

    # Configure logging based on --log-level
    log_level = getattr(logging, args.log_level)

    if log_level == logging.DEBUG:
        # DEBUG: Show timestamps and logger names
        logging.basicConfig(
            level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        # INFO/WARNING/ERROR: Clean format without timestamps
        logging.basicConfig(level=log_level, format="%(message)s")
        # Always suppress opcua library warnings unless DEBUG
        logging.getLogger("opcua").setLevel(logging.ERROR)

    # Support legacy --csv argument
    data_file = args.data if args.data else args.csv
    if not data_file:
        ap.error("Either --data or --csv is required")

    # Check NodeSet requirement
    if not args.nodeset and not args.auto_nodeset:
        ap.error("Either --nodeset or --auto-nodeset is required")

    if args.speed <= 0:
        raise ValueError("--speed must be > 0")

    # Start timing instrumentation
    import time

    _timing_start = time.time()
    _timing_data_load_start = time.time()

    # Load and prepare data (load -> sort -> offset -> max_rows)
    df = load_and_prepare_data(
        data_file,
        args.ts_col,
        offset=args.offset,
        max_rows=args.max_rows,
        sort_and_save=args.sort_by_ts,
    )
    if df.empty:
        raise ValueError("No valid rows found after parsing timestamps.")

    _timing_data_load = time.time() - _timing_data_load_start

    _timing_data_load = time.time() - _timing_data_load_start

    logger.info("[Data] Loaded %d rows from %s", len(df), data_file)
    if args.offset > 0:
        logger.info("[Data] Offset: Skipped first %ss", args.offset)
    logger.info("[Data] Time range: %s to %s", df[args.ts_col].min(), df[args.ts_col].max())
    duration = (df[args.ts_col].max() - df[args.ts_col].min()).total_seconds()
    logger.info("[Data] Duration: %.1fs (%.1f min)", duration, duration / 60)
    # Skip expensive .nunique() - will get count from nodeset later

    unique_tag_count = None  # Will be computed from nodeset or tag_defs

    # Auto-generate NodeSet if requested
    if args.auto_nodeset:
        _timing_nodeset_gen_start = time.time()
        _timing_nodeset_gen_start = time.time()
        # Import here to avoid circular dependency
        from .to_nodeset import generate_nodeset_from_dataframe

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

        # Extract unique tag definitions from data
        tag_defs = df[["TAGNAME", "DATATYPE", "TAGVALUE"]].drop_duplicates(subset=["TAGNAME"])
        unique_tag_count = len(tag_defs)

        mode_info = " (compact mode for faster import)" if unique_tag_count > 5000 else ""
        logger.info(
            "[Auto-NodeSet] Generating from %d unique tags%s...", unique_tag_count, mode_info
        )

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

        _timing_nodeset_gen = time.time() - _timing_nodeset_gen_start

        logger.info("[Auto-NodeSet] Generated: %s", auto_nodeset_path)
        logger.info(
            "[Auto-NodeSet] Tip: Reuse with --nodeset %s for faster startup", auto_nodeset_path
        )

        args.nodeset = auto_nodeset_path
    else:
        _timing_nodeset_gen = 0.0

    # Get unique tag count from existing nodeset if not already computed
    # Only do this for INFO level or higher (expensive operation)
    if unique_tag_count is None and logger.isEnabledFor(logging.INFO):
        _timing_count_start = time.time()
        unique_tag_count = count_variables_in_nodeset(args.nodeset)
        _timing_count = time.time() - _timing_count_start
    else:
        _timing_count = 0.0

    if unique_tag_count is not None:
        logger.info("[Data] Unique tags: %d", unique_tag_count)

    _timing_server_init_start = time.time()

    _timing_server_init_start = time.time()

    server = Server()
    server.set_endpoint(args.endpoint)
    server.set_server_name(args.server_name)

    nodeset_path = args.nodeset
    tmp_nodeset = None

    # Import NodeSet
    logger.info("[NodeSet] Importing %s... (may take 10-30s for large nodesets)", nodeset_path)
    _timing_import_start = time.time()
    server.import_xml(nodeset_path)
    _timing_import = time.time() - _timing_import_start

    _timing_start_server_start = time.time()
    server.start()
    _timing_start_server = time.time() - _timing_start_server_start

    # Build namespace mapping and check for mismatches
    _timing_ns_map_start = time.time()
    ns_map = build_namespace_map(server, nodeset_path)
    _timing_ns_map = time.time() - _timing_ns_map_start
    ns_array = server.get_namespace_array()

    logger.debug("[Server namespaces]")
    for i, ns in enumerate(ns_array):
        logger.debug("  ns=%d: %s", i, ns)

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
        logger.error("")
        logger.error("[WARNING] ERROR: Namespace index mismatch detected!")
        logger.error("   CSV uses namespace indices: %s", sorted(csv_ns_indices))
        logger.error("   Namespace mapping: %s", ns_map)
        logger.error("")
        logger.error("   Mismatches detected:")
        for csv_idx, srv_idx, reason in mismatched_indices:
            if reason == "not found":
                logger.error("   - CSV ns=%d has no corresponding server namespace", csv_idx)
            else:
                logger.error("   - CSV ns=%d maps to server ns=%d", csv_idx, srv_idx)
        logger.error("")
        logger.error("   Solutions:")
        logger.error("   1) Regenerate nodeset to match CSV namespace indices")
        logger.error("   2) Use --allow-ns-mismatch flag to enable automatic namespace remapping")
        server.stop()
        return

    if needs_mapping:
        logger.warning(
            "[Namespace remapping] CSV -> Server: %s",
            {c: s for c, s, _ in mismatched_indices},
        )
        logger.warning("[Using automatic namespace remapping (--allow-ns-mismatch enabled)]")
    else:
        logger.info(
            "[Namespace validation] CSV indices %s align with server [OK]", sorted(csv_ns_indices)
        )

    # Print timing summary
    _timing_total = time.time() - _timing_start
    logger.debug("")
    logger.debug("[Timing] Startup breakdown:")
    logger.debug("  Data load: %.2fs", _timing_data_load)
    if _timing_nodeset_gen > 0:
        logger.debug("  NodeSet generation: %.2fs", _timing_nodeset_gen)
    if _timing_count > 0:
        logger.debug("  Tag count: %.2fs", _timing_count)
    logger.debug("  NodeSet import: %.2fs", _timing_import)
    logger.debug("  Server start: %.2fs", _timing_start_server)
    logger.debug("  Namespace mapping: %.2fs", _timing_ns_map)
    logger.debug("  Total startup: %.2fs", _timing_total)
    logger.debug("")

    # Pre-compute: if ns_map is identity (all indices unchanged), skip regex on every row
    _ns_identity = all(k == v for k, v in ns_map.items())

    # Start the tag-injection HTTP API + background override applier
    override_store = OverrideStore()
    httpd = None
    if args.api_port > 0:
        httpd = start_injection_api(override_store, args.api_port)

    _applier_stop = threading.Event()
    _applier_thread = threading.Thread(
        target=run_override_applier,
        args=(override_store, server, ns_map, _applier_stop),
        daemon=True,
    )
    _applier_thread.start()
    logger.debug("[Override applier] Background thread started (polls every 100 ms)")

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
                tagname = str(row.TAGNAME)
                dtype = str(getattr(row, "DATATYPE", "String"))
                raw_val = getattr(row, "TAGVALUE", None)

                delta = (ts - prev).total_seconds()
                if delta > 0:
                    time.sleep(delta / args.speed)
                prev = ts

                # Auto-convert non-canonical NodeIds to canonical form (unless disabled)
                if not args.allow_non_canonical:
                    try:
                        tagname = canonicalize_nodeid(tagname)
                    except ValueError as e:
                        skipped += 1
                        logger.warning("[SKIP] Invalid TAGNAME: %s @ %s", e, ts.isoformat())
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
                    now = datetime.now(UTC).replace(tzinfo=None)
                    dv.SourceTimestamp = now
                    dv.ServerTimestamp = now
                    node.set_value(dv)
                    written += 1

                except Exception as ex:
                    skipped += 1
                    logger.warning("[SKIP write failure] %s @ %s (%s)", tagname, ts.isoformat(), ex)
                    continue

                if i % 2000 == 0:
                    logger.info(
                        "%s | processed=%d written=%d skipped=%d",
                        ts.isoformat(),
                        i,
                        written,
                        skipped,
                    )

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
