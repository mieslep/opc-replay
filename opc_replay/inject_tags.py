#!/usr/bin/env python3
"""
Client script to inject tag overrides into a running OPC UA replay server.

Usage examples:

  # Single tag injection (override for 60 seconds, starting immediately):
  opc-replay-inject --tag "ns=2;s=PET001.Temperature" --value 95.5 --duration 60

  # Delayed injection (starts after 10 seconds, lasts 30 seconds):
  opc-replay-inject --tag "ns=2;s=PET001.Pressure" --value 3.2 --offset 10 --duration 30

  # Load multiple injections from a CSV file:
  opc-replay-inject --file injections.csv

  # Load from a JSON file:
  opc-replay-inject --file injections.json

  # Target a different server/port:
  opc-replay-inject --url http://localhost:9090 --tag "ns=2;s=Tag" --value 1

  # List active overrides:
  opc-replay-inject --list

  # Clear all overrides:
  opc-replay-inject --clear

CSV file format (header required):
  tagname,value,time_offset_s,duration_s[,dtype]
  ns=2;s=PET001.Temperature,95.5,0,60
  ns=2;s=PET001.Pressure,3.2,10,30
  ns=2;s=PET001.FlowInt,42,0,60,Int32

  dtype column is optional. When omitted, the Python type of value is used
  (int->Int64, float->Double, bool->Boolean, str->String). Supported dtype
  values: Float, Double, Int16, Int32, Int64, UInt16, UInt32, Boolean, String.

JSON file format:
  [
    {"tagname": "ns=2;s=PET001.Temperature", "value": 95.5, "time_offset_s": 0, "duration_s": 60},
    {"tagname": "ns=2;s=PET001.Pressure",    "value": 3.2,  "time_offset_s": 10, "duration_s": 30},
    {"tagname": "ns=2;s=PET001.FlowInt",     "value": 42,   "time_offset_s": 0,  "duration_s": 60, "dtype": "Int32"}
  ]
  The dtype field is optional.
"""

import argparse
import csv
import json
import logging
import sys
import urllib.error
import urllib.request

# Module logger
logger = logging.getLogger(__name__)


def send_injections(base_url: str, injections: list[dict]):
    """POST injections to the replay server API."""
    url = f"{base_url.rstrip('/')}/inject"
    payload = json.dumps({"injections": injections}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            print(json.dumps(body, indent=2))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        print("Is the replay server running with --api-port enabled?", file=sys.stderr)
        sys.exit(1)


def list_overrides(base_url: str):
    """GET active overrides from the replay server."""
    url = f"{base_url.rstrip('/')}/inject"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            overrides = body.get("overrides", [])
            if not overrides:
                print("No active or pending overrides.")
                return
            print(f"{'TAGNAME':<50} {'VALUE':<15} {'ACTIVE':<8} {'PENDING':<8} {'REMAINING_S':<12}")
            print("-" * 95)
            for o in overrides:
                print(
                    f"{o['tagname']:<50} {str(o['value']):<15} {str(o['active']):<8} {str(o['pending']):<8} {o['remaining_s']:<12}"
                )
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


def clear_overrides(base_url: str):
    """DELETE all overrides."""
    url = f"{base_url.rstrip('/')}/inject"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            print(body.get("status", "done"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


def load_file(path: str) -> list[dict]:
    """Load injections from a CSV or JSON file."""
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "injections" in data:
                return data["injections"]
            if isinstance(data, list):
                return data
            raise ValueError('JSON must be an array or {"injections": [...]}')

    # Treat as CSV
    items = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = {
                "tagname": row["tagname"].strip(),
                "value": _try_number(row["value"].strip()),
                "time_offset_s": float(row.get("time_offset_s", 0)),
                "duration_s": float(row.get("duration_s", 60)),
            }
            dtype = row.get("dtype", "").strip()
            if dtype:
                item["dtype"] = dtype
            items.append(item)
    return items


def _try_number(val: str):
    """Attempt to convert a string value to int or float, else return string."""
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        # Handle boolean-like strings
        if val.lower() in ("true", "false"):
            return val.lower() == "true"
        return val


def main():
    ap = argparse.ArgumentParser(
        description="Inject tag overrides into a running OPC UA replay server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--url",
        default="http://localhost:8080",
        help="Base URL of the replay server injection API (default: http://localhost:8080)",
    )

    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--tag", help="Tag name (NodeId) to inject, e.g. 'ns=2;s=PET001.Temperature'"
    )
    group.add_argument("--file", help="Path to a CSV or JSON file with multiple injections")
    group.add_argument("--list", action="store_true", help="List active and pending overrides")
    group.add_argument("--clear", action="store_true", help="Clear all overrides")

    ap.add_argument("--value", help="Value to set (required with --tag)")
    ap.add_argument(
        "--offset",
        type=float,
        default=0,
        help="Seconds before the override activates (default: 0 = immediate)",
    )
    ap.add_argument(
        "--duration", type=float, default=60, help="Seconds to maintain the override (default: 60)"
    )
    ap.add_argument(
        "--dtype",
        help="Optional OPC UA data type hint, e.g. Float, Int32, Boolean (default: inferred from value type)",
    )
    ap.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)",
    )

    args = ap.parse_args()

    # Configure logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(message)s"
        if log_level >= logging.INFO
        else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.list:
        list_overrides(args.url)
        return

    if args.clear:
        clear_overrides(args.url)
        return

    if args.tag:
        if args.value is None:
            ap.error("--value is required when using --tag")
        injections = [
            {
                "tagname": args.tag,
                "value": _try_number(args.value),
                "time_offset_s": args.offset,
                "duration_s": args.duration,
                **({"dtype": args.dtype} if args.dtype else {}),
            }
        ]
        send_injections(args.url, injections)
        return

    if args.file:
        injections = load_file(args.file)
        print(f"Loaded {len(injections)} injection(s) from {args.file}")
        send_injections(args.url, injections)
        return


if __name__ == "__main__":
    main()
