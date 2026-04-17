"""
OPC UA PubSub MQTT Publisher

Publishes OPC UA tag data to an MQTT broker following the OPC UA PubSub
specification (OPC 10000-14), using JSON message mapping over MQTT transport.

Implements the standard topic structure:
    <Prefix>/<Encoding>/data/<PublisherId>/<WriterGroup>[/<DataSetWriter>]

And the standard JSON NetworkMessage format with DataSetMessages containing
tag name-value pairs.

Commercial OPC UA servers (e.g., Kepware, Unified Automation, Prosys) use
this same PubSub/MQTT pattern to publish data to message brokers.

Usage:
    publisher = MqttPublisher(broker="localhost", port=1883, publisher_id="ReplayServer")
    publisher.connect()
    publisher.publish_data_change("ns=2;s=Temperature", 20.5, "Float", timestamp)
    publisher.disconnect()
"""

import json
import logging
import threading
import time
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Lazy import paho-mqtt to keep it optional
_mqtt_client_class = None


def _get_mqtt_client_class():
    """Lazy-load paho-mqtt Client class, raising ImportError with helpful message."""
    global _mqtt_client_class
    if _mqtt_client_class is None:
        try:
            import paho.mqtt.client as mqtt

            _mqtt_client_class = mqtt.Client
        except ImportError as err:
            raise ImportError(
                "paho-mqtt is required for MQTT publishing. "
                "Install it with: pip install paho-mqtt  (or: uv add paho-mqtt)"
            ) from err
    return _mqtt_client_class


def _get_mqtt_module():
    """Lazy-load the paho.mqtt.client module."""
    try:
        import paho.mqtt.client as mqtt

        return mqtt
    except ImportError as err:
        raise ImportError(
            "paho-mqtt is required for MQTT publishing. "
            "Install it with: pip install paho-mqtt  (or: uv add paho-mqtt)"
        ) from err


def format_network_message(
    publisher_id: str,
    writer_group_name: str,
    dataset_messages: list[dict],
) -> dict:
    """
    Build an OPC UA PubSub JSON NetworkMessage (MessageType "ua-data").

    Per OPC 10000-14, Section 7.2.5.3, a JSON NetworkMessage contains:
    - MessageId: globally unique identifier
    - MessageType: "ua-data"
    - PublisherId: unique publisher identifier
    - WriterGroupName: name of the WriterGroup
    - Messages: array of DataSetMessages

    Args:
        publisher_id: Unique identifier for this publisher
        writer_group_name: Name of the WriterGroup
        dataset_messages: List of DataSetMessage dicts

    Returns:
        JSON-serializable NetworkMessage dict
    """
    return {
        "MessageId": str(uuid.uuid4()),
        "MessageType": "ua-data",
        "PublisherId": publisher_id,
        "WriterGroupName": writer_group_name,
        "Messages": dataset_messages,
    }


def format_dataset_message(
    dataset_writer_id: int,
    dataset_writer_name: str,
    sequence_number: int,
    payload: dict,
    timestamp: datetime | None = None,
) -> dict:
    """
    Build an OPC UA PubSub JSON DataSetMessage.

    Per OPC 10000-14, Section 7.2.5.4, a DataSetMessage contains:
    - DataSetWriterId: identifier for the DataSetWriter
    - DataSetWriterName: name of the DataSetWriter
    - SequenceNumber: monotonically increasing counter
    - Timestamp: when the message was created
    - MessageType: "ua-keyframe" for full updates
    - Payload: object with name-value pairs

    Args:
        dataset_writer_id: Numeric ID for this DataSetWriter
        dataset_writer_name: Name of this DataSetWriter
        sequence_number: Monotonically increasing sequence number
        payload: Dict of field name -> value pairs
        timestamp: Message timestamp (defaults to now)

    Returns:
        JSON-serializable DataSetMessage dict
    """
    if timestamp is None:
        timestamp = datetime.now(UTC)

    return {
        "DataSetWriterId": dataset_writer_id,
        "DataSetWriterName": dataset_writer_name,
        "SequenceNumber": sequence_number,
        "Timestamp": timestamp.isoformat(),
        "MessageType": "ua-keyframe",
        "Payload": payload,
    }


def build_data_topic(
    prefix: str,
    publisher_id: str,
    writer_group_name: str,
    dataset_writer_name: str | None = None,
) -> str:
    """
    Build the MQTT topic for data messages per OPC 10000-14, Section 7.3.4.7.3.

    Topic pattern: <Prefix>/<Encoding>/data/<PublisherId>/<WriterGroup>[/<DataSetWriter>]

    Args:
        prefix: Topic prefix (default: "opcua")
        publisher_id: Publisher identifier
        writer_group_name: WriterGroup name
        dataset_writer_name: Optional DataSetWriter name

    Returns:
        MQTT topic string
    """
    topic = f"{prefix}/json/data/{publisher_id}/{writer_group_name}"
    if dataset_writer_name:
        topic = f"{topic}/{dataset_writer_name}"
    return topic


