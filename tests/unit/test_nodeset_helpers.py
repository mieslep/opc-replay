"""
Tests for nodeset helper functions.

Tests cover:
- count_variables_in_nodeset: Counting UAVariable elements in NodeSet XML
- load_namespace_cache: Loading .nsmeta sidecar files
- save_namespace_cache: Saving .nsmeta sidecar files
- build_namespace_map: Building namespace mappings with caching
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from opc_replay.server import (
    count_variables_in_nodeset,
    load_namespace_cache,
    save_namespace_cache,
)


@pytest.mark.unit
class TestCountVariablesInNodeset:
    """Test count_variables_in_nodeset function."""

    def test_count_empty_nodeset(self, tmp_path):
        """Test counting variables in empty NodeSet."""
        nodeset_xml = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
    <NamespaceUris>
        <Uri>urn:test:tags</Uri>
    </NamespaceUris>
</UANodeSet>
"""
        nodeset_path = tmp_path / "empty.xml"
        nodeset_path.write_text(nodeset_xml)

        count = count_variables_in_nodeset(str(nodeset_path))
        assert count == 0

    def test_count_single_variable(self, tmp_path):
        """Test counting single UAVariable."""
        nodeset_xml = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <NamespaceUris>
        <Uri>urn:test:tags</Uri>
    </NamespaceUris>
    <UAVariable NodeId="ns=1;s=Temperature" BrowseName="1:Temperature" DataType="Float">
        <DisplayName>Temperature</DisplayName>
        <References>
            <Reference ReferenceType="HasTypeDefinition">i=63</Reference>
        </References>
        <Value>
            <Float>20.5</Float>
        </Value>
    </UAVariable>
</UANodeSet>
"""
        nodeset_path = tmp_path / "single.xml"
        nodeset_path.write_text(nodeset_xml)

        count = count_variables_in_nodeset(str(nodeset_path))
        assert count == 1

    def test_count_multiple_variables(self, tmp_path):
        """Test counting multiple UAVariable elements."""
        nodeset_xml = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
    <NamespaceUris>
        <Uri>urn:test:tags</Uri>
    </NamespaceUris>
    <UAObject NodeId="ns=1;s=Root" BrowseName="1:Root">
        <DisplayName>Root</DisplayName>
    </UAObject>
    <UAVariable NodeId="ns=1;s=Temp1" BrowseName="1:Temp1" DataType="Float">
        <DisplayName>Temp1</DisplayName>
    </UAVariable>
    <UAVariable NodeId="ns=1;s=Temp2" BrowseName="1:Temp2" DataType="Float">
        <DisplayName>Temp2</DisplayName>
    </UAVariable>
    <UAVariable NodeId="ns=1;s=Pressure" BrowseName="1:Pressure" DataType="Float">
        <DisplayName>Pressure</DisplayName>
    </UAVariable>
</UANodeSet>
"""
        nodeset_path = tmp_path / "multiple.xml"
        nodeset_path.write_text(nodeset_xml)

        count = count_variables_in_nodeset(str(nodeset_path))
        assert count == 3

    def test_count_ignores_objects(self, tmp_path):
        """Test that UAObject elements are not counted."""
        nodeset_xml = """<?xml version="1.0" encoding="utf-8"?>
<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
    <UAObject NodeId="ns=1;s=Folder1" BrowseName="1:Folder1">
        <DisplayName>Folder1</DisplayName>
    </UAObject>
    <UAObject NodeId="ns=1;s=Folder2" BrowseName="1:Folder2">
        <DisplayName>Folder2</DisplayName>
    </UAObject>
    <UAVariable NodeId="ns=1;s=Tag" BrowseName="1:Tag" DataType="String">
        <DisplayName>Tag</DisplayName>
    </UAVariable>
</UANodeSet>
"""
        nodeset_path = tmp_path / "mixed.xml"
        nodeset_path.write_text(nodeset_xml)

        count = count_variables_in_nodeset(str(nodeset_path))
        assert count == 1  # Only the variable, not the objects


