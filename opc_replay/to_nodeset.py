import argparse
import re
import xml.etree.ElementTree as ET
from datetime import date
from xml.dom import minidom

import pandas as pd

from opc_replay.server import canonicalize_nodeid, is_canonical_nodeid

# ---- UA namespaces ----
NS_UA = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
NS_UAX = "http://opcfoundation.org/UA/2008/02/Types.xsd"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("", NS_UA)
ET.register_namespace("uax", NS_UAX)
ET.register_namespace("xsi", NS_XSI)

# ---- UA built-in datatypes ----
UA_BUILTIN = {
    "Boolean": "ns=0;i=1",
    "SByte": "ns=0;i=2",
    "Byte": "ns=0;i=3",
    "Int16": "ns=0;i=4",
    "UInt16": "ns=0;i=5",
    "Int32": "ns=0;i=6",
    "UInt32": "ns=0;i=7",
    "Int64": "ns=0;i=8",
    "UInt64": "ns=0;i=9",
    "Float": "ns=0;i=10",
    "Double": "ns=0;i=11",
    "String": "ns=0;i=12",
    "DateTime": "ns=0;i=13",
}

UAX_TAG = {
    "Boolean": "Boolean",
    "SByte": "SByte",
    "Byte": "Byte",
    "Int16": "Int16",
    "UInt16": "UInt16",
    "Int32": "Int32",
    "UInt32": "UInt32",
    "Int64": "Int64",
    "UInt64": "UInt64",
    "Float": "Float",
    "Double": "Double",
    "String": "String",
    "DateTime": "DateTime",
}

# ---- standard nodes/types ----
OBJECTS_FOLDER = "ns=0;i=85"
FOLDER_TYPE = "ns=0;i=61"
BASE_DATA_VARIABLE_TYPE = "ns=0;i=63"
ORGANIZES = "Organizes"
HAS_TYPE_DEFINITION = "HasTypeDefinition"


def pretty_xml(elem, compact: bool = False) -> str:
    """
    Convert ElementTree to XML string.

    Args:
        elem: Element tree root
        compact: If True, skip pretty-printing (faster, smaller files for large nodesets)
    """
    if compact:
        # Skip pretty-printing for large nodesets (faster, smaller files)
        return ET.tostring(elem, encoding="utf-8").decode("utf-8")
    else:
        # Pretty-print for readability (small nodesets)
        raw = ET.tostring(elem, encoding="utf-8")
        return minidom.parseString(raw).toprettyxml(indent="  ")


def add_ref(refs, ref_type: str, target: str, is_forward=True):
    attrib = {"ReferenceType": ref_type}
    if not is_forward:
        attrib["IsForward"] = "false"
    r = ET.SubElement(refs, f"{{{NS_UA}}}Reference", attrib)
    r.text = target


def extract_s_string(nodeid: str) -> str:
    """
    Extracts the String identifier part from NodeId like:
      ns=2;s=Area.Device.Tag
    Returns 'Area.Device.Tag' (or the full string if not matched).
    """
    m = re.search(r";s=(.*)$", str(nodeid))
    return m.group(1) if m else str(nodeid)


def cast_text(value, dtype: str) -> str:
    if pd.isna(value):
        return ""
    if dtype in ("Float", "Double"):
        return str(float(value))
    if dtype in ("Int16", "UInt16", "Int32", "UInt32", "Int64", "UInt64", "SByte", "Byte"):
        return str(int(float(value)))
    if dtype == "Boolean":
        s = str(value).strip().lower()
        return "true" if s in ("1", "true", "t", "yes", "y") else "false"
    return str(value)


