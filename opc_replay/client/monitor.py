"""Value monitoring classes for OPC UA client."""

import queue
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

try:
    from opcua import Client
except ImportError:
    print("ERROR: opcua package not installed. Run: pip install opcua")
    raise

from .statistics import StatisticsCollector


class ValueMonitor(ABC):
    """Base class for OPC UA value monitoring."""

    def __init__(self, client: Client, nodes: list, stats: StatisticsCollector):
        """
        Initialize value monitor.

        Args:
            client: Connected OPC UA client
            nodes: List of OPC UA nodes to monitor
            stats: Statistics collector instance
        """
        self.client = client
        self.nodes = nodes
        self.stats = stats

    @abstractmethod
    def start(self):
        """Start monitoring."""
        pass

    @abstractmethod
    def get_changes(self) -> list[dict[str, Any]]:
        """
        Get accumulated value changes since last call.

        Returns:
            List of change dicts with keys: timestamp, node_id, browse_name, value
        """
        pass

    @abstractmethod
    def stop(self):
        """Stop monitoring and cleanup."""
        pass


class PollingMonitor(ValueMonitor):
    """Polling-based value monitor (legacy mode)."""

    def __init__(
        self, client: Client, nodes: list, stats: StatisticsCollector, poll_interval: float = 2.0
    ):
        """
        Initialize polling monitor.

        Args:
            client: Connected OPC UA client
            nodes: List of OPC UA nodes to monitor
            stats: Statistics collector instance
            poll_interval: Seconds between polls
        """
        super().__init__(client, nodes, stats)
        self.poll_interval = poll_interval
        self._prev_values = {}
        self._running = False
        self._last_poll_time = 0.0

    def start(self):
        """Initialize monitoring (stores initial values)."""
        self._running = True
        # Pre-populate previous values to avoid everything showing as "changed" on first poll
        for node in self.nodes:
            try:
                node_id = node.nodeid.to_string()
                value = node.get_value()
                self._prev_values[node_id] = value
            except Exception:
                pass

    def get_changes(self) -> list[dict[str, Any]]:
        """
        Poll all nodes and detect changes.

        Returns:
            List of changes detected since last poll
        """
        if not self._running:
            return []

        # Check if enough time has passed since last poll
        now = time.time()
        if now - self._last_poll_time < self.poll_interval:
            time.sleep(self.poll_interval - (now - self._last_poll_time))

        self._last_poll_time = time.time()

        changes = []
        successful_reads = 0
        failed_reads = 0
        start_time = time.time()

        for node in self.nodes:
            try:
                node_id = node.nodeid.to_string()
                browse_name = node.get_browse_name().Name
                value = node.get_value()
                successful_reads += 1

                # Check if value changed
                if node_id not in self._prev_values or self._prev_values[node_id] != value:
                    read_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    changes.append(
                        {
                            "timestamp": read_time,
                            "node_id": node_id,
                            "browse_name": browse_name,
                            "value": value,
                        }
                    )
                    self._prev_values[node_id] = value
                    self.stats.record_change(node_id)

            except Exception as e:
                failed_reads += 1
                self.stats.record_error(e)

        duration = time.time() - start_time
        self.stats.record_read(
            success=(successful_reads > 0), node_count=len(self.nodes), duration=duration
        )

        # Check if connection is lost (all reads failed)
        if successful_reads == 0 and failed_reads > 0:
            raise ConnectionError("All reads failed - connection may be lost")

        return changes

    def stop(self):
        """Stop monitoring."""
        self._running = False


