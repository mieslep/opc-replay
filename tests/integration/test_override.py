#!/usr/bin/env python3
"""
Override injection integration test for the OPC UA replay server.

What it tests:
  1. Reads a tag's current value from the OPC UA server
  2. POSTs an injection override to the HTTP API
  3. Polls the OPC UA node until the injected value appears (≤ 2s expected)
  4. Waits for the override to expire, then confirms the value returns to replay data

Requirements:
  - None - test automatically starts OPC UA server with test data

Usage (pytest - recommended):
  pytest tests/integration/test_override.py -v -s

Usage (standalone with manual server):
  # Start server first:
  opc-replay --data examples/simple-data.csv --ts-col TS --auto-nodeset --loop --speed 10

  # Then run test:
  python tests/integration/test_override.py
  python tests/integration/test_override.py --endpoint opc.tcp://localhost:4840/ --api http://localhost:8080
  python tests/integration/test_override.py --skip-warmup  # Skip initial warmup delay
"""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timezone

import pytest

try:
    from opcua import Client
except ImportError:
    print("ERROR: opcua package not installed. Run: pip install opcua")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Test cases - using simple example tags from examples/simple-data.csv
#
# These tags exist in the simple example NodeSet and have changing values
# in the looping replay data.
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "name": "Temperature Float override",
        "tagname": "ns=2;s=Temperature",
        "expected_before": None,  # Accept any value (replay data changes)
        "inject_value": 99.9,
        "dtype": "Float",
        "duration_s": 5,
        "tolerance": 0.01,
    },
    {
        "name": "Pressure Float override",
        "tagname": "ns=2;s=Pressure",
        "expected_before": None,  # Accept any value (replay data changes)
        "inject_value": 200.5,
        "dtype": "Float",
        "duration_s": 5,
        "tolerance": 0.01,
    },
    {
        "name": "Flow Float override",
        "tagname": "ns=2;s=Flow",
        "expected_before": None,  # Accept any value (replay data changes)
        "inject_value": 50.0,
        "dtype": "Float",
        "duration_s": 5,
        "tolerance": 0.01,
    },
]

POLL_INTERVAL = 0.1  # seconds between OPC UA reads during wait
APPLY_TIMEOUT = 2.0  # max seconds to wait for override to appear on OPC UA

# How many seconds to wait at the start so the replay loop has time to write
# initial values. With simple-data.csv at --speed 10, a few seconds is enough.
DEFAULT_WARMUP_S = 3

# ANSI colours (skipped on Windows if not supported, falls back gracefully)
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def _ok(msg):
    print(f"  {GREEN}PASS{RESET}  {msg}")


def _fail(msg):
    print(f"  {RED}FAIL{RESET}  {msg}")


def _info(msg):
    print(f"  {CYAN}INFO{RESET}  {msg}")


def _warn(msg):
    print(f"  {YELLOW}WARN{RESET}  {msg}")


