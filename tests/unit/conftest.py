"""
Shared pytest fixtures for opc-replay testing.

Provides mocked OPC UA objects, sample data, and temporary file fixtures.
"""

import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest


@pytest.fixture
def sample_dataframe():
    """
    Create a sample DataFrame matching expected CSV structure.
    Columns: TAGNAME, TAGVALUE, DATATYPE, TS
    """
    data = {
        "TAGNAME": [
            "ns=2;s=Temperature",
            "ns=2;s=Pressure",
            "ns=2;s=Flow",
            "ns=2;s=Status",
            "ns=2;s=Enabled",
        ],
        "TAGVALUE": ["20.5", "101.3", "15.2", "Running", "True"],
        "DATATYPE": ["Float", "Float", "Float", "String", "Boolean"],
        "TS": [
            "2026-01-01T10:00:00Z",
            "2026-01-01T10:00:01Z",
            "2026-01-01T10:00:02Z",
            "2026-01-01T10:00:03Z",
            "2026-01-01T10:00:04Z",
        ],
    }
    df = pd.DataFrame(data)
    df["TS"] = pd.to_datetime(df["TS"], utc=True)
    return df


@pytest.fixture
def sample_csv_content():
    """Raw CSV content for testing file loading."""
    return """TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:01Z
ns=2;s=Flow,15.2,Float,2026-01-01T10:00:02Z
ns=2;s=Status,Running,String,2026-01-01T10:00:03Z
ns=2;s=Enabled,true,Boolean,2026-01-01T10:00:04Z
"""


@pytest.fixture
def temp_csv_file(sample_csv_content, tmp_path):
    """Create a temporary CSV file with sample data."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(sample_csv_content)
    return csv_file


@pytest.fixture
def temp_parquet_file(sample_dataframe, tmp_path):
    """Create a temporary Parquet file with sample data."""
    parquet_file = tmp_path / "test_data.parquet"
    sample_dataframe.to_parquet(parquet_file, index=False)
    return parquet_file


@pytest.fixture
def sample_nodeset_xml(tmp_path):
    """Create a minimal NodeSet XML for testing namespace mapping."""
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
  <NamespaceUris>
    <Uri>urn:example:namespace</Uri>
  </NamespaceUris>
  <UAObject NodeId="ns=1;i=5001" BrowseName="1:TestObject">
    <DisplayName>TestObject</DisplayName>
    <References>
      <Reference ReferenceType="HasComponent" IsForward="false">i=85</Reference>
    </References>
  </UAObject>
  <UAVariable NodeId="ns=1;s=Temperature" BrowseName="1:Temperature" DataType="Float">
    <DisplayName>Temperature</DisplayName>
    <References>
      <Reference ReferenceType="HasTypeDefinition">i=63</Reference>
    </References>
  </UAVariable>
</UANodeSet>
"""
    nodeset_file = tmp_path / "test_nodeset.xml"
    nodeset_file.write_text(xml_content)
    return nodeset_file


@pytest.fixture
def mock_opcua_node():
    """Create a mock OPC UA node with common operations."""
    node = Mock()
    node.get_value = Mock(return_value=42.0)
    node.set_value = Mock()
    node.get_browse_name = Mock(return_value=Mock(Name="Temperature"))
    node.get_display_name = Mock(return_value=Mock(Text="Temperature"))
    node.get_node_class = Mock()
    node.get_children = Mock(return_value=[])
    node.nodeid = Mock()
    node.nodeid.NamespaceIndex = 2
    node.nodeid.Identifier = "Temperature"
    return node


@pytest.fixture
def mock_opcua_server():
    """Create a mock OPC UA server with basic operations."""
    server = Mock()

    # Mock namespace operations
    server.get_namespace_array = Mock(
        return_value=["http://opcfoundation.org/UA/", "urn:example:namespace"]
    )
    server.register_namespace = Mock(return_value=2)

    # Mock node operations
    mock_node = Mock()
    mock_node.get_value = Mock(return_value=0.0)
    mock_node.set_value = Mock()
    server.get_node = Mock(return_value=mock_node)

    # Mock server lifecycle
    server.start = Mock()
    server.stop = Mock()

    # Mock import operations
    server.import_xml = Mock()

    return server


@pytest.fixture
def mock_time(mocker):
    """
    Mock time.time() for testing time-based overrides.
    Returns a function to advance time.
    """
    current_time = [1000000.0]  # Use list to allow mutation in closure

    def advance_time(seconds):
        current_time[0] += seconds

    mocker.patch("time.time", side_effect=lambda: current_time[0])
    return advance_time


@pytest.fixture
def override_store():
    """Create a fresh OverrideStore instance for testing."""
    from opc_replay.server import OverrideStore

    return OverrideStore()


@pytest.fixture
def sample_injection_data():
    """Sample data for HTTP injection API testing."""
    return {
        "tagname": "ns=2;s=Temperature",
        "value": 99.9,
        "duration_s": 30,
        "offset_s": 0,
    }


@pytest.fixture
def sample_batch_injection():
    """Sample batch injection data from JSON/CSV."""
    return [
        {
            "tagname": "ns=2;s=Temperature",
            "value": 99.9,
            "duration_s": 30,
            "offset_s": 0,
        },
        {
            "tagname": "ns=2;s=Pressure",
            "value": 200.5,
            "duration_s": 20,
            "offset_s": 10,
        },
    ]


@pytest.fixture
def mock_http_request():
    """Create a mock HTTP request for testing InjectionHandler."""
    request = Mock()
    request.makefile = Mock(side_effect=lambda mode: io.BytesIO())
    return request


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response writer."""
    return io.BytesIO()
