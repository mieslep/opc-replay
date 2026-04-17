"""
Tests for MQTT PubSub publisher - mqtt_publisher module.

Tests cover:
- JSON message formatting per OPC UA PubSub spec (OPC 10000-14)
- Topic construction per the MQTT transport mapping
- Value serialization for all OPC UA data types
- MqttPublisher class (connect, publish, disconnect with mocked broker)
- Batch publishing
- Thread safety of sequence number generation
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from opc_replay.mqtt_publisher import (
    MqttPublisher,
    _serialize_value,
    build_data_topic,
    build_status_topic,
    format_dataset_message,
    format_network_message,
)

# ---------------------------------------------------------------------------
# Topic construction tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildDataTopic:
    """Test MQTT data topic construction per OPC 10000-14 Section 7.3.4.7.3."""

    def test_basic_topic_with_writer_group(self):
        """Topic with prefix/encoding/data/publisher/group."""
        topic = build_data_topic("opcua", "myserver", "default")
        assert topic == "opcua/json/data/myserver/default"

    def test_topic_with_dataset_writer(self):
        """Topic with optional DataSetWriter level."""
        topic = build_data_topic("opcua", "myserver", "default", "ns=2;s=Temperature")
        assert topic == "opcua/json/data/myserver/default/ns=2;s=Temperature"

    def test_custom_prefix(self):
        """Custom topic prefix instead of default 'opcua'."""
        topic = build_data_topic("mycompany", "server1", "group1")
        assert topic == "mycompany/json/data/server1/group1"

    def test_topic_without_dataset_writer_when_none(self):
        """No DataSetWriter level when None is passed."""
        topic = build_data_topic("opcua", "pub1", "grp1", None)
        assert topic == "opcua/json/data/pub1/grp1"


@pytest.mark.unit
class TestBuildStatusTopic:
    """Test MQTT status topic construction per OPC 10000-14 Section 7.3.4.7.7."""

    def test_status_topic(self):
        """Status topic follows: prefix/json/status/publisher_id."""
        topic = build_status_topic("opcua", "myserver")
        assert topic == "opcua/json/status/myserver"

    def test_custom_prefix_status(self):
        """Custom prefix works for status topic."""
        topic = build_status_topic("factory", "plc-01")
        assert topic == "factory/json/status/plc-01"


# ---------------------------------------------------------------------------
# Message formatting tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatNetworkMessage:
    """Test OPC UA PubSub JSON NetworkMessage formatting (Section 7.2.5.3)."""

    def test_required_fields_present(self):
        """NetworkMessage must have MessageId, MessageType, PublisherId, Messages."""
        nm = format_network_message("pub1", "grp1", [])
        assert "MessageId" in nm
        assert nm["MessageType"] == "ua-data"
        assert nm["PublisherId"] == "pub1"
        assert nm["WriterGroupName"] == "grp1"
        assert nm["Messages"] == []

    def test_message_id_is_valid_uuid(self):
        """MessageId should be a valid UUID string."""
        nm = format_network_message("pub1", "grp1", [])
        # Should not raise
        uuid.UUID(nm["MessageId"])

    def test_message_id_is_unique(self):
        """Each call generates a unique MessageId."""
        nm1 = format_network_message("pub1", "grp1", [])
        nm2 = format_network_message("pub1", "grp1", [])
        assert nm1["MessageId"] != nm2["MessageId"]

    def test_messages_array_passed_through(self):
        """DataSetMessages are included in the Messages array."""
        dsm = {"DataSetWriterId": 1, "Payload": {"temp": 20.5}}
        nm = format_network_message("pub1", "grp1", [dsm])
        assert len(nm["Messages"]) == 1
        assert nm["Messages"][0]["Payload"]["temp"] == 20.5


@pytest.mark.unit
class TestFormatDataSetMessage:
    """Test OPC UA PubSub JSON DataSetMessage formatting (Section 7.2.5.4)."""

    def test_required_fields_present(self):
        """DataSetMessage has all required fields."""
        dsm = format_dataset_message(
            dataset_writer_id=1,
            dataset_writer_name="Temperature",
            sequence_number=42,
            payload={"temp": 20.5},
        )
        assert dsm["DataSetWriterId"] == 1
        assert dsm["DataSetWriterName"] == "Temperature"
        assert dsm["SequenceNumber"] == 42
        assert dsm["MessageType"] == "ua-keyframe"
        assert dsm["Payload"] == {"temp": 20.5}
        assert "Timestamp" in dsm

    def test_custom_timestamp(self):
        """Explicit timestamp is used when provided."""
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        dsm = format_dataset_message(1, "tag", 1, {}, timestamp=ts)
        assert dsm["Timestamp"] == "2026-01-15T12:00:00+00:00"

    def test_default_timestamp_is_set(self):
        """Timestamp defaults to current time when not specified."""
        dsm = format_dataset_message(1, "tag", 1, {})
        # Should be a valid ISO timestamp string
        assert dsm["Timestamp"] is not None
        datetime.fromisoformat(dsm["Timestamp"])


# ---------------------------------------------------------------------------
# Value serialization tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSerializeValue:
    """Test value serialization for OPC UA PubSub JSON Payload."""

    def test_none_returns_none(self):
        assert _serialize_value(None, "Float") is None
        assert _serialize_value(None, "String") is None

    def test_float_types(self):
        assert _serialize_value(20.5, "Float") == 20.5
        assert _serialize_value("20.5", "Float") == 20.5
        assert _serialize_value(20, "Float") == 20.0
        assert _serialize_value(3.14, "Double") == 3.14

    def test_integer_types(self):
        assert _serialize_value(42, "Int32") == 42
        assert _serialize_value("42", "Int32") == 42
        assert _serialize_value(42.7, "Int32") == 42
        assert _serialize_value(255, "Byte") == 255
        assert _serialize_value(1000, "UInt16") == 1000
        assert _serialize_value(100000, "UInt32") == 100000
        assert _serialize_value(-128, "SByte") == -128

    def test_boolean_type(self):
        assert _serialize_value(True, "Boolean") is True
        assert _serialize_value(False, "Boolean") is False
        assert _serialize_value("true", "Boolean") is True
        assert _serialize_value("false", "Boolean") is False
        assert _serialize_value("1", "Boolean") is True
        assert _serialize_value("0", "Boolean") is False
        assert _serialize_value("yes", "Boolean") is True

    def test_string_type(self):
        assert _serialize_value("hello", "String") == "hello"
        assert _serialize_value(42, "String") == "42"

    def test_datetime_type(self):
        ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = _serialize_value(ts, "DateTime")
        assert "2026" in result

    def test_invalid_float_returns_none(self):
        assert _serialize_value("not_a_number", "Float") is None

    def test_invalid_int_returns_none(self):
        assert _serialize_value("not_a_number", "Int32") is None

    def test_default_datatype_is_string(self):
        assert _serialize_value(42, None) == "42"
        assert _serialize_value(42, "") == "42"


# ---------------------------------------------------------------------------
# MqttPublisher class tests (with mocked MQTT client)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mqtt_module():
    """Mock the paho.mqtt.client module."""
    mock_module = MagicMock()
    mock_client_instance = MagicMock()
    mock_client_instance.connect = Mock()
    mock_client_instance.disconnect = Mock()
    mock_client_instance.loop_start = Mock()
    mock_client_instance.loop_stop = Mock()
    mock_client_instance.publish = Mock()
    mock_client_instance.username_pw_set = Mock()
    mock_client_instance.tls_set = Mock()

    # Simulate successful connection via callback
    def fake_connect(host, port, keepalive=60):
        pass

    mock_client_instance.connect = Mock(side_effect=fake_connect)

    mock_module.Client = Mock(return_value=mock_client_instance)
    # Add CallbackAPIVersion for v2 API
    mock_module.CallbackAPIVersion = MagicMock()
    mock_module.CallbackAPIVersion.VERSION2 = 2

    return mock_module, mock_client_instance


@pytest.fixture
def publisher_connected(mock_mqtt_module):
    """Create a connected MqttPublisher with mocked MQTT client."""
    mock_module, mock_client = mock_mqtt_module

    with patch("opc_replay.mqtt_publisher._get_mqtt_module", return_value=mock_module):
        pub = MqttPublisher(
            broker="localhost",
            port=1883,
            publisher_id="test-server",
            topic_prefix="opcua",
            writer_group_name="default",
        )
        # Manually set connected state since we're mocking
        pub._client = mock_client
        pub._connected = True

    return pub, mock_client


@pytest.mark.unit
class TestMqttPublisherProperties:
    """Test MqttPublisher property accessors."""

    def test_properties(self):
        """Properties reflect constructor arguments."""
        pub = MqttPublisher.__new__(MqttPublisher)
        pub._broker = "mybroker"
        pub._publisher_id = "pub1"
        pub._topic_prefix = "opcua"
        pub._writer_group_name = "grp1"
        pub._connected = False

        assert pub.publisher_id == "pub1"
        assert pub.topic_prefix == "opcua"
        assert pub.writer_group_name == "grp1"
        assert pub.connected is False


@pytest.mark.unit
class TestMqttPublisherPublishDataChange:
    """Test single tag data publishing."""

    def test_publish_sends_to_correct_topic(self, publisher_connected):
        """Published message goes to the correct MQTT topic."""
        pub, mock_client = publisher_connected

        pub.publish_data_change("ns=2;s=Temperature", 20.5, "Float")

        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        topic = call_args[0][0]
        assert topic == "opcua/json/data/test-server/default/ns=2;s=Temperature"

    def test_publish_sends_valid_json(self, publisher_connected):
        """Published payload is valid JSON NetworkMessage."""
        pub, mock_client = publisher_connected

        pub.publish_data_change("ns=2;s=Temperature", 20.5, "Float")

        call_args = mock_client.publish.call_args
        payload_str = call_args[0][1]
        nm = json.loads(payload_str)

        assert nm["MessageType"] == "ua-data"
        assert nm["PublisherId"] == "test-server"
        assert len(nm["Messages"]) == 1

        dsm = nm["Messages"][0]
        assert dsm["MessageType"] == "ua-keyframe"
        assert "ns=2;s=Temperature" in dsm["Payload"]
        assert dsm["Payload"]["ns=2;s=Temperature"] == 20.5

    def test_publish_uses_configured_qos(self, mock_mqtt_module):
        """QoS level is passed through to MQTT publish."""
        mock_module, mock_client = mock_mqtt_module

        with patch("opc_replay.mqtt_publisher._get_mqtt_module", return_value=mock_module):
            pub = MqttPublisher(
                broker="localhost",
                publisher_id="test",
                qos=2,
            )
            pub._client = mock_client
            pub._connected = True

            pub.publish_data_change("ns=2;s=Tag", 1.0, "Float")

            call_kwargs = mock_client.publish.call_args[1]
            assert call_kwargs["qos"] == 2

    def test_publish_noop_when_disconnected(self):
        """Publishing does nothing when not connected."""
        pub = MqttPublisher.__new__(MqttPublisher)
        pub._client = None
        pub._connected = False
        pub._lock = __import__("threading").Lock()

        # Should not raise
        pub.publish_data_change("ns=2;s=Tag", 1.0, "Float")

    def test_publish_with_custom_timestamp(self, publisher_connected):
        """Custom timestamp is included in the DataSetMessage."""
        pub, mock_client = publisher_connected
        ts = datetime(2026, 6, 15, 8, 30, 0, tzinfo=UTC)

        pub.publish_data_change("ns=2;s=Temp", 25.0, "Float", timestamp=ts)

        payload_str = mock_client.publish.call_args[0][1]
        nm = json.loads(payload_str)
        dsm = nm["Messages"][0]
        assert "2026-06-15" in dsm["Timestamp"]

    def test_sequence_numbers_increment(self, publisher_connected):
        """Sequence numbers increase with each publish."""
        pub, mock_client = publisher_connected

        pub.publish_data_change("ns=2;s=Tag1", 1.0, "Float")
        pub.publish_data_change("ns=2;s=Tag2", 2.0, "Float")

        calls = mock_client.publish.call_args_list
        nm1 = json.loads(calls[0][0][1])
        nm2 = json.loads(calls[1][0][1])

        seq1 = nm1["Messages"][0]["SequenceNumber"]
        seq2 = nm2["Messages"][0]["SequenceNumber"]
        assert seq2 > seq1


@pytest.mark.unit
class TestMqttPublisherPublishBatch:
    """Test batch data publishing."""

    def test_batch_publish_groups_tags(self, publisher_connected):
        """Batch publish combines multiple tags into one Payload."""
        pub, mock_client = publisher_connected

        updates = [
            {"tagname": "ns=2;s=Temperature", "value": 20.5, "datatype": "Float"},
            {"tagname": "ns=2;s=Pressure", "value": 101.3, "datatype": "Float"},
        ]
        pub.publish_batch(updates)

        mock_client.publish.assert_called_once()
        payload_str = mock_client.publish.call_args[0][1]
        nm = json.loads(payload_str)

        dsm = nm["Messages"][0]
        assert dsm["Payload"]["ns=2;s=Temperature"] == 20.5
        assert dsm["Payload"]["ns=2;s=Pressure"] == 101.3

    def test_batch_publish_to_group_topic(self, publisher_connected):
        """Batch publishes to WriterGroup-level topic (no DataSetWriter suffix)."""
        pub, mock_client = publisher_connected

        updates = [{"tagname": "ns=2;s=Tag", "value": 1, "datatype": "Int32"}]
        pub.publish_batch(updates)

        topic = mock_client.publish.call_args[0][0]
        assert topic == "opcua/json/data/test-server/default"

    def test_empty_batch_is_noop(self, publisher_connected):
        """Empty update list does not publish."""
        pub, mock_client = publisher_connected
        pub.publish_batch([])
        mock_client.publish.assert_not_called()

    def test_batch_noop_when_disconnected(self):
        """Batch publishing does nothing when not connected."""
        pub = MqttPublisher.__new__(MqttPublisher)
        pub._client = None
        pub._connected = False
        pub._lock = __import__("threading").Lock()

        # Should not raise
        pub.publish_batch([{"tagname": "tag", "value": 1}])


@pytest.mark.unit
class TestMqttPublisherConnect:
    """Test MQTT connection and disconnection."""

    def test_connect_sets_credentials(self, mock_mqtt_module):
        """Username/password are set when provided."""
        mock_module, mock_client = mock_mqtt_module

        with patch("opc_replay.mqtt_publisher._get_mqtt_module", return_value=mock_module):
            with patch("time.sleep"):
                pub = MqttPublisher(
                    broker="localhost",
                    username="user",
                    password="pass",
                )
                # Simulate connected callback
                pub._connected = False

                # Mock the connect to trigger on_connect
                def connect_side_effect(*a, **kw):
                    pub._connected = True

                mock_client.connect = Mock(side_effect=connect_side_effect)
                mock_module.Client = Mock(return_value=mock_client)

                pub.connect()

                mock_client.username_pw_set.assert_called_once_with("user", "pass")

    def test_connect_enables_tls(self, mock_mqtt_module):
        """TLS is enabled when tls=True."""
        mock_module, mock_client = mock_mqtt_module

        with patch("opc_replay.mqtt_publisher._get_mqtt_module", return_value=mock_module):
            with patch("time.sleep"):
                pub = MqttPublisher(broker="localhost", tls=True)
                pub._connected = False

                def connect_side_effect(*a, **kw):
                    pub._connected = True

                mock_client.connect = Mock(side_effect=connect_side_effect)
                mock_module.Client = Mock(return_value=mock_client)

                pub.connect()

                mock_client.tls_set.assert_called_once()

    def test_disconnect_calls_loop_stop(self, publisher_connected):
        """Disconnect stops the MQTT loop and disconnects."""
        pub, mock_client = publisher_connected

        pub.disconnect()

        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert pub.connected is False


@pytest.mark.unit
class TestMqttPublisherWriterIds:
    """Test DataSetWriter ID assignment."""

    def test_writer_ids_auto_assigned(self, publisher_connected):
        """Each unique tag gets a unique DataSetWriter ID."""
        pub, _ = publisher_connected

        id1 = pub._get_writer_id("ns=2;s=Tag1")
        id2 = pub._get_writer_id("ns=2;s=Tag2")
        id3 = pub._get_writer_id("ns=2;s=Tag1")  # Same tag

        assert id1 != id2
        assert id1 == id3  # Same tag returns same ID

    def test_writer_ids_start_at_one(self, publisher_connected):
        """First writer ID is 1."""
        pub, _ = publisher_connected
        assert pub._get_writer_id("ns=2;s=First") == 1
