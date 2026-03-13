"""Unit tests for client output formatters."""

import csv
import json
import sys
from io import StringIO

import pytest

from opc_replay.client.formatters import (
    ConsoleFormatter,
    CSVFormatter,
    JSONFormatter,
    create_formatter,
)


@pytest.mark.unit
def test_create_formatter_console():
    """Test factory creates ConsoleFormatter."""
    formatter = create_formatter("console")
    assert isinstance(formatter, ConsoleFormatter)


@pytest.mark.unit
def test_create_formatter_csv():
    """Test factory creates CSVFormatter."""
    formatter = create_formatter("csv")
    assert isinstance(formatter, CSVFormatter)


@pytest.mark.unit
def test_create_formatter_json():
    """Test factory creates JSONFormatter."""
    formatter = create_formatter("json")
    assert isinstance(formatter, JSONFormatter)


@pytest.mark.unit
def test_create_formatter_case_insensitive():
    """Test factory is case-insensitive."""
    formatter = create_formatter("CSV")
    assert isinstance(formatter, CSVFormatter)


@pytest.mark.unit
def test_create_formatter_invalid():
    """Test factory raises error for invalid format."""
    with pytest.raises(ValueError, match="Unknown format"):
        create_formatter("invalid")


@pytest.mark.unit
def test_create_formatter_with_display_count():
    """Test factory passes kwargs to formatter."""
    formatter = create_formatter("console", display_count=50)
    assert formatter.display_count == 50


@pytest.mark.unit
def test_console_formatter_changes(capsys):
    """Test ConsoleFormatter formats changes correctly."""
    formatter = ConsoleFormatter(display_count=5)
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": "ns=2;s=Tag1",
            "browse_name": "Tag1",
            "value": 42.5,
        },
        {
            "timestamp": "2026-03-13 15:37:17.456",
            "node_id": "ns=2;s=Tag2",
            "browse_name": "Tag2",
            "value": "test",
        },
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    assert "Poll #1" in captured.out
    assert "2 tag(s) changed" in captured.out
    assert "Tag1" in captured.out
    assert "Tag2" in captured.out
    assert "42.5" in captured.out


@pytest.mark.unit
def test_console_formatter_no_changes(capsys):
    """Test ConsoleFormatter handles no changes."""
    formatter = ConsoleFormatter()
    formatter.format_changes([])
    captured = capsys.readouterr()

    assert "No changes detected" in captured.out


@pytest.mark.unit
def test_console_formatter_truncates_long_values(capsys):
    """Test ConsoleFormatter truncates long values."""
    formatter = ConsoleFormatter()
    long_value = "x" * 100
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": "ns=2;s=Tag1",
            "browse_name": "Tag1",
            "value": long_value,
        }
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    # Value should be truncated to 28 chars
    assert long_value[:28] in captured.out
    assert long_value not in captured.out


@pytest.mark.unit
def test_console_formatter_display_count_limit(capsys):
    """Test ConsoleFormatter respects display_count limit."""
    formatter = ConsoleFormatter(display_count=2)
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": f"ns=2;s=Tag{i}",
            "browse_name": f"Tag{i}",
            "value": i,
        }
        for i in range(5)
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    assert "5 tag(s) changed" in captured.out
    assert "... and 3 more changed tags" in captured.out


@pytest.mark.unit
def test_console_formatter_summary(capsys):
    """Test ConsoleFormatter formats summary."""
    formatter = ConsoleFormatter()
    stats = {
        "uptime_formatted": "1h 23m 45s",
        "total_reads": 1000,
        "successful_reads": 950,
        "failed_reads": 50,
        "read_success_rate": 95.0,
        "total_changes": 123,
        "datachange_count": 123,
        "error_count": 0,
        "poll_count": 10,
        "avg_poll_duration": 0.42,
    }

    formatter.format_summary(stats)
    captured = capsys.readouterr()

    assert "Summary:" in captured.out
    assert "1h 23m 45s" in captured.out
    assert "1000" in captured.out
    assert "95.0%" in captured.out


@pytest.mark.unit
def test_csv_formatter_header(capsys):
    """Test CSVFormatter outputs correct header."""
    formatter = CSVFormatter()
    formatter.format_header()
    captured = capsys.readouterr()

    assert captured.out.strip() == "timestamp,node_id,browse_name,value"


@pytest.mark.unit
def test_csv_formatter_changes(capsys):
    """Test CSVFormatter outputs changes as CSV."""
    formatter = CSVFormatter()
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": "ns=2;s=Tag1",
            "browse_name": "Tag1",
            "value": 42.5,
        },
        {
            "timestamp": "2026-03-13 15:37:17.456",
            "node_id": "ns=2;s=Tag2",
            "browse_name": "Tag2",
            "value": "test",
        },
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    lines = captured.out.strip().split("\n")
    assert len(lines) == 3  # Header + 2 data rows
    assert lines[0].strip() == "timestamp,node_id,browse_name,value"
    assert "Tag1" in lines[1]
    assert "Tag2" in lines[2]


@pytest.mark.unit
def test_csv_formatter_escapes_special_chars(capsys):
    """Test CSVFormatter escapes commas and quotes."""
    formatter = CSVFormatter()
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": "ns=2;s=Tag1",
            "browse_name": "Tag1",
            "value": "value,with,commas",
        }
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    # Should be properly quoted
    assert '"value,with,commas"' in captured.out


@pytest.mark.unit
def test_csv_formatter_summary(capsys):
    """Test CSVFormatter outputs summary as CSV."""
    formatter = CSVFormatter()
    stats = {
        "total_reads": 1000,
        "total_changes": 123,
        "error_count": 5,
        "uptime_formatted": "1h 23m",
    }

    formatter.format_summary(stats)
    captured = capsys.readouterr()

    lines = captured.out.strip().split("\n")
    # Should have header + summary row
    assert "SUMMARY" in captured.out
    assert "reads=1000" in captured.out


@pytest.mark.unit
def test_json_formatter_changes(capsys):
    """Test JSONFormatter outputs line-delimited JSON."""
    formatter = JSONFormatter()
    changes = [
        {
            "timestamp": "2026-03-13 15:37:16.123",
            "node_id": "ns=2;s=Tag1",
            "browse_name": "Tag1",
            "value": 42.5,
        },
        {
            "timestamp": "2026-03-13 15:37:17.456",
            "node_id": "ns=2;s=Tag2",
            "browse_name": "Tag2",
            "value": "test",
        },
    ]

    formatter.format_changes(changes)
    captured = capsys.readouterr()

    lines = captured.out.strip().split("\n")
    assert len(lines) == 2

    # Each line should be valid JSON
    obj1 = json.loads(lines[0])
    obj2 = json.loads(lines[1])
    assert obj1["browse_name"] == "Tag1"
    assert obj2["browse_name"] == "Tag2"
    assert obj1["value"] == 42.5


@pytest.mark.unit
def test_json_formatter_summary(capsys):
    """Test JSONFormatter outputs summary as JSON."""
    formatter = JSONFormatter()
    stats = {
        "uptime_formatted": "1h 23m 45s",
        "total_reads": 1000,
        "total_changes": 123,
    }

    formatter.format_summary(stats)
    captured = capsys.readouterr()

    obj = json.loads(captured.out.strip())
    assert obj["type"] == "summary"
    assert "timestamp" in obj
    assert obj["stats"]["total_reads"] == 1000


@pytest.mark.unit
def test_json_formatter_header_does_nothing(capsys):
    """Test JSONFormatter header does nothing."""
    formatter = JSONFormatter()
    formatter.format_header()
    captured = capsys.readouterr()

    assert captured.out == ""
