"""
Tests for NodeId handling functions - is_canonical_nodeid and remap_nodeid.

Tests cover:
- NodeId format validation
- Namespace index remapping
- Edge cases: malformed NodeIds, missing mappings
"""

import pytest
from opc_replay.server import is_canonical_nodeid, remap_nodeid


@pytest.mark.unit
class TestIsCanonicalNodeId:
    """Test is_canonical_nodeid function for NodeId validation."""

    def test_valid_string_nodeid(self):
        """Test valid string NodeIds are accepted."""
        assert is_canonical_nodeid("ns=2;s=Temperature") is True
        assert is_canonical_nodeid("ns=0;s=Server") is True
        assert is_canonical_nodeid("ns=10;s=Some.Long.Path.To.Tag") is True
        assert is_canonical_nodeid("ns=1;s=Tag_With_Underscore") is True
        assert is_canonical_nodeid("ns=1;s=Tag-With-Dash") is True

    def test_valid_integer_nodeid(self):
        """Test valid integer NodeIds are accepted."""
        assert is_canonical_nodeid("ns=0;i=85") is True
        assert is_canonical_nodeid("ns=1;i=1000") is True
        assert is_canonical_nodeid("ns=2;i=12345") is True

    def test_valid_guid_nodeid(self):
        """Test valid GUID NodeIds are accepted."""
        assert is_canonical_nodeid("ns=1;g=12345678-1234-1234-1234-123456789012") is True
        assert is_canonical_nodeid("ns=2;g=ABCDEF01-2345-6789-ABCD-EF0123456789") is True

    def test_valid_bytestring_nodeid(self):
        """Test valid bytestring NodeIds are accepted."""
        assert is_canonical_nodeid("ns=1;b=ABC123") is True
        assert is_canonical_nodeid("ns=2;b=Base64EncodedString") is True

    def test_invalid_nodeid_missing_ns(self):
        """Test NodeIds without namespace are rejected."""
        assert is_canonical_nodeid("s=Temperature") is False
        assert is_canonical_nodeid("i=85") is False

    def test_invalid_nodeid_missing_identifier_type(self):
        """Test NodeIds without identifier type are rejected."""
        assert is_canonical_nodeid("ns=2;Temperature") is False
        assert is_canonical_nodeid("ns=2;85") is False

    def test_invalid_nodeid_wrong_format(self):
        """Test malformed NodeIds are rejected."""
        assert is_canonical_nodeid("ns:2;s:Temperature") is False  # Wrong separator
        assert is_canonical_nodeid("namespace=2;s=Temperature") is False  # Wrong prefix
        assert is_canonical_nodeid("ns=two;s=Temperature") is False  # Non-numeric ns

    def test_invalid_nodeid_unknown_identifier_type(self):
        """Test NodeIds with unknown identifier types are rejected."""
        assert is_canonical_nodeid("ns=2;x=Temperature") is False
        assert is_canonical_nodeid("ns=2;t=12345") is False

    def test_invalid_nodeid_empty_identifier(self):
        """Test NodeIds with empty identifiers are rejected."""
        assert is_canonical_nodeid("ns=2;s=") is False
        assert is_canonical_nodeid("ns=2;i=") is False

    def test_none_and_empty_string(self):
        """Test None and empty string are rejected."""
        assert is_canonical_nodeid(None) is False
        assert is_canonical_nodeid("") is False
        assert is_canonical_nodeid("   ") is False

    def test_whitespace_handling(self):
        """Test NodeIds with extra whitespace."""
        # Leading/trailing whitespace should be stripped
        assert is_canonical_nodeid("  ns=2;s=Temperature  ") is True
        # Internal whitespace should be preserved
        assert is_canonical_nodeid("ns=2;s=My Tag") is True

    def test_multiple_namespace_digits(self):
        """Test NodeIds with multi-digit namespace indices."""
        assert is_canonical_nodeid("ns=999;s=Tag") is True
        assert is_canonical_nodeid("ns=12345;i=100") is True

    def test_special_characters_in_identifier(self):
        """Test NodeIds with special characters."""
        assert is_canonical_nodeid("ns=2;s=Tag.With.Dots") is True
        assert is_canonical_nodeid("ns=2;s=Tag_With_Underscores") is True
        assert is_canonical_nodeid("ns=2;s=Tag-With-Dashes") is True
        assert is_canonical_nodeid("ns=2;s=Tag/With/Slashes") is True
        assert is_canonical_nodeid("ns=2;s=Tag With Spaces") is True
        assert is_canonical_nodeid("ns=2;s=Tag:With:Colons") is True