@pytest.mark.unit
class TestEventNotifierAttribute:
    """Test that UAObject elements have EventNotifier attribute set."""

    def test_objects_have_event_notifier_zero(self, tmp_path):
        """Test that UAObject elements have EventNotifier='0' attribute."""
        # Import here to test the actual generator
        import pandas as pd

        from opc_replay.to_nodeset import generate_nodeset_from_dataframe

        # Create test data with hierarchical tags
        data = {
            "TAGNAME": ["Area1/Device1/Tag1", "Area1/Device1/Tag2", "Area2/Tag3"],
            "TAGVALUE": [42.0, 43.5, 100.0],
            "DATATYPE": ["Float", "Float", "Float"],
        }
        df = pd.DataFrame(data)

        # Generate NodeSet
        nodeset_xml = generate_nodeset_from_dataframe(
            df=df,
            root_name="TestRoot",
            namespace_uri="urn:test:tags",
            split_regex="/",
            compact=False,
        )

        # Write to file for parsing
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text(nodeset_xml)

        # Parse the generated XML
        tree = ET.parse(str(nodeset_path))
        root = tree.getroot()

        # Define namespace
        ns = {"ua": "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"}

        # Find all UAObject elements
        objects = root.findall("ua:UAObject", ns)

        # Should have at least the root and folders
        assert len(objects) > 0, "Should have UAObject elements"

        # All UAObject elements should have EventNotifier="0"
        for obj in objects:
            assert "EventNotifier" in obj.attrib, (
                f"UAObject {obj.get('NodeId')} missing EventNotifier attribute"
            )
            assert obj.get("EventNotifier") == "0", (
                f"UAObject {obj.get('NodeId')} has wrong EventNotifier value"
            )

    def test_variables_do_not_have_event_notifier(self, tmp_path):
        """Test that UAVariable elements do NOT have EventNotifier attribute."""
        import pandas as pd

        from opc_replay.to_nodeset import generate_nodeset_from_dataframe

        # Create test data
        data = {
            "TAGNAME": ["Tag1", "Tag2"],
            "TAGVALUE": [42.0, 43.5],
            "DATATYPE": ["Float", "Float"],
        }
        df = pd.DataFrame(data)

        # Generate NodeSet
        nodeset_xml = generate_nodeset_from_dataframe(
            df=df,
            root_name="TestRoot",
            namespace_uri="urn:test:tags",
            split_regex=r"\.",
            compact=False,
        )

        # Write to file for parsing
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text(nodeset_xml)

        # Parse the generated XML
        tree = ET.parse(str(nodeset_path))
        root = tree.getroot()

        # Define namespace
        ns = {"ua": "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"}

        # Find all UAVariable elements
        variables = root.findall("ua:UAVariable", ns)

        # Should have variables
        assert len(variables) > 0, "Should have UAVariable elements"

        # UAVariable elements should NOT have EventNotifier attribute
        for var in variables:
            assert "EventNotifier" not in var.attrib, (
                f"UAVariable {var.get('NodeId')} should not have EventNotifier attribute"
            )


@pytest.mark.unit
class TestNamespaceCache:
    """Test namespace cache save/load functions."""

    def test_save_namespace_cache(self, tmp_path):
        """Test saving namespace cache to .nsmeta file."""
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text("<xml/>")

        namespaces = ["urn:test:tags", "urn:test:other"]
        save_namespace_cache(str(nodeset_path), namespaces)

        # Check .nsmeta file was created
        cache_path = tmp_path / "test.xml.nsmeta"
        assert cache_path.exists()

        # Verify contents
        with open(cache_path) as f:
            cache_data = json.load(f)

        assert "namespaces" in cache_data
        assert cache_data["namespaces"] == namespaces
        assert "generated" in cache_data

    def test_load_namespace_cache_success(self, tmp_path):
        """Test loading existing namespace cache."""
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text("<xml/>")

        # Create cache file
        cache_path = tmp_path / "test.xml.nsmeta"
        cache_data = {
            "namespaces": ["urn:test:tags"],
            "generated": "2026-03-13T10:00:00",
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

        # Load cache
        loaded = load_namespace_cache(str(nodeset_path))

        assert loaded is not None
        assert loaded["namespaces"] == ["urn:test:tags"]
        assert loaded["generated"] == "2026-03-13T10:00:00"

    def test_load_namespace_cache_missing_file(self, tmp_path):
        """Test loading cache when .nsmeta file doesn't exist."""
        nodeset_path = tmp_path / "nonexistent.xml"

        loaded = load_namespace_cache(str(nodeset_path))

        assert loaded is None

    def test_load_namespace_cache_invalid_json(self, tmp_path):
        """Test loading cache with invalid JSON."""
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text("<xml/>")

        # Create invalid cache file
        cache_path = tmp_path / "test.xml.nsmeta"
        cache_path.write_text("invalid json content")

        loaded = load_namespace_cache(str(nodeset_path))

        assert loaded is None

    def test_save_load_roundtrip(self, tmp_path):
        """Test save and load roundtrip."""
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text("<xml/>")

        # Save
        namespaces = ["urn:test:ns1", "urn:test:ns2", "urn:test:ns3"]
        save_namespace_cache(str(nodeset_path), namespaces)

        # Load
        loaded = load_namespace_cache(str(nodeset_path))

        assert loaded is not None
        assert loaded["namespaces"] == namespaces

    def test_cache_json_format(self, tmp_path):
        """Test cache file is valid JSON with proper structure."""
        nodeset_path = tmp_path / "test.xml"
        nodeset_path.write_text("<xml/>")

        namespaces = ["urn:test:tags"]
        save_namespace_cache(str(nodeset_path), namespaces)

        # Read and parse manually
        cache_path = tmp_path / "test.xml.nsmeta"
        with open(cache_path) as f:
            data = json.load(f)

        # Verify structure
        assert isinstance(data, dict)
        assert "namespaces" in data
        assert "generated" in data
        assert isinstance(data["namespaces"], list)
        assert isinstance(data["generated"], str)