def build_status_topic(prefix: str, publisher_id: str) -> str:
    """
    Build the MQTT topic for status messages per OPC 10000-14, Section 7.3.4.7.7.

    Topic pattern: <Prefix>/<Encoding>/status/<PublisherId>

    Args:
        prefix: Topic prefix
        publisher_id: Publisher identifier

    Returns:
        MQTT topic string
    """
    return f"{prefix}/json/status/{publisher_id}"


class MqttPublisher:
    """
    OPC UA PubSub MQTT publisher.

    Publishes tag data changes to an MQTT broker using OPC UA PubSub JSON
    message format. Follows the standard topic hierarchy and message structure
    defined in OPC 10000-14.

    Thread-safe: publish methods can be called from multiple threads.
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        publisher_id: str = "opc-replay",
        topic_prefix: str = "opcua",
        writer_group_name: str = "default",
        qos: int = 0,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
    ):
        """
        Initialize the MQTT publisher.

        Args:
            broker: MQTT broker hostname or IP address
            port: MQTT broker port (default: 1883, TLS: 8883)
            publisher_id: Unique publisher ID (used in topics and messages)
            topic_prefix: MQTT topic prefix (default: "opcua" per OPC UA spec)
            writer_group_name: WriterGroup name for topic hierarchy
            qos: MQTT QoS level (0=AtMostOnce, 1=AtLeastOnce, 2=ExactlyOnce)
            username: Optional MQTT username
            password: Optional MQTT password
            tls: Enable TLS (use port 8883)
        """
        self._broker = broker
        self._port = port
        self._publisher_id = publisher_id
        self._topic_prefix = topic_prefix
        self._writer_group_name = writer_group_name
        self._qos = qos
        self._username = username
        self._password = password
        self._tls = tls

        self._client = None
        self._connected = False
        self._lock = threading.Lock()
        self._sequence_number = 0

        # Per-tag DataSetWriter IDs (auto-assigned)
        self._writer_ids: dict[str, int] = {}
        self._next_writer_id = 1

    @property
    def connected(self) -> bool:
        """Whether the MQTT client is currently connected."""
        return self._connected

    @property
    def publisher_id(self) -> str:
        """The publisher ID used in topics and messages."""
        return self._publisher_id

    @property
    def topic_prefix(self) -> str:
        """The MQTT topic prefix."""
        return self._topic_prefix

    @property
    def writer_group_name(self) -> str:
        """The WriterGroup name."""
        return self._writer_group_name

    def _get_writer_id(self, tagname: str) -> int:
        """Get or assign a DataSetWriter ID for a tag."""
        with self._lock:
            if tagname not in self._writer_ids:
                self._writer_ids[tagname] = self._next_writer_id
                self._next_writer_id += 1
            return self._writer_ids[tagname]

    def _next_sequence(self) -> int:
        """Get next sequence number (thread-safe)."""
        with self._lock:
            self._sequence_number += 1
            return self._sequence_number

    def connect(self) -> None:
        """
        Connect to the MQTT broker.

        Raises:
            ImportError: If paho-mqtt is not installed
            ConnectionError: If connection to broker fails
        """
        mqtt = _get_mqtt_module()

        # Create client with unique client ID
        client_id = f"opc-replay-{self._publisher_id}-{uuid.uuid4().hex[:8]}"

        # Support both paho-mqtt v1 and v2 API
        try:
            # paho-mqtt v2 uses CallbackAPIVersion
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
        except (AttributeError, TypeError):
            # paho-mqtt v1 fallback
            self._client = mqtt.Client(client_id=client_id)

        if self._username:
            self._client.username_pw_set(self._username, self._password)

        if self._tls:
            self._client.tls_set()

        # Set up callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(self._broker, self._port, keepalive=60)
            self._client.loop_start()
            # Wait briefly for connection to establish
            timeout = 5.0
            elapsed = 0.0
            while not self._connected and elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
            if not self._connected:
                self._client.loop_stop()
                raise ConnectionError(
                    f"Failed to connect to MQTT broker at {self._broker}:{self._port} "
                    f"within {timeout}s"
                )
        except ImportError:
            raise
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to MQTT broker at {self._broker}:{self._port}: {e}"
            ) from e

        logger.info(
            "[MQTT] Connected to %s:%d (publisher_id=%s)",
            self._broker,
            self._port,
            self._publisher_id,
        )

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client is not None:
            # Publish offline status before disconnecting
            try:
                self._publish_status("Error")
            except Exception:
                pass
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("[MQTT] Disconnected from %s:%d", self._broker, self._port)

    def _on_connect(self, *args) -> None:
        """Callback when connected to broker."""
        self._connected = True
        logger.debug("[MQTT] Connection established")
        # Publish online status
        try:
            self._publish_status("Operational")
        except Exception as e:
            logger.warning("[MQTT] Failed to publish status: %s", e)

    def _on_disconnect(self, *args) -> None:
        """Callback when disconnected from broker."""
        self._connected = False
        logger.debug("[MQTT] Connection lost")

    def _publish_status(self, status: str) -> None:
        """
        Publish a status message per OPC 10000-14, Section 7.3.4.7.7.

        Args:
            status: PubSub state ("Operational", "Error", "Disabled")
        """
        if self._client is None or not self._connected:
            return

        topic = build_status_topic(self._topic_prefix, self._publisher_id)
        now = datetime.now(UTC)
        message = {
            "MessageId": str(uuid.uuid4()),
            "MessageType": "ua-status",
            "PublisherId": self._publisher_id,
            "Timestamp": now.isoformat(),
            "IsCyclic": False,
            "Status": status,
        }
        payload = json.dumps(message, default=str)
        self._client.publish(topic, payload, qos=self._qos, retain=True)

    def publish_data_change(
        self,
        tagname: str,
        value,
        datatype: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Publish a single tag data change as an OPC UA PubSub DataSetMessage.

        Creates a NetworkMessage containing one DataSetMessage with the tag
        value in the Payload field.

        Args:
            tagname: OPC UA NodeId string (e.g., "ns=2;s=Temperature")
            value: Tag value
            datatype: OPC UA data type name (e.g., "Float", "Int32")
            timestamp: Source timestamp (defaults to now)
        """
        if self._client is None or not self._connected:
            return

        if timestamp is None:
            timestamp = datetime.now(UTC)

        writer_id = self._get_writer_id(tagname)
        seq = self._next_sequence()

        # Build DataSetMessage with the tag value in Payload
        # Per spec, Payload is a JSON object with name-value pairs
        payload = {tagname: _serialize_value(value, datatype)}

        dsm = format_dataset_message(
            dataset_writer_id=writer_id,
            dataset_writer_name=tagname,
            sequence_number=seq,
            payload=payload,
            timestamp=timestamp,
        )

        nm = format_network_message(
            publisher_id=self._publisher_id,
            writer_group_name=self._writer_group_name,
            dataset_messages=[dsm],
        )

        # Determine topic - per-tag DataSetWriter topic
        topic = build_data_topic(
            prefix=self._topic_prefix,
            publisher_id=self._publisher_id,
            writer_group_name=self._writer_group_name,
            dataset_writer_name=tagname,
        )

        json_payload = json.dumps(nm, default=str)
        self._client.publish(topic, json_payload, qos=self._qos)

    def publish_batch(
        self,
        updates: list[dict],
        timestamp: datetime | None = None,
    ) -> None:
        """
        Publish multiple tag updates as a single NetworkMessage.

        Groups all updates into one DataSetMessage for efficiency,
        published to the WriterGroup-level topic.

        Args:
            updates: List of dicts with keys: tagname, value, datatype
            timestamp: Common timestamp for all updates (defaults to now)
        """
        if self._client is None or not self._connected:
            return

        if not updates:
            return

        if timestamp is None:
            timestamp = datetime.now(UTC)

        seq = self._next_sequence()

        # Build combined Payload with all tag values
        payload = {}
        for update in updates:
            tagname = update["tagname"]
            value = update["value"]
            datatype = update.get("datatype", "String")
            payload[tagname] = _serialize_value(value, datatype)

        dsm = format_dataset_message(
            dataset_writer_id=0,  # Group-level message
            dataset_writer_name="batch",
            sequence_number=seq,
            payload=payload,
            timestamp=timestamp,
        )

        nm = format_network_message(
            publisher_id=self._publisher_id,
            writer_group_name=self._writer_group_name,
            dataset_messages=[dsm],
        )

        # Publish to WriterGroup-level topic (no DataSetWriter suffix)
        topic = build_data_topic(
            prefix=self._topic_prefix,
            publisher_id=self._publisher_id,
            writer_group_name=self._writer_group_name,
        )

        json_payload = json.dumps(nm, default=str)
        self._client.publish(topic, json_payload, qos=self._qos)


def _serialize_value(value: object, datatype: str | None) -> object:
    """
    Serialize a value for JSON encoding in OPC UA PubSub Payload.

    Per OPC 10000-14 VerboseEncoding (Section 7.2.5.4.2), simple scalar
    values are encoded directly (e.g., Int32 -> number, String -> string).

    Args:
        value: The value to serialize
        datatype: OPC UA data type name (e.g., "Float", "Int32", "Boolean")

    Returns:
        JSON-compatible Python value (float, int, bool, str, or None)
    """
    if value is None:
        return None

    datatype = (datatype or "String").strip()

    if datatype in ("Float", "Double"):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    if datatype in ("Int16", "UInt16", "Int32", "UInt32", "Int64", "UInt64", "SByte", "Byte"):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    if datatype == "Boolean":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        return s in ("1", "true", "t", "yes", "y")
    if datatype == "DateTime":
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    return str(value)
