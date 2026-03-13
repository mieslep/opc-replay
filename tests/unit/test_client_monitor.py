"""Unit tests for client monitoring classes."""

import queue
import time

import pytest

from opc_replay.client.monitor import PollingMonitor, SubscriptionMonitor
from opc_replay.client.statistics import StatisticsCollector


class MockNode:
    """Mock OPC UA node for testing."""

    def __init__(self, node_id, browse_name, initial_value):
        self.nodeid = MockNodeId(node_id)
        self._browse_name = MockBrowseName(browse_name)
        self._value = initial_value

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value

    def get_browse_name(self):
        return self._browse_name


class MockNodeId:
    """Mock NodeId."""

    def __init__(self, identifier):
        self.Identifier = identifier

    def to_string(self):
        return self.Identifier


class MockBrowseName:
    """Mock BrowseName."""

    def __init__(self, name):
        self.Name = name


class MockClient:
    """Mock OPC UA Client."""

    def __init__(self):
        self._subscription_handler = None
        self._subscribed_nodes = []

    def create_subscription(self, interval, handler):
        self._subscription_handler = handler
        return MockSubscription(self)

    def simulate_datachange(self, node, value):
        """Simulate a datachange notification."""
        if self._subscription_handler:
            self._subscription_handler.datachange_notification(node, value, None)


class MockSubscription:
    """Mock OPC UA Subscription."""

    def __init__(self, client):
        self.client = client
        self.handles = []
        self._next_handle = 1

    def subscribe_data_change(self, node):
        handle = self._next_handle
        self._next_handle += 1
        self.handles.append((handle, node))
        self.client._subscribed_nodes.append(node)
        return handle

    def unsubscribe(self, handle):
        self.handles = [(h, n) for h, n in self.handles if h != handle]

    def delete(self):
        self.handles = []


# PollingMonitor Tests


@pytest.mark.unit
def test_polling_monitor_initialization():
    """Test PollingMonitor initializes correctly."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=1.0)

    assert monitor.poll_interval == 1.0
    assert len(monitor.nodes) == 1


@pytest.mark.unit
def test_polling_monitor_start():
    """Test PollingMonitor start initializes previous values."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    node2 = MockNode("ns=2;s=Tag2", "Tag2", "test")
    nodes = [node1, node2]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()

    # Should have stored initial values
    assert "ns=2;s=Tag1" in monitor._prev_values
    assert "ns=2;s=Tag2" in monitor._prev_values
    assert monitor._prev_values["ns=2;s=Tag1"] == 42
    assert monitor._prev_values["ns=2;s=Tag2"] == "test"


@pytest.mark.unit
def test_polling_monitor_detects_changes():
    """Test PollingMonitor detects value changes."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()

    # Change value
    node1.set_value(99)

    # Get changes
    changes = monitor.get_changes()

    assert len(changes) == 1
    assert changes[0]["node_id"] == "ns=2;s=Tag1"
    assert changes[0]["browse_name"] == "Tag1"
    assert changes[0]["value"] == 99


@pytest.mark.unit
def test_polling_monitor_no_changes():
    """Test PollingMonitor returns empty list when no changes."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()

    # No changes
    changes = monitor.get_changes()

    assert len(changes) == 0


@pytest.mark.unit
def test_polling_monitor_multiple_changes():
    """Test PollingMonitor detects multiple changes."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    node2 = MockNode("ns=2;s=Tag2", "Tag2", "old")
    node3 = MockNode("ns=2;s=Tag3", "Tag3", 100)
    nodes = [node1, node2, node3]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()

    # Change two values
    node1.set_value(99)
    node2.set_value("new")

    changes = monitor.get_changes()

    assert len(changes) == 2
    change_ids = [c["node_id"] for c in changes]
    assert "ns=2;s=Tag1" in change_ids
    assert "ns=2;s=Tag2" in change_ids


@pytest.mark.unit
def test_polling_monitor_records_statistics():
    """Test PollingMonitor records read statistics."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()
    monitor.get_changes()

    summary = stats.get_summary()
    assert summary["total_reads"] == 1
    assert summary["successful_reads"] == 1
    assert summary["poll_count"] == 1