class SubscriptionMonitor(ValueMonitor):
    """Subscription-based value monitor (default mode)."""

    def __init__(
        self,
        client: Client,
        nodes: list,
        stats: StatisticsCollector,
        max_nodes_per_subscription: int = 1000,
        verbose: bool = False,
    ):
        """
        Initialize subscription monitor.

        Args:
            client: Connected OPC UA client
            nodes: List of OPC UA nodes to monitor
            stats: Statistics collector instance
            max_nodes_per_subscription: Maximum nodes per subscription (helps with large node counts)
            verbose: Enable verbose output for debugging subscription issues
        """
        super().__init__(client, nodes, stats)
        self._subscriptions = []  # List of (subscription, handles) tuples
        self._change_queue = queue.Queue()
        self._max_nodes_per_subscription = max_nodes_per_subscription
        self._verbose = verbose
        self._running = False

    def start(self):
        """Start subscription-based monitoring."""
        self._running = True

        # Create subscription handler (shared across all subscriptions)
        handler = self._SubscriptionHandler(self._change_queue, self.stats)

        # Subscribe to all nodes with progress reporting
        total_nodes = len(self.nodes)

        # Determine number of subscriptions needed
        num_subscriptions = (
            total_nodes + self._max_nodes_per_subscription - 1
        ) // self._max_nodes_per_subscription

        if num_subscriptions > 1:
            print(f"Subscribing to {total_nodes} nodes across {num_subscriptions} subscriptions...")
            print(f"  ({self._max_nodes_per_subscription} nodes per subscription)")
        else:
            print(f"Subscribing to {total_nodes} nodes...")

        # Large node counts take time - warn user
        if total_nodes > 10000:
            print(f"  [NOTE] Subscribing to {total_nodes} nodes may take several minutes.")

        # Time-based progress reporting (every 10 seconds)
        start_time = time.time()
        last_report_time = start_time
        report_interval = 10.0  # seconds

        total_subscribed = 0
        total_failed = 0

        # Chunk nodes into groups for multiple subscriptions
        for sub_idx in range(num_subscriptions):
            start_idx = sub_idx * self._max_nodes_per_subscription
            end_idx = min(start_idx + self._max_nodes_per_subscription, total_nodes)
            chunk = self.nodes[start_idx:end_idx]

            # Create subscription for this chunk
            subscription = self.client.create_subscription(500, handler)
            handles = []

            # Subscribe nodes in this chunk
            for node in chunk:
                if self._verbose:
                    print(
                        f"  [DEBUG] Subscribing to node {total_subscribed + total_failed + 1}/{total_nodes}: {node.nodeid}",
                        flush=True,
                    )

                try:
                    handle = subscription.subscribe_data_change(node)
                    handles.append(handle)
                    total_subscribed += 1
                except Exception as e:
                    total_failed += 1
                    self.stats.record_error(e)
                    # Show detailed error info
                    error_type = type(e).__name__
                    error_msg = str(e) if str(e) else repr(e)
                    print(
                        f"  [WARNING] Failed to subscribe to {node.nodeid}: {error_type}: {error_msg}"
                    )

                # Show progress every 10 seconds or at completion
                total_processed = total_subscribed + total_failed
                current_time = time.time()
                if (
                    current_time - last_report_time
                ) >= report_interval or total_processed == total_nodes:
                    elapsed = current_time - start_time
                    percent = (total_processed / total_nodes) * 100
                    rate = total_processed / elapsed if elapsed > 0 else 0
                    eta_seconds = (total_nodes - total_processed) / rate if rate > 0 else 0

                    if eta_seconds > 60:
                        eta_mins = int(eta_seconds // 60)
                        eta_secs = int(eta_seconds % 60)
                        eta_str = f", ETA: {eta_mins}m {eta_secs}s"
                    elif eta_seconds > 0:
                        eta_str = f", ETA: {int(eta_seconds)}s"
                    else:
                        eta_str = ""

                    rate_str = f"{rate:.1f} nodes/sec"
                    if total_failed > 0:
                        print(
                            f"  Progress: {total_processed}/{total_nodes} nodes ({percent:.1f}%) - {rate_str}{eta_str} - {total_subscribed} OK, {total_failed} failed",
                            flush=True,
                        )
                    else:
                        print(
                            f"  Progress: {total_processed}/{total_nodes} nodes ({percent:.1f}%) - {rate_str}{eta_str}",
                            flush=True,
                        )
                    last_report_time = current_time

            # Store subscription and its handles
            self._subscriptions.append((subscription, handles))

        if total_failed > 0:
            print(
                f"[OK] Subscribed to {total_subscribed} nodes across {num_subscriptions} subscription(s), {total_failed} failed"
            )
        else:
            print(
                f"[OK] Subscribed to {total_subscribed} nodes across {num_subscriptions} subscription(s)"
            )

    def get_changes(self) -> list[dict[str, Any]]:
        """
        Get accumulated changes from subscription notifications.

        Returns:
            List of changes since last call
        """
        if not self._running:
            return []

        changes = []

        # Drain the queue (non-blocking)
        try:
            while True:
                change = self._change_queue.get_nowait()
                changes.append(change)
        except queue.Empty:
            pass

        return changes

    def stop(self):
        """Stop all subscriptions and cleanup."""
        self._running = False

        for subscription, handles in self._subscriptions:
            try:
                # Unsubscribe all handles in this subscription
                for handle in handles:
                    try:
                        subscription.unsubscribe(handle)
                    except Exception:
                        pass

                # Delete subscription
                subscription.delete()
            except Exception as e:
                self.stats.record_error(e)

        self._subscriptions = []

    class _SubscriptionHandler:
        """Handler for OPC UA subscription notifications."""

        def __init__(self, change_queue: queue.Queue, stats: StatisticsCollector):
            """
            Initialize subscription handler.

            Args:
                change_queue: Thread-safe queue for buffering changes
                stats: Statistics collector instance
            """
            self.change_queue = change_queue
            self.stats = stats

        def datachange_notification(self, node, val, data):
            """
            Called when a subscribed value changes.

            Args:
                node: OPC UA node that changed
                val: New value
                data: Additional data from notification
            """
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                node_id = node.nodeid.to_string()
                browse_name = node.get_browse_name().Name

                change = {
                    "timestamp": timestamp,
                    "node_id": node_id,
                    "browse_name": browse_name,
                    "value": val,
                }

                self.change_queue.put(change)
                self.stats.record_datachange()

            except Exception as e:
                self.stats.record_error(e)

        def event_notification(self, event):
            """Called for event notifications (unused)."""
            pass
