#!/usr/bin/env python3
"""
OPC UA client for monitoring and demonstrating OPC replay server.

This tool connects to an OPC UA server, discovers all variables in a namespace,
and continuously monitors them to display value changes.

Supports two monitoring modes:
- Subscription (default): Push-based notifications from server (fast, efficient)
- Polling: Periodic reading of all values (legacy mode)

Usage examples:

  # Subscribe to changes in all namespaces (default mode)
  opc-replay-client

  # Monitor specific namespace
  opc-replay-client --namespace 2

  # Monitor by namespace URI
  opc-replay-client --namespace-uri "http://example.com/simple"

  # Use polling mode instead of subscriptions
  opc-replay-client --read-mode poll --poll-interval 2.0

  # Read nodemap statistics and exit
  opc-replay-client --read-nodemap

  # Browse all namespaces
  opc-replay-client --all-namespaces

  # Output as CSV
  opc-replay-client --format csv > output.csv

  # Quiet mode with periodic summaries
  opc-replay-client --report-frequency 30

  # Show connection statistics
  opc-replay-client --show-stats --report-frequency 15

  # Connect to remote server
  opc-replay-client --endpoint opc.tcp://192.168.1.100:4840/
"""

import argparse
import logging
import sys
import time

try:
    from opcua import Client
except ImportError:
    print("ERROR: opcua package not installed. Run: pip install opcua", file=sys.stderr)
    sys.exit(1)

from .browser import NodeBrowser
from .formatters import create_formatter
from .monitor import PollingMonitor, SubscriptionMonitor
from .statistics import StatisticsCollector