@pytest.mark.unit
class TestRemapNodeId:
    """Test remap_nodeid function for namespace remapping."""

    def test_remap_basic_string_nodeid(self):
        """Test basic remapping of string NodeIds."""
        ns_map = {2: 3}
        result = remap_nodeid("ns=2;s=Temperature", ns_map)
        assert result == "ns=3;s=Temperature"

    def test_remap_integer_nodeid(self):
        """Test remapping integer NodeIds."""
        ns_map = {1: 5}
        result = remap_nodeid("ns=1;i=1000", ns_map)
        assert result == "ns=5;i=1000"

    def test_remap_guid_nodeid(self):
        """Test remapping GUID NodeIds."""
        ns_map = {2: 4}
        result = remap_nodeid("ns=2;g=12345678-1234-1234-1234-123456789012", ns_map)
        assert result == "ns=4;g=12345678-1234-1234-1234-123456789012"

    def test_remap_bytestring_nodeid(self):
        """Test remapping bytestring NodeIds."""
        ns_map = {1: 2}
        result = remap_nodeid("ns=1;b=ABC123", ns_map)
        assert result == "ns=2;b=ABC123"

    def test_remap_no_mapping_preserves_original(self):
        """Test that missing namespace mapping preserves original."""
        ns_map = {2: 3}
        result = remap_nodeid("ns=5;s=Temperature", ns_map)
        assert result == "ns=5;s=Temperature"

    def test_remap_empty_map_preserves_original(self):
        """Test that empty namespace map preserves original."""
        ns_map = {}
        result = remap_nodeid("ns=2;s=Temperature", ns_map)
        assert result == "ns=2;s=Temperature"

    def test_remap_identity_mapping(self):
        """Test remapping where namespace maps to itself."""
        ns_map = {2: 2}
        result = remap_nodeid("ns=2;s=Temperature", ns_map)
        assert result == "ns=2;s=Temperature"

    def test_remap_multiple_namespaces(self):
        """Test remapping with multiple namespace mappings."""
        ns_map = {1: 5, 2: 6, 3: 7}
        
        assert remap_nodeid("ns=1;s=Tag1", ns_map) == "ns=5;s=Tag1"
        assert remap_nodeid("ns=2;s=Tag2", ns_map) == "ns=6;s=Tag2"
        assert remap_nodeid("ns=3;s=Tag3", ns_map) == "ns=7;s=Tag3"

    def test_remap_namespace_zero(self):
        """Test remapping namespace 0 (standard OPC UA namespace)."""
        ns_map = {0: 0, 1: 2}
        result = remap_nodeid("ns=0;i=85", ns_map)
        assert result == "ns=0;i=85"

    def test_remap_large_namespace_indices(self):
        """Test remapping with large namespace indices."""
        ns_map = {999: 1000}
        result = remap_nodeid("ns=999;s=Tag", ns_map)
        assert result == "ns=1000;s=Tag"

    def test_remap_preserves_complex_identifiers(self):
        """Test that complex identifiers are preserved during remapping."""
        ns_map = {2: 3}
        
        # Complex string identifier
        result = remap_nodeid("ns=2;s=Root.Folder.SubFolder.Tag.Name", ns_map)
        assert result == "ns=3;s=Root.Folder.SubFolder.Tag.Name"
        
        # Identifier with special characters
        result = remap_nodeid("ns=2;s=Tag_With-Special.Chars/123", ns_map)
        assert result == "ns=3;s=Tag_With-Special.Chars/123"

    def test_remap_malformed_nodeid_returns_original(self):
        """Test that malformed NodeIds are returned unchanged."""
        ns_map = {2: 3}
        
        # Missing namespace
        assert remap_nodeid("s=Temperature", ns_map) == "s=Temperature"
        
        # Wrong format
        assert remap_nodeid("ns:2;s:Temperature", ns_map) == "ns:2;s:Temperature"
        
        # Missing identifier type
        assert remap_nodeid("ns=2;Temperature", ns_map) == "ns=2;Temperature"
        
        # Empty string
        assert remap_nodeid("", ns_map) == ""

    def test_remap_with_whitespace(self):
        """Test remapping handles NodeIds without expecting whitespace."""
        ns_map = {2: 3}
        result = remap_nodeid("ns=2;s=Temperature", ns_map)
        assert result == "ns=3;s=Temperature"
        
        # No internal whitespace should be added or removed
        result = remap_nodeid("ns=2;s=My Tag", ns_map)
        assert result == "ns=3;s=My Tag"


