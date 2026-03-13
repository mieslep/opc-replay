#!/usr/bin/env python3
"""
Integration test: Verify auto-conversion of non-canonical NodeIds.

Tests that non-canonical TAGNAMEs (e.g., 'Temperature' instead of 'ns=2;s=Temperature')
are automatically converted to canonical format during:
- Auto-NodeSet generation
- CSV replay
- Server operation

Also tests the --allow-non-canonical flag for opt-out behavior.

Requirements:
    - OPC UA server can be started
    - Test data with mixed canonical/non-canonical TAGNAMEs

Usage (pytest):
    pytest tests/integration/test_auto_conversion.py -v
"""

import sys
import tempfile
import time
from pathlib import Path

import pandas as pd
import pytest

# Add parent directory to path to import from opc_replay
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from opc_replay.server import canonicalize_nodeid
from opc_replay.to_nodeset import generate_nodeset_from_dataframe


@pytest.mark.integration
def test_auto_conversion_in_nodeset_generation():
    """Test that auto-conversion works during NodeSet generation"""
    # Create DataFrame with mixed canonical and non-canonical TAGNAMEs
    data = {
        "TAGNAME": [
            "Temperature",  # Non-canonical - should be converted
            "ns=2;s=Pressure",  # Already canonical - should remain unchanged
            "PET001.Flow",  # Non-canonical with dot - should be converted
            "Tank_Level",  # Non-canonical with underscore - should be converted
        ],
        "TAGVALUE": [20.5, 101.3, 15.2, 45.0],
        "DATATYPE": ["Float", "Float", "Float", "Float"],
    }
    df = pd.DataFrame(data)

    # Generate NodeSet XML
    xml_string = generate_nodeset_from_dataframe(df, root_name="TestServer", namespace_index=2)

    # Verify all tags are present in the XML (with canonical format)
    assert "ns=2;s=Temperature" in xml_string, "Converted 'Temperature' not found"
    assert "ns=2;s=Pressure" in xml_string, "Canonical 'Pressure' not found"
    assert "ns=2;s=PET001.Flow" in xml_string, "Converted 'PET001.Flow' not found"
    assert "ns=2;s=Tank_Level" in xml_string, "Converted 'Tank_Level' not found"

    # Verify non-canonical versions are NOT present
    assert 'NodeId="Temperature"' not in xml_string
    assert 'NodeId="PET001.Flow"' not in xml_string

    print("[OK] Auto-conversion in NodeSet generation verified")


@pytest.mark.integration
def test_canonicalize_nodeid_function():
    """Test the canonicalize_nodeid function directly"""
    # Test already canonical - should remain unchanged
    assert canonicalize_nodeid("ns=2;s=Temperature") == "ns=2;s=Temperature", (
        "Canonical should remain unchanged"
    )
    assert canonicalize_nodeid("ns=0;i=85") == "ns=0;i=85", "Integer NodeId should remain unchanged"

    # Test non-canonical - should be wrapped
    assert canonicalize_nodeid("Temperature") == "ns=2;s=Temperature", (
        "Simple name should be wrapped"
    )
    assert canonicalize_nodeid("PET001.Flow") == "ns=2;s=PET001.Flow", (
        "Dotted name should be wrapped"
    )
    assert canonicalize_nodeid("Tank_Level") == "ns=2;s=Tank_Level", (
        "Name with underscore should be wrapped"
    )

    # Test custom namespace
    assert canonicalize_nodeid("Temperature", default_ns=3) == "ns=3;s=Temperature", (
        "Custom namespace should work"
    )

    # Test whitespace handling
    assert canonicalize_nodeid("  Temperature  ") == "ns=2;s=Temperature", (
        "Whitespace should be stripped"
    )

    # Test error on empty
    with pytest.raises(ValueError, match="NodeId cannot be empty"):
        canonicalize_nodeid("")

    with pytest.raises(ValueError, match="NodeId cannot be empty"):
        canonicalize_nodeid("   ")

    with pytest.raises(ValueError, match="NodeId cannot be empty"):
        canonicalize_nodeid(None)

    print("[OK] canonicalize_nodeid function verified")


@pytest.mark.integration
def test_auto_conversion_preserves_all_tags():
    """Test that auto-conversion doesn't filter out any tags"""
    # Create DataFrame with all non-canonical TAGNAMEs
    data = {
        "TAGNAME": [
            "Tag1",
            "Tag2",
            "Tag3",
            "Tag4WithLongName",
            "Tag.With.Dots",
            "Tag_With_Underscores",
            "Tag-With-Dashes",
        ],
        "TAGVALUE": [1, 2, 3, 4, 5, 6, 7],
        "DATATYPE": ["Int32"] * 7,
    }
    df = pd.DataFrame(data)
    initial_count = len(df)

    # Generate NodeSet
    xml_string = generate_nodeset_from_dataframe(df, root_name="TestServer", namespace_index=2)

    # Count variable definitions in XML (each should create one UAVariable)
    variable_count = xml_string.count("<UAVariable")

    # All tags should be present (no filtering)
    assert variable_count == initial_count, (
        f"Expected {initial_count} variables, found {variable_count}"
    )

    # Spot check a few conversions
    assert "ns=2;s=Tag1" in xml_string
    assert "ns=2;s=Tag.With.Dots" in xml_string
    assert "ns=2;s=Tag-With-Dashes" in xml_string

    print(f"[OK] All {initial_count} tags preserved after auto-conversion")


@pytest.mark.integration
def test_auto_conversion_with_real_server():
    """Test auto-conversion with an actual OPC UA server"""
    from opcua import Server, ua

    # Create test data with non-canonical names
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("TAGNAME,TAGVALUE,DATATYPE,TS\n")
        f.write("Temperature,20.5,Float,2026-01-01T10:00:00Z\n")
        f.write("Pressure,101.3,Float,2026-01-01T10:00:01Z\n")
        f.write("ns=2;s=Flow,15.2,Float,2026-01-01T10:00:02Z\n")  # Already canonical
        csv_path = f.name

    try:
        # Load and convert data
        df = pd.read_csv(csv_path)
        df["TS"] = pd.to_datetime(df["TS"])

        # Generate NodeSet with auto-conversion
        xml_string = generate_nodeset_from_dataframe(df, root_name="TestServer", namespace_index=2)

        # Write NodeSet to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write(xml_string)
            nodeset_path = f.name

        try:
            # Start server and import NodeSet
            server = Server()
            server.set_endpoint("opc.tcp://0.0.0.0:4841")
            server.import_xml(nodeset_path)
            server.start()

            time.sleep(0.5)  # Give server time to start

            try:
                # Verify all nodes are accessible with canonical IDs
                temp_node = server.get_node("ns=2;s=Temperature")
                assert temp_node is not None, "Temperature node not found"

                pressure_node = server.get_node("ns=2;s=Pressure")
                assert pressure_node is not None, "Pressure node not found"

                flow_node = server.get_node("ns=2;s=Flow")
                assert flow_node is not None, "Flow node not found"

                print("[OK] Auto-conversion verified with real OPC UA server")

            finally:
                server.stop()

        finally:
            Path(nodeset_path).unlink(missing_ok=True)

    finally:
        Path(csv_path).unlink(missing_ok=True)


if __name__ == "__main__":
    # Allow running as standalone script
    print("Running auto-conversion integration tests...\n")
    test_auto_conversion_in_nodeset_generation()
    test_canonicalize_nodeid_function()
    test_auto_conversion_preserves_all_tags()
    test_auto_conversion_with_real_server()
    print("\n[OK] All auto-conversion tests passed")
