#!/usr/bin/env python3
"""
OPC UA replay server (Python):

- Imports a UA NodeSet2 XML file (address space / tags)
- Replays timestamped tag samples from a CSV file at real-time speed (default) or accelerated (e.g. 10x)

IMPORTANT REALITY:
- If the NodeSet XML itself contains invalid NodeIds (e.g. NodeId="PET001CalcAlarm" with no "ns=...;s=..."),
  the FreeOpcUa importer will crash BEFORE the server starts.
- If you *do not want to "fix" those NodeIds*, the only safe option is to DROP those nodes from the imported NodeSet.
  This script supports that via --drop-bad-nodeset-nodeids.

Separately, the CSV may contain "bad" TAGNAME values; those can be skipped during replay.

Install:
  python -m pip install opcua pandas pyarrow

Typical usage with CSV:
  uv run python opcua_nodeset_replay_server.py --nodeset PET001-UANodeSet.xml --data PET001-2025-10-03.csv --ts-col TS
  uv run python opcua_nodeset_replay_server.py --nodeset PET001-UANodeSet.xml --data PET001-2025-10-03.csv --ts-col TS --speed 10

Typical usage with Parquet:
  uv run python opcua_nodeset_replay_server.py --nodeset PETALL-UANodeSet.xml --data PETALL_20251214_20251221.parquet --ts-col TIMESTAMP --speed 10

Graceful skipping (recommended for your case with PET001CalcAlarm in the NodeSet):
  uv run python opcua_nodeset_replay_server.py \
    --nodeset PET001-UANodeSet.xml \
    --data PET001-2025-10-03.csv \
    --ts-col TS \
    --speed 10 \
    --drop-bad-nodeset-nodeids \
    --skip-bad-csv
"""

import argparse
import time
import re
import tempfile
import os
import xml.etree.ElementTree as ET

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
    ap.add_argument("--nodeset", required=True, help="NodeSet2 XML file")
    ap.add_argument("--data", required=True, help="Data file (.csv or .parquet) with TAGNAME/TAG_NAME, TAGVALUE/VALUE, DATATYPE columns and timestamp column")
    ap.add_argument("--csv", help="(Deprecated: use --data) CSV with TAGNAME,TAGVALUE,DATATYPE and timestamp column")
    ap.add_argument("--ts-col", default="TS", help="Timestamp column name (default: TS, common: TIMESTAMP)")
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speedup (1=real-time, 10=10x faster)")
    ap.add_argument("--offset", type=float, default=0.0, help="Skip ahead by N seconds from the first timestamp (e.g., 3600 skips first hour)")
    ap.add_argument("--loop", action="store_true", help="Loop playback forever")
    ap.add_argument("--max-rows", type=int, default=None, help="Limit number of rows for quick testing")
    ap.add_argument("--warmup", type=float, default=0.0, help="Seconds to wait before replay begins")
    ap.add_argument("--quiet", action="store_true", help="Reduce per-update logging")

    # New "skip, don't fix" behaviors:
    ap.add_argument("--drop-bad-nodeset-nodeids", action="store_true",
                    help="Drop nodes from the imported NodeSet that have non-canonical NodeIds (prevents import crash).")
    ap.add_argument("--skip-bad-csv", action="store_true",
                    help="Skip/log data rows with non-canonical TAGNAMEs, or writes that fail (BadNodeIdUnknown, etc.).")
    
    # Namespace mapping control:
    ap.add_argument("--allow-ns-mismatch", action="store_true",
                    help="Allow namespace index mismatch between data file and server. Automatically maps data namespace indices to server indices. Use this when nodeset was generated with different --namespace-index than data file.")

    args = ap.parse_args()
    
    # Support legacy --csv argument
    data_file = args.data if args.data else args.csv
    if not data_file:
        ap.error("Either --data or --csv is required")

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
        server_idx = ns_map.get(csv_idx, csv_idx)
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
    
    try:
        if args.warmup > 0:
            time.sleep(args.warmup)

        while True:
            prev = df[args.ts_col].iloc[0]
            node_cache: dict[str, object] = {}
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
                remapped_tagname = remap_nodeid(tagname, ns_map)

                try:
                    node = node_cache.get(remapped_tagname)
                    if node is None:
                        node = server.get_node(remapped_tagname)
                        node_cache[remapped_tagname] = node

                    py_val = cast_value(raw_val, dtype)
                    vtype = VARIANT_TYPE.get(dtype, ua.VariantType.String)
                    node.set_value(ua.Variant(py_val, vtype))
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
        server.stop()
        if tmp_nodeset:
            try:
                os.remove(tmp_nodeset)
            except OSError:
                pass


if __name__ == "__main__":
    main()