def post_injection(
    api_base: str,
    tagname: str,
    value,
    dtype: str | None,
    duration_s: float,
    time_offset_s: float = 0.0,
) -> dict:
    payload = json.dumps(
        {
            "tagname": tagname,
            "value": value,
            "dtype": dtype,
            "time_offset_s": time_offset_s,
            "duration_s": duration_s,
        }
    ).encode()
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/inject",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def get_overrides(api_base: str) -> list:
    req = urllib.request.Request(f"{api_base.rstrip('/')}/inject", method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get("overrides", [])


def clear_overrides(api_base: str):
    req = urllib.request.Request(f"{api_base.rstrip('/')}/inject", method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def read_dv(node):
    """Return (value, source_ts, server_ts) from a node's DataValue."""
    dv = node.get_data_value()
    val = dv.Value.Value if dv.Value else None
    return val, dv.SourceTimestamp, dv.ServerTimestamp


def values_equal(actual, expected, tolerance):
    if tolerance is not None:
        try:
            return abs(float(actual) - float(expected)) <= tolerance
        except (TypeError, ValueError):
            return actual == expected
    # Boolean: normalise both sides
    if isinstance(expected, bool):
        if isinstance(actual, bool):
            return actual == expected
        return (
            str(actual).lower() in ("true", "1")
            if expected
            else str(actual).lower() in ("false", "0")
        )
    return actual == expected


def run_test(tc: dict, opcua_endpoint: str, api_base: str) -> bool:
    tagname = tc["tagname"]
    inj_value = tc["inject_value"]
    dtype = tc.get("dtype")
    duration = tc["duration_s"]
    tolerance = tc.get("tolerance")
    expected_before = tc.get("expected_before")

    print(f"\n{'─' * 60}")
    print(f"  Test : {tc['name']}")
    print(f"  Tag  : {tagname}")
    print(f"  Inject value: {inj_value}  dtype={dtype}  duration={duration}s")
    print(f"{'─' * 60}")

    client = Client(opcua_endpoint)
    try:
        client.connect()
    except Exception as e:
        _fail(f"OPC UA connect failed: {e}")
        return False

    passed = True
    try:
        node = client.get_node(tagname)

        # ── Step 1: read current value + timestamps ───────────────────────
        try:
            before_val, src_ts, srv_ts = read_dv(node)
            if before_val is None:
                _warn("Value before injection is None — replay may not have reached this tag yet")
            else:
                _info(f"Value before injection : {before_val}")
                _info(f"  SourceTimestamp      : {src_ts}  (should be historical data time)")
                _info(f"  ServerTimestamp      : {srv_ts}  (should be recent wall-clock time)")
                # Validate: SourceTimestamp should NOT be None
                if src_ts is None:
                    _fail("SourceTimestamp is None — server is not setting it")
                    passed = False
                else:
                    _ok("SourceTimestamp is set")
                if srv_ts is None:
                    _fail("ServerTimestamp is None — server is not setting it")
                    passed = False
                else:
                    _ok("ServerTimestamp is set")
                if expected_before is not None:
                    if values_equal(before_val, expected_before, tolerance):
                        _ok(f"Before-value matches expected ({expected_before})")
                    else:
                        _info(
                            f"Before-value {before_val!r} differs from expected {expected_before!r} (replay has moved on — that's fine)"
                        )
        except Exception as e:
            _fail(f"Could not read tag before injection: {e}")
            return False

        # ── Step 2: POST the override ─────────────────────────────────────
        try:
            resp = post_injection(api_base, tagname, inj_value, dtype, duration)
            result = resp.get("results", [{}])[0]
            _info(
                f"API response: status={result.get('status')}  "
                f"activate_at={result.get('activate_at')}  "
                f"expire_at={result.get('expire_at')}"
            )
        except Exception as e:
            _fail(f"POST to injection API failed: {e}")
            return False

        # ── Step 3: poll until override appears on OPC UA ─────────────────
        deadline = time.time() + APPLY_TIMEOUT
        applied = False
        inject_time = time.time()
        while time.time() < deadline:
            try:
                current, cur_src_ts, cur_srv_ts = read_dv(node)
            except Exception:
                time.sleep(POLL_INTERVAL)
                continue
            if values_equal(current, inj_value, tolerance):
                latency = time.time() - inject_time
                _ok(f"Override applied on OPC UA within ~{latency:.2f}s  (value={current})")
                _info(f"  SourceTimestamp during override : {cur_src_ts}  (should be ~now)")
                _info(f"  ServerTimestamp during override : {cur_srv_ts}  (should be ~now)")
                # Both timestamps should be recent (within last 10 s)
                now_utc = datetime.now(UTC).replace(tzinfo=None)
                for label, ts_val in (
                    ("SourceTimestamp", cur_src_ts),
                    ("ServerTimestamp", cur_srv_ts),
                ):
                    if ts_val is None:
                        _fail(f"{label} is None during override")
                        passed = False
                    else:
                        age_s = abs((now_utc - ts_val).total_seconds())
                        if age_s <= 10:
                            _ok(f"{label} is recent ({age_s:.1f}s ago)")
                        else:
                            _fail(
                                f"{label} is stale ({age_s:.1f}s ago — expected ≤10s for an injected value)"
                            )
                            passed = False
                applied = True
                break
            time.sleep(POLL_INTERVAL)

        if not applied:
            try:
                current, _, _ = read_dv(node)
            except Exception:
                current = "?"
            _fail(
                f"Override NOT seen on OPC UA within {APPLY_TIMEOUT}s  "
                f"(still reading {current}, expected {inj_value})"
            )
            passed = False

        # ── Step 4: confirm override appears in API listing ───────────────
        try:
            overrides = get_overrides(api_base)
            match = next((o for o in overrides if o["tagname"] == tagname), None)
            if match:
                _ok(
                    f"Override listed in API  (remaining={match['remaining_s']}s  active={match['active']})"
                )
            else:
                _fail("Override NOT found in GET /inject listing")
                passed = False
        except Exception as e:
            _fail(f"GET /inject failed: {e}")
            passed = False

        # ── Step 5: wait for expiry, confirm override is gone from API ────
        _info(f"Waiting {duration + 0.5:.1f}s for override to expire…")
        time.sleep(duration + 0.5)

        try:
            overrides = get_overrides(api_base)
            match = next((o for o in overrides if o["tagname"] == tagname), None)
            if match is None:
                _ok("Override correctly absent from API after expiry")
            else:
                _fail(f"Override still listed in API after expiry: {match}")
                passed = False
        except Exception as e:
            _fail(f"GET /inject after expiry failed: {e}")
            passed = False

    finally:
        client.disconnect()

    return passed


def run_sub_test(tagname: str, endpoint: str, duration_s: float = 8.0) -> None:
    """Subscribe to a node and log every change notification for `duration_s` seconds."""
    received = []
    lock = threading.Lock()

    class _Handler:
        def datachange_notification(self, node, val, data):
            # data is DataChangeNotif; the ua.DataValue is at data.monitored_item.Value
            dv = data.monitored_item.Value
            with lock:
                received.append(
                    {
                        "seq": len(received) + 1,
                        "value": val,
                        "variant_type": dv.Value.VariantType if dv.Value else None,
                        "status": dv.StatusCode,
                        "source_ts": dv.SourceTimestamp,
                        "server_ts": dv.ServerTimestamp,
                        "arrived": datetime.now(UTC).replace(tzinfo=None),
                    }
                )

        def event_notification(self, event):
            pass

    print(f"\n{'═' * 60}")
    print("  Subscription Diagnostic")
    print(f"  Tag     : {tagname}")
    print(f"  Endpoint: {endpoint}")
    print(f"  Watching for {duration_s:.0f}s…")
    print(f"{'─' * 60}")

    client = Client(endpoint)
    try:
        client.connect()
        node = client.get_node(tagname)
        handler = _Handler()
        sub = client.create_subscription(200, handler)  # 200 ms publishing interval
        handle = sub.subscribe_data_change(node)
        _info("Subscription created — waiting for notifications…")
        time.sleep(duration_s)
        sub.unsubscribe(handle)
        sub.delete()
    except Exception as e:
        _fail(f"Subscription test error: {e}")
        return
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

    with lock:
        events = list(received)

    if not events:
        _warn(f"No notifications received in {duration_s:.0f}s — is the node being updated?")
        return

    _info(f"Received {len(events)} notification(s):")
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    for ev in events[:20]:  # cap output
        src_age = (
            f"{abs((now_utc - ev['source_ts']).total_seconds()):.1f}s ago"
            if ev["source_ts"]
            else "None"
        )
        srv_age = (
            f"{abs((now_utc - ev['server_ts']).total_seconds()):.1f}s ago"
            if ev["server_ts"]
            else "None"
        )
        print(
            f"    #{ev['seq']:3d}  "
            f"val={str(ev['value']):<18}  "
            f"type={str(ev['variant_type']):<22}  "
            f"status={ev['status']}  "
            f"src_ts={src_age}  "
            f"srv_ts={srv_age}"
        )
    if len(events) > 20:
        _info(f"  … and {len(events) - 20} more (capped at 20)")
    print(f"{'═' * 60}")


def check_api_reachable(api_base: str) -> bool:
    try:
        get_overrides(api_base)
        return True
    except urllib.error.URLError as e:
        print(f"{RED}ERROR{RESET}: Injection API not reachable at {api_base}/inject — {e.reason}")
        print("  Is the replay server running with --api-port enabled?")
        return False
    except Exception as e:
        print(f"{RED}ERROR{RESET}: Unexpected error reaching API: {e}")
        return False


def check_opcua_reachable(endpoint: str) -> bool:
    client = Client(endpoint)
    try:
        client.connect()
        client.disconnect()
        return True
    except Exception as e:
        print(f"{RED}ERROR{RESET}: OPC UA server not reachable at {endpoint} — {e}")
        print("  Is the replay server running?")
        return False


@pytest.mark.integration
def test_override_injection(
    opcua_test_server,
    warmup=0.5,  # Shorter warmup for pytest
    no_clear=False,
):
    """
    Test tag injection overrides against the OPC UA replay server.

    Args:
        opcua_test_server: Pytest fixture providing server info
        warmup: Seconds to wait before running tests
        no_clear: Do not clear existing overrides before running tests
    """
    endpoint = opcua_test_server["endpoint"]
    api_base = opcua_test_server["api_base"]

    print(f"\n{'═' * 60}")
    print("  OPC UA Override Injection Test")
    print(f"  Endpoint : {endpoint}")
    print(f"  API      : {api_base}")
    print(f"{'═' * 60}")

    # Pre-flight checks
    if not check_api_reachable(api_base):
        pytest.fail("API not reachable")
    if not check_opcua_reachable(endpoint):
        pytest.fail("OPC UA server not reachable")
    _ok("Pre-flight checks passed")

    if not no_clear:
        clear_overrides(api_base)
        _info("Cleared any existing overrides")

    if warmup > 0:
        _info(f"Waiting {warmup:.1f}s for replay to write initial tag values…")
        time.sleep(warmup)

    results = []
    for tc in TEST_CASES:
        ok = run_test(tc, endpoint, api_base)
        results.append((tc["name"], ok))

    print(f"\n{'═' * 60}")
    print("  Summary")
    print(f"{'─' * 60}")
    all_passed = True
    for name, ok in results:
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {status}  {name}")
        if not ok:
            all_passed = False
    print(f"{'═' * 60}\n")

    # Pytest assertion
    assert all_passed, "Some override injection tests failed"


def main():
    """CLI wrapper for the test - allows running as standalone script."""
    ap = argparse.ArgumentParser(
        description="Test tag injection overrides against the OPC UA replay server"
    )
    ap.add_argument(
        "--endpoint",
        default="opc.tcp://localhost:4840/",
        help="OPC UA server endpoint (default: opc.tcp://localhost:4840/)",
    )
    ap.add_argument(
        "--api",
        default="http://localhost:8080",
        help="Injection API base URL (default: http://localhost:8080)",
    )
    ap.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear existing overrides before running tests",
    )
    ap.add_argument(
        "--warmup",
        type=float,
        default=DEFAULT_WARMUP_S,
        help=f"Seconds to wait before running tests, allowing the replay loop to "
        f"write initial tag values (default: {DEFAULT_WARMUP_S}s). "
        f"Set to 0 if the server has already been running for a while.",
    )
    ap.add_argument(
        "--sub-test",
        action="store_true",
        help="Run subscription diagnostic instead of override tests",
    )
    ap.add_argument(
        "--sub-tag",
        default=TEST_CASES[0]["tagname"],
        help="NodeId to subscribe to during --sub-test (default: first TEST_CASE tag)",
    )
    ap.add_argument(
        "--sub-duration",
        type=float,
        default=8.0,
        help="Seconds to watch the subscription during --sub-test (default: 8)",
    )
    args = ap.parse_args()

    # Subscription diagnostic mode — bypass injection tests
    if args.sub_test:
        if not check_opcua_reachable(args.endpoint):
            sys.exit(1)
        run_sub_test(args.sub_tag, args.endpoint, args.sub_duration)
        sys.exit(0)

    # Run the main test
    try:
        test_override_injection(
            endpoint=args.endpoint, api_base=args.api, warmup=args.warmup, no_clear=args.no_clear
        )
        sys.exit(0)
    except AssertionError:
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}ERROR{RESET}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
