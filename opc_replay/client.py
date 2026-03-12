#!/usr/bin/env python3
"""
OPC UA client for monitoring and demonstrating OPC replay server.

This tool connects to an OPC UA server, discovers all variables in a namespace,
and continuously polls them to display value changes.

Usage examples:

  # Connect and monitor all namespaces
  opc-client

  # Monitor specific namespace
  opc-client --namespace 2

  # Monitor specific namespace URI
  opc-client --namespace-uri "http://example.com/simple"

  # Custom polling settings
  opc-client --poll-count 10 --poll-interval 1.0 --display-count 20

  # Connect to remote server
  opc-client --endpoint opc.tcp://192.168.1.100:4840/
"""

import argparse
import sys
import time
from datetime import datetime

try:
    from opcua import Client
except ImportError:
    print("ERROR: opcua package not installed. Run: pip install opcua", file=sys.stderr)
    sys.exit(1)


def browse_variables(node, target_ns=None, found_vars=None):
    """
    Recursively browse to find all variable nodes in target namespace.

    Args:
        node: OPC UA node to browse from
        target_ns: Target namespace index (None = all namespaces)
        found_vars: List to accumulate found variables

    Returns:
        List of variable nodes
    """
    if found_vars is None:
        found_vars = []

    try:
        for child in node.get_children():
            try:
                node_class = child.get_node_class()
                ns_idx = child.nodeid.NamespaceIndex

                # Check if it's a variable node in the target namespace
                if node_class.name == "Variable":
                    if target_ns is None or ns_idx == target_ns:
                        found_vars.append(child)

                # Recursively browse folders/objects
                browse_variables(child, target_ns, found_vars)
            except Exception:
                continue
    except Exception:
        pass

    return found_vars