# Module logger
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="OPC UA client for monitoring tag changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Monitor all namespaces (subscription mode)
  %(prog)s --namespace 2                      # Monitor namespace index 2
  %(prog)s --namespace-uri "urn:example:tags" # Monitor by URI
  %(prog)s --read-mode poll --poll-interval 2 # Use polling mode
  %(prog)s --format csv --report-frequency 30 # CSV output with 30s summaries
  %(prog)s --read-nodemap --all-namespaces    # Read nodemap stats and exit
  %(prog)s --endpoint opc.tcp://10.0.0.1:4840 # Connect to remote server
        """,
    )

    # Connection settings
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://localhost:4840",
        help="OPC UA server endpoint (default: opc.tcp://localhost:4840)",
    )

    # Namespace selection
    ns_group = parser.add_mutually_exclusive_group()
    ns_group.add_argument(
        "--namespace",
        "-n",
        type=int,
        default=None,
        help="Namespace index to monitor (default: auto-select first custom namespace)",
    )
    ns_group.add_argument(
        "--namespace-uri",
        default=None,
        help="Namespace URI to monitor (alternative to --namespace)",
    )
    ns_group.add_argument(
        "--all-namespaces",
        action="store_true",
        help="Browse and monitor all namespaces (including ns=0 and ns=1)",
    )

    # Monitoring mode
    parser.add_argument(
        "--read-mode",
        choices=["subscribe", "poll"],
        default="subscribe",
        help="Monitoring mode: subscribe (default, push-based) or poll (legacy, periodic reads)",
    )

    # Polling mode settings
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between polls in polling mode (default: 2.0)",
    )
    parser.add_argument(
        "--poll-count",
        type=int,
        default=0,
        help="Number of times to poll (default: 0=infinite)",
    )

    # Subscription mode settings
    parser.add_argument(
        "--max-nodes-per-subscription",
        type=int,
        default=1000,
        help="Maximum nodes per subscription in subscribe mode (default: 1000, helps with large node counts)",
    )

    # Output settings
    parser.add_argument(
        "--format",
        choices=["console", "csv", "json"],
        default="console",
        help="Output format: console (default), csv, or json",
    )
    parser.add_argument(
        "--display-count",
        type=int,
        default=25,
        help="Maximum number of changed tags to display per poll in console mode (default: 25)",
    )

    # Quiet mode and statistics
    parser.add_argument(
        "--report-frequency",
        type=int,
        default=0,
        help="Seconds between summary reports (0=off, shows all changes)",
    )
    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Display connection statistics with reports",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)"
    )

    # Nodemap reading
    parser.add_argument(
        "--read-nodemap",
        action="store_true",
        help="Read nodemap, print statistics, and exit (no monitoring)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = getattr(logging, args.log_level)
    if log_level == logging.DEBUG:
        # DEBUG: Show timestamps and logger names
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # INFO/WARNING/ERROR: Clean format
        logging.basicConfig(
            level=log_level,
            format='%(message)s'
        )
        # Always suppress opcua library warnings unless DEBUG
        logging.getLogger("opcua").setLevel(logging.ERROR)

    # Connect to server
    print(f"Connecting to {args.endpoint}...")
    client = Client(args.endpoint)

    # Increase timeout for large node counts (default is usually 1-4 seconds)
    client.session_timeout = 30000  # 30 seconds (in milliseconds)

    try:
        client.connect()
        print("[OK] Connected\n")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}", file=sys.stderr)
        print(f"\nIs the OPC UA server running at {args.endpoint}?", file=sys.stderr)
        sys.exit(1)

    try:
        # Get namespace array
        namespaces = client.get_namespace_array()
        print("Server namespaces:")
        for i, ns in enumerate(namespaces):
            print(f"  ns={i}: {ns}")
        print()

        # Create browser
        browser = NodeBrowser(client, namespaces)

        # Quick mode: read nodemap and exit
        if args.read_nodemap:
            if args.all_namespaces:
                stats = browser.read_nodemap_stats()
            elif args.namespace is not None:
                stats = browser.read_nodemap_stats(args.namespace)
            elif args.namespace_uri:
                try:
                    ns_idx = namespaces.index(args.namespace_uri)
                    stats = browser.read_nodemap_stats(ns_idx)
                except ValueError:
                    print(
                        f"[ERROR] Namespace URI '{args.namespace_uri}' not found", file=sys.stderr
                    )
                    sys.exit(1)
            else:
                # Auto-select first custom namespace
                target_ns = None
                for i in range(2, len(namespaces)):
                    target_ns = i
                    break
                if target_ns is None:
                    print("[ERROR] No custom namespaces found", file=sys.stderr)
                    sys.exit(1)
                stats = browser.read_nodemap_stats(target_ns)

            browser.print_nodemap_stats(stats)
            return

        # Determine target namespace(s) for monitoring
        nodes = []

        if args.all_namespaces:
            print("Discovering variables in all namespaces...")
            print("-" * 80)
            all_vars = browser.browse_all_namespaces()
            for ns_idx, vars_list in all_vars.items():
                print(f"  ns={ns_idx}: {len(vars_list)} variables")
                nodes.extend(vars_list)
            print(f"\nTotal: {len(nodes)} variables\n")

        elif args.namespace_uri:
            # Find namespace by URI
            try:
                target_ns = namespaces.index(args.namespace_uri)
                print(f"[OK] Found namespace URI '{args.namespace_uri}' at ns={target_ns}\n")
            except ValueError:
                print(f"[ERROR] Namespace URI '{args.namespace_uri}' not found", file=sys.stderr)
                print("Available namespaces:", file=sys.stderr)
                for i, ns in enumerate(namespaces):
                    print(f"  ns={i}: {ns}", file=sys.stderr)
                sys.exit(1)

            print(f"Discovering variables in ns={target_ns}...")
            print("-" * 80)
            nodes = browser.browse_namespace(target_ns)
            print(f"Found {len(nodes)} variables\n")

        elif args.namespace is not None:
            # Validate namespace index
            if args.namespace >= len(namespaces):
                print(f"[ERROR] Namespace index {args.namespace} does not exist", file=sys.stderr)
                print(f"Server has namespaces 0-{len(namespaces) - 1}", file=sys.stderr)
                sys.exit(1)

            print(f"[OK] Monitoring namespace ns={args.namespace}\n")
            print(f"Discovering variables in ns={args.namespace}...")
            print("-" * 80)
            nodes = browser.browse_namespace(args.namespace)
            print(f"Found {len(nodes)} variables\n")

        else:
            # Auto-select: find first non-standard namespace (skip ns=0 and ns=1)
            target_ns = None
            for i in range(2, len(namespaces)):
                target_ns = i
                break

            if target_ns is None:
                print(
                    "[ERROR] No custom namespaces found (only standard ns=0 and ns=1)",
                    file=sys.stderr,
                )
                print("The server may not have any custom tags loaded.", file=sys.stderr)
                sys.exit(1)

            print(f"[OK] Auto-selected namespace ns={target_ns}: {namespaces[target_ns]}\n")
            print(f"Discovering variables in ns={target_ns}...")
            print("-" * 80)
            nodes = browser.browse_namespace(target_ns)
            print(f"Found {len(nodes)} variables\n")

        # Check if any variables were found
        if not nodes:
            print("[ERROR] No variables found to monitor", file=sys.stderr)
            sys.exit(1)

        # Create components
        formatter_kwargs = {}
        if args.format == "console":
            formatter_kwargs["display_count"] = args.display_count

        formatter = create_formatter(args.format, **formatter_kwargs)
        stats = StatisticsCollector()

        # Create monitor based on read mode
        if args.read_mode == "subscribe":
            print("Starting subscription monitor...\n")
            monitor = SubscriptionMonitor(
                client,
                nodes,
                stats,
                max_nodes_per_subscription=args.max_nodes_per_subscription,
                verbose=(args.log_level == "DEBUG"),
            )
        else:
            print(f"Starting polling monitor (interval: {args.poll_interval}s)...\n")
            monitor = PollingMonitor(client, nodes, stats, args.poll_interval)

        # Start monitoring
        monitor.start()

        # Monitoring loop
        poll_count = 0
        last_report_time = time.time()
        max_consecutive_errors = 3
        consecutive_errors = 0

        try:
            while args.poll_count == 0 or poll_count < args.poll_count:
                poll_count += 1

                try:
                    # Get changes (waits for poll interval or subscription notifications)
                    if args.read_mode == "subscribe":
                        # In subscription mode, just sleep briefly and collect buffered changes
                        time.sleep(0.1)

                    changes = monitor.get_changes()
                    consecutive_errors = 0  # Reset on success

                    # Determine if it's time for a report
                    now = time.time()
                    time_for_report = (
                        args.report_frequency > 0
                        and (now - last_report_time) >= args.report_frequency
                    )

                    if args.report_frequency > 0:
                        # Quiet mode: only show summaries
                        if time_for_report:
                            formatter.format_summary(stats.get_summary())
                            last_report_time = now
                    else:
                        # Normal mode: show all changes
                        if changes or (args.read_mode == "poll"):
                            formatter.format_changes(changes)

                    # Show statistics if requested
                    if args.show_stats and time_for_report:
                        summary = stats.get_summary()
                        print("\n[Statistics]")
                        print(f"  Uptime: {summary['uptime_formatted']}")
                        print(f"  Reads: {summary['successful_reads']}/{summary['total_reads']}")
                        print(f"  Changes: {summary['total_changes']}")
                        print(f"  Errors: {summary['error_count']}")
                        if args.read_mode == "subscribe":
                            print(f"  Datachange notifications: {summary['datachange_count']}")

                except ConnectionError as e:
                    consecutive_errors += 1
                    print(f"\n[ERROR] Connection error: {e}", file=sys.stderr)

                    if consecutive_errors >= max_consecutive_errors:
                        print(
                            f"\n[ERROR] Lost connection after {consecutive_errors} failed attempts",
                            file=sys.stderr,
                        )
                        print("  Server may have stopped. Exiting...", file=sys.stderr)
                        break

                    print(
                        f"  Retrying... ({consecutive_errors}/{max_consecutive_errors})",
                        file=sys.stderr,
                    )
                    time.sleep(args.poll_interval if args.read_mode == "poll" else 1.0)

        except KeyboardInterrupt:
            print("\n\nStopped by user")

        # Stop monitoring
        monitor.stop()

        print(f"\n[OK] Completed {poll_count} monitoring cycles")

    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
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
