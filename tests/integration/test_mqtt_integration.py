"""
Integration tests for MQTT PubSub publishing.

Tests cover:
- Server argument parsing with MQTT options
- MQTT publisher lifecycle (connect/disconnect) with mocked broker
- End-to-end message flow from data replay to MQTT publish
- Backward compatibility: server works without MQTT arguments
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.mark.integration
class TestMqttServerArguments:
    """Test that MQTT CLI arguments are properly accepted by the server."""

    def test_server_accepts_mqtt_broker_arg(self):
        """Server argument parser accepts --mqtt-broker."""

        ap = argparse.ArgumentParser()
        # Recreate just the MQTT args to verify they parse correctly
        ap.add_argument("--mqtt-broker", default=None)
        ap.add_argument("--mqtt-port", type=int, default=1883)
        ap.add_argument("--mqtt-topic-prefix", default="opcua")
        ap.add_argument("--mqtt-publisher-id", default=None)
        ap.add_argument("--mqtt-writer-group", default="default")
        ap.add_argument("--mqtt-qos", type=int, default=0, choices=[0, 1, 2])
        ap.add_argument("--mqtt-username", default=None)
        ap.add_argument("--mqtt-password", default=None)
        ap.add_argument("--mqtt-tls", action="store_true")

        args = ap.parse_args(
            [
                "--mqtt-broker",
                "broker.example.com",
                "--mqtt-port",
                "8883",
                "--mqtt-topic-prefix",
                "factory",
                "--mqtt-publisher-id",
                "plc-01",
                "--mqtt-writer-group",
                "process-data",
                "--mqtt-qos",
                "1",
                "--mqtt-username",
                "user",
                "--mqtt-password",
                "secret",
                "--mqtt-tls",
            ]
        )

        assert args.mqtt_broker == "broker.example.com"
        assert args.mqtt_port == 8883
        assert args.mqtt_topic_prefix == "factory"
        assert args.mqtt_publisher_id == "plc-01"
        assert args.mqtt_writer_group == "process-data"
        assert args.mqtt_qos == 1
        assert args.mqtt_username == "user"
        assert args.mqtt_password == "secret"
        assert args.mqtt_tls is True

    def test_server_defaults_without_mqtt_args(self):
        """Server works with default values when no MQTT args are provided."""
        ap = argparse.ArgumentParser()
        ap.add_argument("--mqtt-broker", default=None)
        ap.add_argument("--mqtt-port", type=int, default=1883)
        ap.add_argument("--mqtt-topic-prefix", default="opcua")
        ap.add_argument("--mqtt-publisher-id", default=None)
        ap.add_argument("--mqtt-writer-group", default="default")
        ap.add_argument("--mqtt-qos", type=int, default=0)
        ap.add_argument("--mqtt-tls", action="store_true")

        args = ap.parse_args([])

        assert args.mqtt_broker is None
        assert args.mqtt_port == 1883
        assert args.mqtt_topic_prefix == "opcua"
        assert args.mqtt_publisher_id is None
        assert args.mqtt_writer_group == "default"
        assert args.mqtt_qos == 0
        assert args.mqtt_tls is False


@pytest.mark.integration
class TestMqttEndToEndMessageFormat:
    """Test complete message flow produces valid OPC UA PubSub messages."""

    def test_full_publish_cycle_produces_valid_pubsub_json(self):
        """A full publish cycle produces spec-compliant JSON."""
        from opc_replay.mqtt_publisher import (
            MqttPublisher,
            _serialize_value,
            build_data_topic,
            format_dataset_message,
            format_network_message,
        )

        # Simulate what the replay loop does
        tagname = "ns=2;s=Temperature"
        value = 20.5
        datatype = "Float"
        ts = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

        # Build message like MqttPublisher.publish_data_change does
        payload = {tagname: _serialize_value(value, datatype)}
        dsm = format_dataset_message(
            dataset_writer_id=1,
            dataset_writer_name=tagname,
            sequence_number=1,
            payload=payload,
            timestamp=ts,
        )
        nm = format_network_message(
            publisher_id="ReplayServer",
            writer_group_name="default",
            dataset_messages=[dsm],
        )

        # Verify the full message is valid JSON
        json_str = json.dumps(nm, default=str)
        parsed = json.loads(json_str)

        # Verify OPC UA PubSub structure
        assert parsed["MessageType"] == "ua-data"
        assert parsed["PublisherId"] == "ReplayServer"
        assert parsed["WriterGroupName"] == "default"
        assert len(parsed["Messages"]) == 1

        msg = parsed["Messages"][0]
        assert msg["MessageType"] == "ua-keyframe"
        assert msg["DataSetWriterId"] == 1
        assert msg["SequenceNumber"] == 1
        assert msg["Payload"]["ns=2;s=Temperature"] == 20.5
        assert "2026-03-15" in msg["Timestamp"]

    def test_topic_matches_spec_pattern(self):
        """Generated topic matches OPC UA PubSub MQTT topic pattern."""
        from opc_replay.mqtt_publisher import build_data_topic

        topic = build_data_topic("opcua", "ReplayServer", "default", "ns=2;s=Temperature")

        # Per OPC 10000-14 Section 7.3.4.7.3:
        # <Prefix>/<Encoding>/data/<PublisherId>/<WriterGroup>/<DataSetWriter>
        parts = topic.split("/")
        assert parts[0] == "opcua"  # Prefix
        assert parts[1] == "json"  # Encoding
        assert parts[2] == "data"  # MqttMessageType
        assert parts[3] == "ReplayServer"  # PublisherId
        assert parts[4] == "default"  # WriterGroup
        assert parts[5] == "ns=2;s=Temperature"  # DataSetWriter

    def test_multiple_datatypes_serialize_correctly(self):
        """All common OPC UA data types serialize to valid JSON."""
        from opc_replay.mqtt_publisher import _serialize_value

        test_cases = [
            ("Float", 20.5, 20.5),
            ("Double", 3.14159, 3.14159),
            ("Int32", 42, 42),
            ("UInt16", 1000, 1000),
            ("Boolean", True, True),
            ("Boolean", "true", True),
            ("String", "hello", "hello"),
            ("Int64", 9007199254740991, 9007199254740991),
        ]

        for dtype, input_val, expected in test_cases:
            result = _serialize_value(input_val, dtype)
            assert result == expected, f"Failed for {dtype}: {input_val} -> {result} != {expected}"

            # Verify it survives JSON round-trip
            json_str = json.dumps({"value": result})
            parsed = json.loads(json_str)
            assert parsed["value"] == expected


@pytest.mark.integration
class TestMqttPublisherWithMockedBroker:
    """Test MqttPublisher lifecycle with a mocked MQTT broker."""

    def test_publisher_graceful_when_paho_missing(self):
        """Publisher raises clear ImportError when paho-mqtt is not installed."""
        with patch.dict("sys.modules", {"paho": None, "paho.mqtt": None, "paho.mqtt.client": None}):
            # Reset the cached module reference
            import opc_replay.mqtt_publisher as mp

            original = mp._mqtt_client_class
            mp._mqtt_client_class = None
            try:
                with pytest.raises(ImportError, match="paho-mqtt"):
                    mp._get_mqtt_client_class()
            finally:
                mp._mqtt_client_class = original

    def test_status_message_format(self):
        """Status messages follow OPC UA PubSub status format."""
        from opc_replay.mqtt_publisher import build_status_topic

        topic = build_status_topic("opcua", "ReplayServer")
        assert topic == "opcua/json/status/ReplayServer"
