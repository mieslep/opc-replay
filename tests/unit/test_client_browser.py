"""Unit tests for client node browsing."""

import pytest

from opc_replay.client.browser import NodeBrowser


class MockNode:
    """Mock OPC UA node for testing."""

    def __init__(self, node_id, ns_idx, name, node_class="Variable", children=None):
        self.nodeid = MockNodeId(node_id, ns_idx)
        self.name = name
        self._node_class = node_class
        self._children = children or []
        self._browse_name = MockBrowseName(name)
        self._data_type = "Int32"

    def get_children(self):
        return self._children

    def get_node_class(self):
        return MockNodeClass(self._node_class)

    def get_browse_name(self):
        return self._browse_name

    def get_data_type_as_variant_type(self):
        return MockVariantType(self._data_type)


class MockNodeId:
    """Mock NodeId."""

    def __init__(self, identifier, ns_idx):
        self.Identifier = identifier
        self.NamespaceIndex = ns_idx

    def to_string(self):
        return f"ns={self.NamespaceIndex};s={self.Identifier}"


class MockNodeClass:
    """Mock NodeClass enum."""

    def __init__(self, name):
        self.name = name


class MockBrowseName:
    """Mock BrowseName."""

    def __init__(self, name):
        self.Name = name


class MockVariantType:
    """Mock VariantType."""

    def __init__(self, type_name):
        self._type = type_name

    def __str__(self):
        return f"VariantType.{self._type}"


class MockClient:
    """Mock OPC UA Client."""

    def __init__(self, root_node):
        self._root = root_node

    def get_objects_node(self):
        return self._root


@pytest.mark.unit
def test_browse_namespace_finds_variables():
    """Test browsing specific namespace finds variables."""
    # Create mock tree: Root -> Folder1 -> Tag1, Tag2
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    tag2 = MockNode("Tag2", 2, "Tag2", "Variable")
    folder1 = MockNode("Folder1", 2, "Folder1", "Object", [tag1, tag2])
    root = MockNode("Root", 0, "Root", "Object", [folder1])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    variables = browser.browse_namespace(2)

    assert len(variables) == 2
    assert variables[0].name == "Tag1"
    assert variables[1].name == "Tag2"


@pytest.mark.unit
def test_browse_namespace_filters_by_namespace():
    """Test browsing filters to target namespace only."""
    # Create tags in different namespaces
    tag1_ns2 = MockNode("Tag1", 2, "Tag1", "Variable")
    tag2_ns3 = MockNode("Tag2", 3, "Tag2", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag1_ns2, tag2_ns3])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom", "urn:other"]
    browser = NodeBrowser(client, namespaces)

    variables = browser.browse_namespace(2)

    assert len(variables) == 1
    assert variables[0].nodeid.NamespaceIndex == 2


@pytest.mark.unit
def test_browse_namespace_ignores_objects():
    """Test browsing skips Object nodes (not Variables)."""
    folder1 = MockNode("Folder1", 2, "Folder1", "Object")
    folder2 = MockNode("Folder2", 2, "Folder2", "Object")
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [folder1, folder2, tag1])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    variables = browser.browse_namespace(2)

    assert len(variables) == 1
    assert variables[0].name == "Tag1"


@pytest.mark.unit
def test_browse_namespace_recursive():
    """Test browsing works recursively through tree."""
    # Deep nesting: Root -> Folder1 -> Folder2 -> Tag1
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    folder2 = MockNode("Folder2", 2, "Folder2", "Object", [tag1])
    folder1 = MockNode("Folder1", 2, "Folder1", "Object", [folder2])
    root = MockNode("Root", 0, "Root", "Object", [folder1])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    variables = browser.browse_namespace(2)

    assert len(variables) == 1
    assert variables[0].name == "Tag1"


@pytest.mark.unit
def test_browse_namespace_empty():
    """Test browsing empty namespace returns empty list."""
    root = MockNode("Root", 0, "Root", "Object", [])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    variables = browser.browse_namespace(2)

    assert len(variables) == 0


