"""Unit tests for client statistics collection."""

import time

import pytest

from opc_replay.client.statistics import StatisticsCollector


@pytest.mark.unit
def test_statistics_initialization():
    """Test StatisticsCollector initializes with zero values."""
    stats = StatisticsCollector()
    summary = stats.get_summary()

    assert summary["total_reads"] == 0
    assert summary["successful_reads"] == 0
    assert summary["failed_reads"] == 0
    assert summary["total_changes"] == 0
    assert summary["error_count"] == 0
    assert summary["datachange_count"] == 0
    assert summary["poll_count"] == 0


@pytest.mark.unit
def test_record_successful_read():
    """Test recording successful read operations."""
    stats = StatisticsCollector()
    stats.record_read(success=True, node_count=10, duration=0.5)

    summary = stats.get_summary()
    assert summary["total_reads"] == 10
    assert summary["successful_reads"] == 10
    assert summary["failed_reads"] == 0
    assert summary["poll_count"] == 1


@pytest.mark.unit
def test_record_failed_read():
    """Test recording failed read operations."""
    stats = StatisticsCollector()
    stats.record_read(success=False, node_count=10, duration=0.5)

    summary = stats.get_summary()
    assert summary["total_reads"] == 10
    assert summary["successful_reads"] == 0
    assert summary["failed_reads"] == 10
    assert summary["poll_count"] == 1


@pytest.mark.unit
def test_record_mixed_reads():
    """Test recording mix of successful and failed reads."""
    stats = StatisticsCollector()
    stats.record_read(success=True, node_count=10, duration=0.5)
    stats.record_read(success=False, node_count=5, duration=0.3)
    stats.record_read(success=True, node_count=15, duration=0.7)

    summary = stats.get_summary()
    assert summary["total_reads"] == 30
    assert summary["successful_reads"] == 25
    assert summary["failed_reads"] == 5
    assert summary["poll_count"] == 3


@pytest.mark.unit
def test_record_change():
    """Test recording value changes."""
    stats = StatisticsCollector()
    stats.record_change("ns=2;s=Tag1")
    stats.record_change("ns=2;s=Tag2")
    stats.record_change("ns=2;s=Tag3")

    summary = stats.get_summary()
    assert summary["total_changes"] == 3


@pytest.mark.unit
def test_record_datachange():
    """Test recording subscription datachange notifications."""
    stats = StatisticsCollector()
    stats.record_datachange()
    stats.record_datachange()

    summary = stats.get_summary()
    assert summary["datachange_count"] == 2
    assert summary["total_changes"] == 2


@pytest.mark.unit
def test_record_error():
    """Test recording errors."""
    stats = StatisticsCollector()
    error = Exception("Test error")
    stats.record_error(error)

    summary = stats.get_summary()
    assert summary["error_count"] == 1
    assert summary["last_error"] == "Test error"
    assert summary["last_error_time"] is not None


@pytest.mark.unit
def test_multiple_errors():
    """Test recording multiple errors."""
    stats = StatisticsCollector()
    stats.record_error(Exception("Error 1"))
    time.sleep(0.01)
    stats.record_error(Exception("Error 2"))

    summary = stats.get_summary()
    assert summary["error_count"] == 2
    assert summary["last_error"] == "Error 2"


@pytest.mark.unit
def test_read_success_rate():
    """Test read success rate calculation."""
    stats = StatisticsCollector()
    stats.record_read(success=True, node_count=80, duration=0.5)
    stats.record_read(success=False, node_count=20, duration=0.2)

    summary = stats.get_summary()
    assert summary["read_success_rate"] == 80.0


@pytest.mark.unit
def test_read_success_rate_zero_reads():
    """Test read success rate with zero reads."""
    stats = StatisticsCollector()
    summary = stats.get_summary()
    assert summary["read_success_rate"] == 0.0


@pytest.mark.unit
def test_avg_poll_duration():
    """Test average poll duration calculation."""
    stats = StatisticsCollector()
    stats.record_read(success=True, node_count=10, duration=0.4)
    stats.record_read(success=True, node_count=10, duration=0.6)
    stats.record_read(success=True, node_count=10, duration=0.5)

    summary = stats.get_summary()
    assert summary["avg_poll_duration"] == 0.5


@pytest.mark.unit
def test_uptime_tracking():
    """Test uptime tracking."""
    stats = StatisticsCollector()
    time.sleep(0.1)
    summary = stats.get_summary()

    assert summary["uptime_seconds"] >= 0.1
    assert "uptime_formatted" in summary


@pytest.mark.unit
def test_format_duration_seconds():
    """Test duration formatting for seconds only."""
    formatted = StatisticsCollector._format_duration(45)
    assert formatted == "45s"


@pytest.mark.unit
def test_format_duration_minutes():
    """Test duration formatting with minutes."""
    formatted = StatisticsCollector._format_duration(125)
    assert formatted == "2m 5s"


@pytest.mark.unit
def test_format_duration_hours():
    """Test duration formatting with hours."""
    formatted = StatisticsCollector._format_duration(3725)
    assert formatted == "1h 2m 5s"


@pytest.mark.unit
def test_changes_per_second():
    """Test changes per second calculation."""
    stats = StatisticsCollector()
    time.sleep(0.1)
    stats.record_change("ns=2;s=Tag1")
    stats.record_change("ns=2;s=Tag2")

    summary = stats.get_summary()
    assert summary["changes_per_second"] > 0


@pytest.mark.unit
def test_errors_per_minute():
    """Test errors per minute calculation."""
    stats = StatisticsCollector()
    time.sleep(0.1)
    stats.record_error(Exception("Error 1"))
    stats.record_error(Exception("Error 2"))

    summary = stats.get_summary()
    assert summary["errors_per_minute"] > 0


@pytest.mark.unit
def test_reset():
    """Test resetting statistics."""
    stats = StatisticsCollector()
    stats.record_read(success=True, node_count=10, duration=0.5)
    stats.record_change("ns=2;s=Tag1")
    stats.record_error(Exception("Error"))

    stats.reset()

    summary = stats.get_summary()
    assert summary["total_reads"] == 0
    assert summary["successful_reads"] == 0
    assert summary["failed_reads"] == 0
    assert summary["total_changes"] == 0
    assert summary["error_count"] == 0
    assert summary["last_error"] is None
    assert summary["poll_count"] == 0
