"""Statistics collection for OPC UA client monitoring."""

import threading
import time


class StatisticsCollector:
    """
    Collect and track metrics for OPC UA client monitoring.

    Tracks connection uptime, read operations, value changes, and errors.
    Thread-safe for concurrent access.
    """

    def __init__(self):
        """Initialize statistics collector."""
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Read statistics
        self._total_reads = 0
        self._successful_reads = 0
        self._failed_reads = 0

        # Change statistics
        self._total_changes = 0
        self._datachange_count = 0  # For subscription mode

        # Error tracking
        self._error_count = 0
        self._last_error: str | None = None
        self._last_error_time: float | None = None

        # Performance tracking
        self._total_read_duration = 0.0
        self._poll_count = 0

    def record_read(self, success: bool, node_count: int = 1, duration: float = 0.0):
        """
        Record a read operation.

        Args:
            success: Whether the read was successful
            node_count: Number of nodes read
            duration: Time taken for the read operation in seconds
        """
        with self._lock:
            self._total_reads += node_count
            if success:
                self._successful_reads += node_count
            else:
                self._failed_reads += node_count

            self._total_read_duration += duration
            if duration > 0:
                self._poll_count += 1

    def record_change(self, node_id: str):
        """
        Record a value change.

        Args:
            node_id: OPC UA node identifier
        """
        with self._lock:
            self._total_changes += 1

    def record_datachange(self):
        """Record a subscription datachange notification."""
        with self._lock:
            self._datachange_count += 1
            self._total_changes += 1

    def record_error(self, error: Exception):
        """
        Record an error.

        Args:
            error: Exception that occurred
        """
        with self._lock:
            self._error_count += 1
            self._last_error = str(error)
            self._last_error_time = time.time()

    def get_summary(self) -> dict:
        """
        Get summary of collected statistics.

        Returns:
            Dictionary with all statistics
        """
        with self._lock:
            now = time.time()
            uptime = now - self._start_time

            # Calculate rates
            read_success_rate = 0.0
            if self._total_reads > 0:
                read_success_rate = (self._successful_reads / self._total_reads) * 100

            avg_poll_duration = 0.0
            if self._poll_count > 0:
                avg_poll_duration = self._total_read_duration / self._poll_count

            changes_per_second = 0.0
            if uptime > 0:
                changes_per_second = self._total_changes / uptime

            errors_per_minute = 0.0
            if uptime > 0:
                errors_per_minute = (self._error_count / uptime) * 60

            return {
                "uptime_seconds": uptime,
                "uptime_formatted": self._format_duration(uptime),
                "total_reads": self._total_reads,
                "successful_reads": self._successful_reads,
                "failed_reads": self._failed_reads,
                "read_success_rate": read_success_rate,
                "total_changes": self._total_changes,
                "datachange_count": self._datachange_count,
                "error_count": self._error_count,
                "last_error": self._last_error,
                "last_error_time": self._last_error_time,
                "poll_count": self._poll_count,
                "avg_poll_duration": avg_poll_duration,
                "changes_per_second": changes_per_second,
                "errors_per_minute": errors_per_minute,
            }

    def reset(self):
        """Reset all statistics counters."""
        with self._lock:
            self._start_time = time.time()
            self._total_reads = 0
            self._successful_reads = 0
            self._failed_reads = 0
            self._total_changes = 0
            self._datachange_count = 0
            self._error_count = 0
            self._last_error = None
            self._last_error_time = None
            self._total_read_duration = 0.0
            self._poll_count = 0

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """
        Format duration in human-readable format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "1h 23m 45s"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