@pytest.mark.unit
def test_browse_all_namespaces():
    """Test browsing all namespaces finds variables in each."""
    tag_ns1 = MockNode("Tag1", 1, "Tag1", "Variable")
    tag_ns2 = MockNode("Tag2", 2, "Tag2", "Variable")
    tag_ns3 = MockNode("Tag3", 3, "Tag3", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag_ns1, tag_ns2, tag_ns3])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom", "urn:other"]
    browser = NodeBrowser(client, namespaces)

    all_vars = browser.browse_all_namespaces()

    assert 1 in all_vars
    assert 2 in all_vars
    assert 3 in all_vars
    assert len(all_vars[1]) == 1
    assert len(all_vars[2]) == 1
    assert len(all_vars[3]) == 1


@pytest.mark.unit
def test_browse_all_namespaces_skips_empty():
    """Test browse_all_namespaces only returns namespaces with variables."""
    tag_ns2 = MockNode("Tag2", 2, "Tag2", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag_ns2])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom", "urn:other"]
    browser = NodeBrowser(client, namespaces)

    all_vars = browser.browse_all_namespaces()

    assert 0 not in all_vars  # Empty
    assert 1 not in all_vars  # Empty
    assert 2 in all_vars  # Has variables
    assert 3 not in all_vars  # Empty


@pytest.mark.unit
def test_read_nodemap_stats_single_namespace():
    """Test reading nodemap stats for single namespace."""
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    tag2 = MockNode("Tag2", 2, "Tag2", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag1, tag2])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    stats = browser.read_nodemap_stats(namespace_idx=2)

    assert stats["total_namespaces"] == 3
    assert stats["total_variables"] == 2
    assert stats["variables_by_namespace"][2] == 2
    assert 0 in stats["namespaces"]
    assert 1 in stats["namespaces"]
    assert 2 in stats["namespaces"]


@pytest.mark.unit
def test_read_nodemap_stats_all_namespaces():
    """Test reading nodemap stats for all namespaces."""
    tag_ns1 = MockNode("Tag1", 1, "Tag1", "Variable")
    tag_ns2a = MockNode("Tag2a", 2, "Tag2a", "Variable")
    tag_ns2b = MockNode("Tag2b", 2, "Tag2b", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag_ns1, tag_ns2a, tag_ns2b])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    stats = browser.read_nodemap_stats()

    assert stats["total_variables"] == 3
    assert stats["variables_by_namespace"][1] == 1
    assert stats["variables_by_namespace"][2] == 2


@pytest.mark.unit
def test_read_nodemap_stats_data_types():
    """Test nodemap stats collects data type information."""
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    tag1._data_type = "Int32"
    tag2 = MockNode("Tag2", 2, "Tag2", "Variable")
    tag2._data_type = "Float"
    tag3 = MockNode("Tag3", 2, "Tag3", "Variable")
    tag3._data_type = "Int32"
    root = MockNode("Root", 0, "Root", "Object", [tag1, tag2, tag3])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    stats = browser.read_nodemap_stats(namespace_idx=2)

    assert stats["data_types"]["Int32"] == 2
    assert stats["data_types"]["Float"] == 1


@pytest.mark.unit
def test_print_nodemap_stats(capsys):
    """Test printing nodemap statistics."""
    tag1 = MockNode("Tag1", 2, "Tag1", "Variable")
    root = MockNode("Root", 0, "Root", "Object", [tag1])

    client = MockClient(root)
    namespaces = ["http://opcfoundation.org/UA/", "urn:server", "urn:custom"]
    browser = NodeBrowser(client, namespaces)

    stats = browser.read_nodemap_stats(namespace_idx=2)
    browser.print_nodemap_stats(stats)

    captured = capsys.readouterr()
    assert "Nodemap Statistics" in captured.out
    assert "Namespaces (3)" in captured.out
    assert "Total Variables: 1" in captured.out
    assert "Data Types:" in captured.out