@pytest.mark.unit
class TestNodeIdEdgeCases:
    """Test edge cases for NodeId handling."""

    def test_is_canonical_very_long_identifier(self):
        """Test validation of very long identifiers."""
        long_id = "ns=2;s=" + "A" * 1000
        assert is_canonical_nodeid(long_id) is True

    def test_remap_very_long_identifier(self):
        """Test remapping preserves very long identifiers."""
        ns_map = {2: 3}
        long_id = "ns=2;s=" + "X" * 1000
        result = remap_nodeid(long_id, ns_map)
        expected = "ns=3;s=" + "X" * 1000
        assert result == expected

    def test_remap_with_unicode_characters(self):
        """Test remapping with Unicode characters in identifier."""
        ns_map = {2: 3}
        result = remap_nodeid("ns=2;s=Temperature_°C", ns_map)
        assert result == "ns=3;s=Temperature_°C"
        
        result = remap_nodeid("ns=2;s=中文标签", ns_map)
        assert result == "ns=3;s=中文标签"

    def test_is_canonical_with_unicode(self):
        """Test validation with Unicode characters."""
        assert is_canonical_nodeid("ns=2;s=Temperature_°C") is True
        assert is_canonical_nodeid("ns=2;s=中文标签") is True
        assert is_canonical_nodeid("ns=2;s=Ütf8_chärs") is True

    def test_remap_zero_namespace_to_nonzero(self):
        """Test remapping namespace 0 to another namespace (edge case)."""
        ns_map = {0: 5}
        result = remap_nodeid("ns=0;i=85", ns_map)
        assert result == "ns=5;i=85"

    def test_multiple_semicolons_in_identifier(self):
        """Test identifiers containing semicolons (edge case)."""
        # The identifier itself can contain semicolons after the first one
        assert is_canonical_nodeid("ns=2;s=Tag;With;Semicolons") is True
        
        ns_map = {2: 3}
        result = remap_nodeid("ns=2;s=Tag;With;Semicolons", ns_map)
        assert result == "ns=3;s=Tag;With;Semicolons"

    def test_remap_preserves_all_identifier_types(self):
        """Test all identifier types are preserved correctly."""
        ns_map = {1: 2}
        
        # String
        assert remap_nodeid("ns=1;s=Tag", ns_map) == "ns=2;s=Tag"
        
        # Integer
        assert remap_nodeid("ns=1;i=123", ns_map) == "ns=2;i=123"
        
        # GUID
        assert remap_nodeid("ns=1;g=00000000-0000-0000-0000-000000000000", ns_map) == "ns=2;g=00000000-0000-0000-0000-000000000000"
        
        # Bytestring
        assert remap_nodeid("ns=1;b=ABCD", ns_map) == "ns=2;b=ABCD"
