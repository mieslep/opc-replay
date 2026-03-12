#!/usr/bin/env python3
"""
Integration test: OPC UA client to monitor tag changes.

Tests the OPC UA server by connecting and polling for tag value changes.

Requirements:
  - None - test automatically starts OPC UA server with test data

Usage (pytest):
  pytest tests/integration/test_client.py -v -s

Usage (standalone):
  python tests/integration/test_client.py
  python tests/integration/test_client.py --poll-count 10 --poll-interval 1.0
"""

import argparse
import time
from datetime import datetime

import pytest
from opcua import Client


@pytest.mark.integration
def test_opcua_client_monitor(
    opcua_test_server,
    tag_read_count=25,
    poll_interval=0.5,  # Faster for automated tests
    poll_count=3,  # Default to 3 polls for pytest
    namespace=2,
):
    """
    Test OPC UA client by monitoring tag changes.

    Args:
        opcua_test_server: Pytest fixture providing server info
        tag_read_count: Number of changed tags to display per poll
        poll_interval: Seconds between polls
        poll_count: Number of times to poll (0 for infinite)
        namespace: Namespace index to monitor
    """
    endpoint = opcua_test_server["endpoint"]
    client = Client(endpoint)
    client.connect()

    try:
        # Check namespace array
        namespaces = client.get_namespace_array()
        print("Namespaces on server:")
        for i, ns in enumerate(namespaces):
            print(f"  ns={i}: {ns}")

        # Use specified or default namespace (typically ns=2 for example data)
        target_ns_idx = namespace
        if target_ns_idx >= len(namespaces):
            pytest.fail(
                f"Namespace {target_ns_idx} not found. Server has {len(namespaces)} namespaces."
            )

        print(f"\nMonitoring namespace: ns={target_ns_idx} ({namespaces[target_ns_idx]})")

        # Browse to find all variable nodes in the target namespace
        print(f"\nDiscovering all tags in ns={target_ns_idx}...")
        print("-" * 80)

        root = client.get_root_node()
        objects = client.get_objects_node()

        # Recursively browse to find ALL variable nodes in the target namespace
        def browse_variables(node, target_ns, found_vars=None):
            if found_vars is None:
                found_vars = []

            try:
                for child in node.get_children():
                    try:
                        # Check if it's a variable node in the target namespace
                        node_class = child.get_node_class()
                        if (
                            node_class.name == "Variable"
                            and child.nodeid.NamespaceIndex == target_ns
                        ):
                            found_vars.append(child)
                        # Recursively browse folders/objects
                        browse_variables(child, target_ns, found_vars)
                    except Exception:
                        continue
            except Exception:
                pass
            return found_vars

        variables = browse_variables(objects, target_ns_idx)

        print(f"Found {len(variables)} total variables\n")

        # Store previous values
        prev_values = {}

        # Poll loop
        poll_num = 0
        try:
            while poll_count == 0 or poll_num < poll_count:
                poll_num += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # Read all variables and track changes
                changed_vars = []
                for var in variables:
                    try:
                        node_id = var.nodeid.to_string()
                        browse_name = var.get_browse_name().Name
                        value = var.get_value()

                        # Check if value changed
                        if node_id not in prev_values or prev_values[node_id] != value:
                            read_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            changed_vars.append(
                                {
                                    "timestamp": read_time,
                                    "node_id": node_id,
                                    "browse_name": browse_name,
                                    "value": value,
                                    "prev_value": prev_values.get(node_id, "N/A"),
                                }
                            )
                            prev_values[node_id] = value
                    except Exception:
                        continue

                # Display changed values (up to tag-read-count)
                print(f"\n{'=' * 110}")
                print(f"Poll #{poll_num} at {timestamp} - {len(changed_vars)} tag(s) changed")
                print(f"{'=' * 110}")

                if changed_vars:
                    print(f"{'#':<4} {'Timestamp':<23} {'NodeID':<50} {'Value':<30}")
                    print(f"{'-' * 110}")

                    for i, item in enumerate(changed_vars[:tag_read_count], 1):
                        value_str = str(item["value"])[:28]  # Truncate long values
                        print(
                            f"{i:<4} {item['timestamp']:<23} {item['browse_name']:<50} {value_str:<30}"
                        )

                    if len(changed_vars) > tag_read_count:
                        print(
                            f"\n... and {len(changed_vars) - tag_read_count} more changed tags (use --tag-read-count to see more)"
                        )
                else:
                    print("No changes detected")

                if poll_count == 0 or poll_num < poll_count:
                    print(f"\nWaiting {poll_interval}s before next poll... (Ctrl+C to stop)")
                    time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n\nStopped by user")

        print(f"\n✓ Completed {poll_num} polls")

        # Assertions for pytest
        assert len(variables) > 0, "Should find at least one variable in the namespace"
        assert poll_num > 0, "Should complete at least one poll"

    except Exception as e:
        pytest.fail(f"Test failed: {e}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    # Allow running as standalone CLI script
    parser = argparse.ArgumentParser(description="Test OPC UA client - monitor tag changes")
    parser.add_argument(
        "--tag-read-count",
        type=int,
        default=25,
        help="Number of changed tags to display per poll (default: 25)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0, help="Seconds between polls (default: 2.0)"
    )
    parser.add_argument(
        "--poll-count",
        type=int,
        default=5,
        help="Number of times to poll (default: 5, use 0 for infinite)",
    )
    parser.add_argument(
        "--namespace", type=int, default=2, help="Namespace index to monitor (default: 2)"
    )
    args = parser.parse_args()

    test_opcua_client_monitor(
        tag_read_count=args.tag_read_count,
        poll_interval=args.poll_interval,
        poll_count=args.poll_count,
        namespace=args.namespace,
    )
