"""Output formatters for OPC UA client monitoring."""

import csv
import json
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class OutputFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format_header(self):
        """Print header/initialization output."""
        pass

    @abstractmethod
    def format_changes(self, changes: list[dict[str, Any]]):
        """
        Format and output value changes.

        Args:
            changes: List of change dicts with keys: timestamp, node_id, browse_name, value
        """
        pass

    @abstractmethod
    def format_summary(self, stats: dict[str, Any]):
        """
        Format and output summary statistics.

        Args:
            stats: Dictionary of statistics from StatisticsCollector.get_summary()
        """
        pass


class ConsoleFormatter(OutputFormatter):
    """Human-readable console output formatter."""

    def __init__(self, display_count: int = 25):
        """
        Initialize console formatter.

        Args:
            display_count: Maximum number of changes to display
        """
        self.display_count = display_count
        self._poll_num = 0

    def format_header(self):
        """Print column headers."""
        print(f"{'#':<4} {'Timestamp':<23} {'Browse Name':<50} {'Value':<30}")
        print(f"{'-' * 110}")

    def format_changes(self, changes: list[dict[str, Any]]):
        """Format changes as a human-readable table."""
        self._poll_num += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        print(f"\n{'=' * 110}")
        print(f"Poll #{self._poll_num} at {timestamp} - {len(changes)} tag(s) changed")
        print(f"{'=' * 110}")

        if changes:
            self.format_header()

            for i, item in enumerate(changes[: self.display_count], 1):
                value_str = str(item["value"])[:28]  # Truncate long values
                print(f"{i:<4} {item['timestamp']:<23} {item['browse_name']:<50} {value_str:<30}")

            if len(changes) > self.display_count:
                remaining = len(changes) - self.display_count
                print(f"\n... and {remaining} more changed tags (use --display-count to see more)")
        else:
            print("No changes detected")

    def format_summary(self, stats: dict[str, Any]):
        """Format summary statistics."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n{timestamp} - Summary:")
        print(f"  Uptime: {stats['uptime_formatted']}")
        print(f"  Total reads: {stats['total_reads']}")
        print(f"  Successful: {stats['successful_reads']}")
        print(f"  Failed: {stats['failed_reads']}")
        print(f"  Success rate: {stats['read_success_rate']:.1f}%")
        print(f"  Total changes: {stats['total_changes']}")
        print(f"  Datachange notifications: {stats['datachange_count']}")

        if stats["error_count"] > 0:
            print(f"  Errors: {stats['error_count']}")
            if stats["last_error"]:
                print(f"  Last error: {stats['last_error']}")

        if stats["poll_count"] > 0:
            print(f"  Avg poll duration: {stats['avg_poll_duration']:.2f}s")


class CSVFormatter(OutputFormatter):
    """CSV output formatter (writes to stdout)."""

    def __init__(self):
        """Initialize CSV formatter."""
        self._header_written = False

    def format_header(self):
        """Print CSV header."""
        if not self._header_written:
            writer = csv.writer(sys.stdout)
            writer.writerow(["timestamp", "node_id", "browse_name", "value"])
            sys.stdout.flush()
            self._header_written = True

    def format_changes(self, changes: list[dict[str, Any]]):
        """Format changes as CSV rows."""
        if not self._header_written:
            self.format_header()

        writer = csv.writer(sys.stdout)
        for change in changes:
            writer.writerow(
                [
                    change["timestamp"],
                    change["node_id"],
                    change["browse_name"],
                    str(change["value"]),
                ]
            )
        sys.stdout.flush()

    def format_summary(self, stats: dict[str, Any]):
        """Format summary as CSV row with summary type."""
        if not self._header_written:
            self.format_header()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                timestamp,
                "SUMMARY",
                f"reads={stats['total_reads']} changes={stats['total_changes']} errors={stats['error_count']}",
                stats["uptime_formatted"],
            ]
        )
        sys.stdout.flush()


class JSONFormatter(OutputFormatter):
    """Line-delimited JSON (JSONL) output formatter."""

    def format_header(self):
        """No header needed for JSONL."""
        pass

    def format_changes(self, changes: list[dict[str, Any]]):
        """Format changes as line-delimited JSON."""
        for change in changes:
            json.dump(change, sys.stdout)
            sys.stdout.write("\n")
        sys.stdout.flush()

    def format_summary(self, stats: dict[str, Any]):
        """Format summary as JSON object."""
        summary = {"type": "summary", "timestamp": datetime.now().isoformat(), "stats": stats}
        json.dump(summary, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


def create_formatter(format_name: str, **kwargs) -> OutputFormatter:
    """
    Factory function to create formatter instances.

    Args:
        format_name: One of "console", "csv", "json"
        **kwargs: Additional arguments passed to formatter constructor

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format_name is not recognized
    """
    formatters = {
        "console": ConsoleFormatter,
        "csv": CSVFormatter,
        "json": JSONFormatter,
    }

    formatter_class = formatters.get(format_name.lower())
    if formatter_class is None:
        raise ValueError(
            f"Unknown format: {format_name}. Valid formats: {', '.join(formatters.keys())}"
        )

    return formatter_class(**kwargs)