@pytest.mark.unit
def test_polling_monitor_records_changes():
    """Test PollingMonitor records change statistics."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.1)
    monitor.start()

    node1.set_value(99)
    monitor.get_changes()

    summary = stats.get_summary()
    assert summary["total_changes"] == 1


@pytest.mark.unit
def test_polling_monitor_stop():
    """Test PollingMonitor stop terminates monitoring."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats)
    monitor.start()
    monitor.stop()

    assert not monitor._running


@pytest.mark.unit
def test_polling_monitor_respects_poll_interval():
    """Test PollingMonitor respects poll interval."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = PollingMonitor(client, nodes, stats, poll_interval=0.2)
    monitor.start()

    # First poll
    start = time.time()
    monitor.get_changes()

    # Second poll should wait
    monitor.get_changes()
    elapsed = time.time() - start

    # Should have waited at least 0.2 seconds
    assert elapsed >= 0.2


# SubscriptionMonitor Tests


@pytest.mark.unit
def test_subscription_monitor_initialization():
    """Test SubscriptionMonitor initializes correctly."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)

    assert len(monitor.nodes) == 1
    assert len(monitor._subscriptions) == 0


@pytest.mark.unit
def test_subscription_monitor_start_creates_subscription():
    """Test SubscriptionMonitor start creates subscription."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    assert len(monitor._subscriptions) == 1
    subscription, handles = monitor._subscriptions[0]
    assert subscription is not None
    assert len(handles) == 1
    assert monitor._running


@pytest.mark.unit
def test_subscription_monitor_receives_datachange():
    """Test SubscriptionMonitor receives datachange notifications."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    # Simulate datachange
    client.simulate_datachange(node1, 99)

    # Get changes
    time.sleep(0.01)  # Allow queue to process
    changes = monitor.get_changes()

    assert len(changes) == 1
    assert changes[0]["node_id"] == "ns=2;s=Tag1"
    assert changes[0]["value"] == 99


@pytest.mark.unit
def test_subscription_monitor_multiple_datachanges():
    """Test SubscriptionMonitor handles multiple datachanges."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    node2 = MockNode("ns=2;s=Tag2", "Tag2", "old")
    nodes = [node1, node2]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    # Simulate multiple datachanges
    client.simulate_datachange(node1, 99)
    client.simulate_datachange(node2, "new")
    client.simulate_datachange(node1, 100)

    time.sleep(0.01)
    changes = monitor.get_changes()

    assert len(changes) == 3


@pytest.mark.unit
def test_subscription_monitor_records_datachange_stats():
    """Test SubscriptionMonitor records datachange statistics."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    # Simulate datachange
    client.simulate_datachange(node1, 99)
    time.sleep(0.01)

    summary = stats.get_summary()
    assert summary["datachange_count"] == 1
    assert summary["total_changes"] == 1


@pytest.mark.unit
def test_subscription_monitor_get_changes_drains_queue():
    """Test get_changes drains the entire queue."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    nodes = [node1]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    # Queue multiple changes
    for i in range(5):
        client.simulate_datachange(node1, i)

    time.sleep(0.01)
    changes = monitor.get_changes()

    assert len(changes) == 5

    # Second call should return empty
    changes2 = monitor.get_changes()
    assert len(changes2) == 0


@pytest.mark.unit
def test_subscription_monitor_stop_unsubscribes():
    """Test SubscriptionMonitor stop unsubscribes all nodes."""
    client = MockClient()
    node1 = MockNode("ns=2;s=Tag1", "Tag1", 42)
    node2 = MockNode("ns=2;s=Tag2", "Tag2", "test")
    nodes = [node1, node2]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()

    assert len(monitor._subscriptions) == 1
    subscription, handles = monitor._subscriptions[0]
    assert len(handles) == 2

    monitor.stop()

    assert len(monitor._subscriptions) == 0
    assert not monitor._running


@pytest.mark.unit
def test_subscription_monitor_empty_when_not_started():
    """Test get_changes returns empty when not started."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)

    # Not started
    changes = monitor.get_changes()

    assert len(changes) == 0


@pytest.mark.unit
def test_subscription_monitor_empty_after_stop():
    """Test get_changes returns empty after stop."""
    client = MockClient()
    nodes = [MockNode("ns=2;s=Tag1", "Tag1", 42)]
    stats = StatisticsCollector()

    monitor = SubscriptionMonitor(client, nodes, stats)
    monitor.start()
    monitor.stop()

    changes = monitor.get_changes()

    assert len(changes) == 0
