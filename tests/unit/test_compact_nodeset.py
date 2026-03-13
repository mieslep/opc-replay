"""
Tests for NodeSet XML generation compact mode.

Tests that compact mode (no pretty-printing) produces valid, smaller XML files
for large nodesets (>5000 tags).
"""

import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from opc_replay.to_nodeset import generate_nodeset_from_dataframe


@pytest.mark.unit
class TestCompactMode:
    """Test compact mode for NodeSet generation."""

    def test_compact_mode_auto_enabled_for_large_nodesets(self, tmp_path):
        """Test compact mode is automatically enabled for >5000 tags."""
        # Create dataframe with 5001 tags (just over threshold)
        tag_count = 5001
        df = pd.DataFrame(
            {
                "TAGNAME": [f"ns=1;s=Tag{i:05d}" for i in range(tag_count)],
                "DATATYPE": ["Float"] * tag_count,
                "TAGVALUE": [0.0] * tag_count,
            }
        )

        xml_content = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, no_folders=True
        )

        # Compact mode should have minimal whitespace
        # Check that there are no indentation spaces (pretty-printing adds "  ")
        lines = xml_content.split("\n")
        # In compact mode, most content is on fewer lines
        assert len(lines) < 100  # Compact mode has minimal newlines

    def test_compact_mode_explicit_true(self):
        """Test compact mode can be explicitly enabled."""
        df = pd.DataFrame(
            {
                "TAGNAME": ["ns=1;s=Tag1", "ns=1;s=Tag2"],
                "DATATYPE": ["Float", "Float"],
                "TAGVALUE": [1.0, 2.0],
            }
        )

        xml_content = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, no_folders=True, compact=True
        )

        # Should have minimal whitespace
        assert "  " not in xml_content  # No indentation spaces

    def test_compact_mode_explicit_false(self):
        """Test compact mode can be explicitly disabled (pretty-printing)."""
        df = pd.DataFrame(
            {
                "TAGNAME": ["ns=1;s=Tag1", "ns=1;s=Tag2"],
                "DATATYPE": ["Float", "Float"],
                "TAGVALUE": [1.0, 2.0],
            }
        )

        xml_content = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, no_folders=True, compact=False
        )

        # Should have pretty indentation
        assert "  " in xml_content  # Has indentation spaces

    def test_compact_mode_produces_valid_xml(self):
        """Test compact mode produces valid parseable XML."""
        df = pd.DataFrame(
            {
                "TAGNAME": ["ns=1;s=Tag1", "ns=1;s=Tag2", "ns=1;s=Tag3"],
                "DATATYPE": ["Float", "Int32", "String"],
                "TAGVALUE": [1.5, 42, "test"],
            }
        )

        xml_content = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, compact=True
        )

        # Should parse successfully
        root = ET.fromstring(xml_content)
        assert root is not None

        # Check for UAVariable elements
        ns = {"ua": "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"}
        variables = root.findall(".//ua:UAVariable", ns)
        assert len(variables) == 3

    def test_compact_mode_smaller_file_size(self):
        """Test compact mode produces smaller files than pretty mode."""
        df = pd.DataFrame(
            {
                "TAGNAME": [f"ns=1;s=Tag{i}" for i in range(100)],
                "DATATYPE": ["Float"] * 100,
                "TAGVALUE": [0.0] * 100,
            }
        )

        xml_compact = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, compact=True
        )

        xml_pretty = generate_nodeset_from_dataframe(
            df=df, root_name="TestSystem", namespace_index=1, compact=False
        )

        # Compact should be significantly smaller
        size_compact = len(xml_compact)
        size_pretty = len(xml_pretty)
        assert size_compact < size_pretty
        # Should save at least 10% (typically 12-15% for small nodesets, more for large ones)
        assert size_compact < size_pretty * 0.90

    def test_compact_threshold_5000_tags(self):
        """Test auto-detection threshold is exactly 5000 tags."""
        # 5000 tags should use pretty mode
        df_5000 = pd.DataFrame(
            {
                "TAGNAME": [f"ns=1;s=Tag{i}" for i in range(5000)],
                "DATATYPE": ["Float"] * 5000,
                "TAGVALUE": [0.0] * 5000,
            }
        )

        xml_5000 = generate_nodeset_from_dataframe(
            df=df_5000, root_name="TestSystem", namespace_index=1, no_folders=True
        )

        # Should have pretty-printing (has indentation)
        assert "  " in xml_5000

        # 5001 tags should use compact mode
        df_5001 = pd.DataFrame(
            {
                "TAGNAME": [f"ns=1;s=Tag{i}" for i in range(5001)],
                "DATATYPE": ["Float"] * 5001,
                "TAGVALUE": [0.0] * 5001,
            }
        )

        xml_5001 = generate_nodeset_from_dataframe(
            df=df_5001, root_name="TestSystem", namespace_index=1, no_folders=True
        )

        # Compact mode has very minimal newlines
        lines_5001 = xml_5001.split("\n")
        assert len(lines_5001) < 100  # Much fewer lines in compact mode