def generate_nodeset_from_dataframe(
    df: pd.DataFrame,
    root_name: str,
    namespace_index: int = 1,
    namespace_uri: str = None,
    split_regex: str = r"\.",
    no_folders: bool = False,
    compact: bool = None,
) -> str:
    """
    Generate OPC UA NodeSet2 XML from a DataFrame with TAGNAME, DATATYPE, and optionally TAGVALUE.

    Args:
        df: DataFrame with columns TAGNAME, DATATYPE, and optionally TAGVALUE
        root_name: Root object name (e.g., "MySystem")
        namespace_index: Namespace index for generated nodes (default: 1)
        namespace_uri: Namespace URI (default: urn:<root_name>:tags)
        split_regex: Regex to split tag names into folder hierarchy (default: "\\.")
        no_folders: If True, place all variables under root without folder hierarchy
        compact: If True, skip pretty-printing for faster generation and smaller files.
                 If None (default), auto-detect based on tag count (compact for >5000 tags)

    Returns:
        XML string of the NodeSet

    Raises:
        ValueError: If required columns are missing or no valid TAGNAMEs found
    """
    # Set default namespace URI
    if namespace_uri is None:
        namespace_uri = f"urn:{root_name.lower()}:tags"

    # Defensive: ensure required columns exist
    for col in ("TAGNAME", "DATATYPE"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    if "TAGVALUE" not in df.columns:
        df = df.copy()
        df["TAGVALUE"] = ""
    else:
        df = df.copy()

    # De-duplicate
    df = df.drop_duplicates(subset=["TAGNAME"])

    # Auto-convert non-canonical NodeIds to canonical form
    df["TAGNAME"] = df["TAGNAME"].astype(str).str.strip()

    # Track conversions for user feedback
    non_canonical_mask = ~df["TAGNAME"].map(is_canonical_nodeid)
    non_canonical = df.loc[non_canonical_mask, "TAGNAME"].unique().tolist()

    # Apply canonicalization
    df["TAGNAME"] = df["TAGNAME"].map(lambda t: canonicalize_nodeid(t, default_ns=namespace_index))

    if non_canonical:
        examples = non_canonical[:4]
        converted_examples = [canonicalize_nodeid(t, default_ns=namespace_index) for t in examples]
        pairs = ", ".join(
            [
                f"'{orig}' -> '{conv}'"
                for orig, conv in zip(examples, converted_examples, strict=False)
            ]
        )
        print(f"[Auto-convert] Canonicalized {len(non_canonical)} TAGNAMEs (examples: {pairs})")

    if df.empty:
        raise ValueError("No valid TAGNAMEs found in DataFrame")

    # Build NodeSet root
    root = ET.Element(f"{{{NS_UA}}}UANodeSet")

    # NamespaceUris
    ns_uris = ET.SubElement(root, f"{{{NS_UA}}}NamespaceUris")
    max_idx = max(1, namespace_index)
    for i in range(1, max_idx + 1):
        uri = "urn:placeholder:ns1"
        if i == namespace_index:
            uri = namespace_uri
        ET.SubElement(ns_uris, f"{{{NS_UA}}}Uri").text = uri

    # Models
    models = ET.SubElement(root, f"{{{NS_UA}}}Models")
    ET.SubElement(
        models,
        f"{{{NS_UA}}}Model",
        {
            "ModelUri": namespace_uri,
            "PublicationDate": str(date.today()),
            "Version": "1.0.0",
        },
    )

    # Root object under Objects
    root_obj_nodeid = f"ns={namespace_index};s={root_name}"
    root_obj = ET.SubElement(
        root,
        f"{{{NS_UA}}}UAObject",
        {
            "NodeId": root_obj_nodeid,
            "BrowseName": f"{namespace_index}:{root_name}",
        },
    )
    ET.SubElement(root_obj, f"{{{NS_UA}}}DisplayName").text = root_name
    refs = ET.SubElement(root_obj, f"{{{NS_UA}}}References")
    add_ref(refs, ORGANIZES, OBJECTS_FOLDER, is_forward=False)
    add_ref(refs, HAS_TYPE_DEFINITION, FOLDER_TYPE, is_forward=True)

    # Optional folder hierarchy
    folders = {"": root_obj_nodeid}

    def ensure_folder(path_parts):
        cur_path = ""
        parent_nodeid = root_obj_nodeid
        for part in path_parts:
            cur_path = f"{cur_path}/{part}" if cur_path else part
            if cur_path in folders:
                parent_nodeid = folders[cur_path]
                continue

            folder_nodeid = f"ns={namespace_index};s=folder:{root_name}/{cur_path}"
            obj = ET.SubElement(
                root,
                f"{{{NS_UA}}}UAObject",
                {
                    "NodeId": folder_nodeid,
                    "BrowseName": f"{namespace_index}:{part}",
                },
            )
            ET.SubElement(obj, f"{{{NS_UA}}}DisplayName").text = part
            r = ET.SubElement(obj, f"{{{NS_UA}}}References")
            add_ref(r, ORGANIZES, parent_nodeid, is_forward=False)
            add_ref(r, HAS_TYPE_DEFINITION, FOLDER_TYPE, is_forward=True)

            folders[cur_path] = folder_nodeid
            parent_nodeid = folder_nodeid
        return parent_nodeid

    splitter = re.compile(split_regex)

    # Create variables
    for _, row in df.iterrows():
        nodeid = str(row["TAGNAME"])
        dtype = str(row.get("DATATYPE", "String"))
        value = row.get("TAGVALUE", "")

        # Rewrite node ID to use target namespace index
        nodeid_match = re.match(r"^ns=(\d+);(.+)$", nodeid)
        if nodeid_match:
            nodeid = f"ns={namespace_index};{nodeid_match.group(2)}"

        datatype_nodeid = UA_BUILTIN.get(dtype, "ns=0;i=12")  # fallback String
        s_part = extract_s_string(nodeid)

        if no_folders:
            parent = root_obj_nodeid
            leaf_name = s_part.split("/")[-1]
        else:
            parts = [p for p in splitter.split(s_part) if p]
            if len(parts) <= 1:
                parent = root_obj_nodeid
                leaf_name = parts[0] if parts else s_part
            else:
                parent = ensure_folder(parts[:-1])
                leaf_name = parts[-1]

        var = ET.SubElement(
            root,
            f"{{{NS_UA}}}UAVariable",
            {
                "NodeId": nodeid,
                "BrowseName": f"{namespace_index}:{leaf_name}",
                "DataType": datatype_nodeid,
                "AccessLevel": "3",
                "UserAccessLevel": "3",
            },
        )
        ET.SubElement(var, f"{{{NS_UA}}}DisplayName").text = leaf_name

        r = ET.SubElement(var, f"{{{NS_UA}}}References")
        add_ref(r, ORGANIZES, parent, is_forward=False)
        add_ref(r, HAS_TYPE_DEFINITION, BASE_DATA_VARIABLE_TYPE, is_forward=True)

        # Initial value snapshot
        val = ET.SubElement(var, f"{{{NS_UA}}}Value")
        tag = UAX_TAG.get(dtype, "String")
        v = ET.SubElement(val, f"{{{NS_UAX}}}{tag}")
        v.text = cast_text(value, dtype)

    # Auto-detect compact mode for large nodesets (>5000 tags)
    if compact is None:
        compact = len(df) > 5000

    return pretty_xml(root, compact=compact)


def main():
    ap = argparse.ArgumentParser(
        description="Generate OPC UA NodeSet2 XML from data file with TAGNAME and DATATYPE columns",
        epilog="""
This tool pre-generates a NodeSet XML file from a data file (CSV or Parquet).
For automatic NodeSet generation during replay, use: opc-replay --auto-nodeset

Examples:
  # Generate from CSV
  python -m opc_replay.to_nodeset --csv data.csv --out nodeset.xml --root-name MySystem

  # With custom namespace
  python -m opc_replay.to_nodeset --csv data.csv --out nodeset.xml --root-name MySystem \\
      --namespace-uri "urn:mycompany:tags"

  # Flat structure (no folder hierarchy)
  python -m opc_replay.to_nodeset --csv data.csv --out nodeset.xml --root-name MySystem \\
      --no-folders
        """,
    )
    ap.add_argument(
        "--csv", required=True, help="Input CSV/Parquet with TAGNAME and DATATYPE columns"
    )
    ap.add_argument("--out", required=True, help="Output .xml NodeSet file")
    ap.add_argument("--root-name", required=True, help="Root object name (e.g., MySystem)")
    ap.add_argument(
        "--namespace-index",
        type=int,
        default=None,
        help="Namespace index for generated nodes. If not specified, auto-detected from data.",
    )
    ap.add_argument(
        "--namespace-uri", default=None, help="Namespace URI. Default: urn:<root-name>:tags"
    )
    ap.add_argument(
        "--split-regex",
        default=r"\.",
        help=r"Regex to split tag names into folders. Default '\.' (dot)",
    )
    ap.add_argument(
        "--no-folders",
        action="store_true",
        help="Do not create folder hierarchy; put all variables under root",
    )
    args = ap.parse_args()

    # Load data file
    if args.csv.endswith(".parquet"):
        df = pd.read_parquet(args.csv)
    else:
        df = pd.read_csv(args.csv)

    # Normalize column names
    if "TAG_NAME" in df.columns:
        df = df.rename(columns={"TAG_NAME": "TAGNAME"})
    if "VALUE" in df.columns and "TAGVALUE" not in df.columns:
        df = df.rename(columns={"VALUE": "TAGVALUE"})

    # Auto-detect namespace index from data if not specified
    if args.namespace_index is None:
        ns_indices = set()
        for tagname in df["TAGNAME"]:
            match = re.match(r"^ns=(\d+);", str(tagname))
            if match:
                ns_indices.add(int(match.group(1)))

        if len(ns_indices) == 0:
            raise ValueError(
                "Could not detect namespace index from TAGNAMEs. Use --namespace-index."
            )
        elif len(ns_indices) > 1:
            print(f"Warning: Multiple namespace indices found: {sorted(ns_indices)}")
            csv_ns = max(ns_indices)
            print(f"Using highest index: ns={csv_ns}")
        else:
            csv_ns = ns_indices.pop()
            print(f"Detected namespace index: ns={csv_ns}")

        # Always generate nodeset for ns=1 (will land at server ns=2)
        args.namespace_index = 1
        print("Generating NodeSet for ns=1 (will appear as ns=2 on server to match data)")
    else:
        print(f"Using specified namespace index: ns={args.namespace_index}")

    # Generate NodeSet XML
    xml_content = generate_nodeset_from_dataframe(
        df=df,
        root_name=args.root_name,
        namespace_index=args.namespace_index,
        namespace_uri=args.namespace_uri,
        split_regex=args.split_regex,
        no_folders=args.no_folders,
    )

    # Write to file
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(xml_content)

    unique_tags = df["TAGNAME"].nunique()
    ns_uri = args.namespace_uri or f"urn:{args.root_name.lower()}:tags"
    print(f"[OK] Wrote {args.out}")
    print(f"  {unique_tags} unique variables")
    print(f"  root={args.root_name}")
    print(f"  ns={args.namespace_index}")
    print(f"  uri={ns_uri}")


if __name__ == "__main__":
    main()