def main():
    parser = argparse.ArgumentParser(
        description="OPC UA client for monitoring tag changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Monitor all namespaces
  %(prog)s --namespace 2                      # Monitor namespace index 2
  %(prog)s --namespace-uri "urn:example:tags" # Monitor by URI
  %(prog)s --poll-count 10 --poll-interval 1  # 10 polls, 1 second apart
  %(prog)s --endpoint opc.tcp://10.0.0.1:4840 # Connect to remote server
        """,
    )

    parser.add_argument(
        "--endpoint",
        default="opc.tcp://localhost:4840",
        help="OPC UA server endpoint (default: opc.tcp://localhost:4840)",
    )
    parser.add_argument(
        "--namespace",
        "-n",
        type=int,
        default=None,
        help="Namespace index to monitor (default: all non-standard namespaces)",
    )
    parser.add_argument(
        "--namespace-uri",
        default=None,
        help="Namespace URI to monitor (alternative to --namespace)",
    )
    parser.add_argument(
        "--display-count",
        type=int,
        default=25,
        help="Maximum number of changed tags to display per poll (default: 25)",
    )
    parser.add_argument(
        "--poll-interval", type=float, default=2.0, help="Seconds between polls (default: 2.0)"
    )
    parser.add_argument(
        "--poll-count", type=int, default=0, help="Number of times to poll (default: 0=infinite)"
    )

    args = parser.parse_args()

    # Connect to server
    print(f"Connecting to {args.endpoint}...")
    client = Client(args.endpoint)

    try:
        client.connect()
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}", file=sys.stderr)
        print(f"\nIs the OPC UA server running at {args.endpoint}?", file=sys.stderr)
        sys.exit(1)

    try:
        # Get namespace array
        namespaces = client.get_namespace_array()
        print("Server namespaces:")
        for i, ns in enumerate(namespaces):
            print(f"  ns={i}: {ns}")

        # Determine target namespace
        target_ns = args.namespace

        if args.namespace_uri:
            # Find namespace by URI
            try:
                target_ns = namespaces.index(args.namespace_uri)
                print(f"\n✓ Found namespace URI '{args.namespace_uri}' at ns={target_ns}")
            except ValueError:
                print(
                    f"\n✗ ERROR: Namespace URI '{args.namespace_uri}' not found on server",
                    file=sys.stderr,
                )
                print("Available namespaces:", file=sys.stderr)
                for i, ns in enumerate(namespaces):
                    print(f"  ns={i}: {ns}", file=sys.stderr)
                sys.exit(1)
        elif target_ns is not None:
            # Validate namespace index
            if target_ns >= len(namespaces):
                print(
                    f"\n✗ ERROR: Namespace index {target_ns} does not exist on server",
                    file=sys.stderr,
                )
                print(f"Server has namespaces 0-{len(namespaces) - 1}", file=sys.stderr)
                sys.exit(1)
            print(f"\n✓ Monitoring namespace ns={target_ns}")
        else:
            # Auto-select: find first non-standard namespace (skip ns=0 and ns=1)
            for i in range(2, len(namespaces)):
                target_ns = i
                break

            if target_ns is None:
                print(
                    "\n✗ ERROR: No custom namespaces found (only standard ns=0 and ns=1)",
                    file=sys.stderr,
                )
                print("The server may not have any custom tags loaded.", file=sys.stderr)
                sys.exit(1)

            print(f"\n✓ Auto-selected namespace ns={target_ns}: {namespaces[target_ns]}")

        # Discover variables
        print(f"\nDiscovering variables in ns={target_ns}...")
        print("-" * 110)

        objects = client.get_objects_node()
        variables = browse_variables(objects, target_ns)

        if not variables:
            print(f"\n✗ No variables found in ns={target_ns}", file=sys.stderr)
            print("The namespace may be empty or contain only folders/objects.", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(variables)} variables\n")

        # Store previous values for change detection
        prev_values = {}

        # Poll loop with connection monitoring
        poll_num = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        try:
            while args.poll_count == 0 or poll_num < args.poll_count:
                poll_num += 1
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                # Read all variables and track changes
                changed_vars = []
                successful_reads = 0
                failed_reads = 0
                last_error = None

                for var in variables:
                    try:
                        node_id = var.nodeid.to_string()
                        browse_name = var.get_browse_name().Name
                        value = var.get_value()
                        successful_reads += 1

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
                    except Exception as e:
                        failed_reads += 1
                        last_error = e

                # Check if connection is lost
                if successful_reads == 0 and failed_reads > 0:
                    # All reads failed - likely connection problem
                    consecutive_errors += 1
                    print(f"\n✗ Connection error: All reads failed ({last_error})", file=sys.stderr)

                    if consecutive_errors >= max_consecutive_errors:
                        print(
                            f"\n✗ Lost connection to server after {consecutive_errors} failed attempts",
                            file=sys.stderr,
                        )
                        print("  Server may have stopped. Exiting...", file=sys.stderr)
                        break

                    print(
                        f"  Retrying... ({consecutive_errors}/{max_consecutive_errors})",
                        file=sys.stderr,
                    )
                    time.sleep(args.poll_interval)
                    continue
                elif successful_reads > 0:
                    # Some reads succeeded - reset error counter
                    consecutive_errors = 0

                # Display results
                print(f"\n{'=' * 110}")
                print(f"Poll #{poll_num} at {timestamp} - {len(changed_vars)} tag(s) changed")
                print(f"{'=' * 110}")

                if changed_vars:
                    print(f"{'#':<4} {'Timestamp':<23} {'Browse Name':<50} {'Value':<30}")
                    print(f"{'-' * 110}")

                    for i, item in enumerate(changed_vars[: args.display_count], 1):
                        value_str = str(item["value"])[:28]  # Truncate long values
                        print(
                            f"{i:<4} {item['timestamp']:<23} {item['browse_name']:<50} {value_str:<30}"
                        )

                    if len(changed_vars) > args.display_count:
                        remaining = len(changed_vars) - args.display_count
                        print(
                            f"\n... and {remaining} more changed tags (use --display-count to see more)"
                        )
                else:
                    print("No changes detected")

                # Wait before next poll
                if args.poll_count == 0 or poll_num < args.poll_count:
                    print(f"\nWaiting {args.poll_interval}s before next poll... (Ctrl+C to stop)")
                    time.sleep(args.poll_interval)

        except KeyboardInterrupt:
            print("\n\nStopped by user")

        print(f"\n✓ Completed {poll_num} polls")

    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        try:
            client.disconnect()
            print("Disconnected")
        except Exception:
            # Disconnect may fail if connection is already dead
            pass


if __name__ == "__main__":
    main()
