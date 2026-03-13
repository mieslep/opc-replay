"""OPC UA node browsing and discovery."""

try:
    from opcua import Client
except ImportError:
    print("ERROR: opcua package not installed. Run: pip install opcua")
    raise


class NodeBrowser:
    """
    Browse and discover OPC UA nodes.

    Handles recursive browsing of OPC UA address space, namespace discovery,
    and nodemap statistics generation.
    """

    def __init__(self, client: Client, namespaces: list[str]):
        """
        Initialize node browser.

        Args:
            client: Connected OPC UA client
            namespaces: List of namespace URIs from server
        """
        self.client = client
        self.namespaces = namespaces

    def browse_namespace(self, namespace_idx: int) -> list:
        """
        Browse and discover all variables in a specific namespace.

        Args:
            namespace_idx: Namespace index to browse

        Returns:
            List of variable nodes
        """
        objects = self.client.get_objects_node()
        return self._browse_recursive(objects, target_ns=namespace_idx)

    def browse_all_namespaces(self) -> dict[int, list]:
        """
        Browse and discover variables in all namespaces.

        Returns:
            Dictionary mapping namespace index to list of variables
        """
        result = {}
        for i in range(len(self.namespaces)):
            variables = self.browse_namespace(i)
            if variables:
                result[i] = variables
        return result

    def _browse_recursive(
        self, node, target_ns: int | None = None, found_vars: list | None = None
    ) -> list:
        """
        Recursively browse to find all variable nodes.

        Args:
            node: OPC UA node to browse from
            target_ns: Target namespace index (None = all namespaces)
            found_vars: List to accumulate found variables

        Returns:
            List of variable nodes
        """
        if found_vars is None:
            found_vars = []

        try:
            for child in node.get_children():
                try:
                    node_class = child.get_node_class()
                    ns_idx = child.nodeid.NamespaceIndex

                    # Check if it's a variable node in the target namespace
                    if node_class.name == "Variable":
                        if target_ns is None or ns_idx == target_ns:
                            found_vars.append(child)

                    # Recursively browse folders/objects
                    self._browse_recursive(child, target_ns, found_vars)
                except Exception:
                    # Skip inaccessible nodes
                    continue
        except Exception:
            # Skip nodes that can't be browsed
            pass

        return found_vars

    def read_nodemap_stats(self, namespace_idx: int | None = None) -> dict:
        """
        Read nodemap and generate statistics.

        Args:
            namespace_idx: Optional specific namespace to analyze (None = all)

        Returns:
            Dictionary with statistics about nodes, namespaces, and data types
        """
        stats = {
            "total_namespaces": len(self.namespaces),
            "namespaces": {},
            "total_variables": 0,
            "variables_by_namespace": {},
            "data_types": {},
        }

        # Add namespace URIs
        for i, ns_uri in enumerate(self.namespaces):
            stats["namespaces"][i] = ns_uri

        # Browse and count variables
        if namespace_idx is not None:
            # Single namespace
            variables = self.browse_namespace(namespace_idx)
            stats["variables_by_namespace"][namespace_idx] = len(variables)
            stats["total_variables"] = len(variables)

            # Collect data types
            self._collect_data_types(variables, stats["data_types"])
        else:
            # All namespaces
            all_vars = self.browse_all_namespaces()
            for ns_idx, variables in all_vars.items():
                count = len(variables)
                stats["variables_by_namespace"][ns_idx] = count
                stats["total_variables"] += count

                # Collect data types
                self._collect_data_types(variables, stats["data_types"])

        return stats

    def _collect_data_types(self, variables: list, type_counts: dict[str, int]):
        """
        Collect data type statistics from variables.

        Args:
            variables: List of variable nodes
            type_counts: Dictionary to accumulate type counts
        """
        for var in variables:
            try:
                data_type = var.get_data_type_as_variant_type()
                type_name = str(data_type).split(".")[-1]  # Get enum name
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            except Exception:
                # If we can't determine type, count as Unknown
                type_counts["Unknown"] = type_counts.get("Unknown", 0) + 1

    def print_nodemap_stats(self, stats: dict):
        """
        Print formatted nodemap statistics.

        Args:
            stats: Statistics dictionary from read_nodemap_stats()
        """
        print("\nNodemap Statistics")
        print("=" * 80)

        print(f"\nNamespaces ({stats['total_namespaces']}):")
        for ns_idx, ns_uri in stats["namespaces"].items():
            var_count = stats["variables_by_namespace"].get(ns_idx, 0)
            print(f"  ns={ns_idx}: {ns_uri} ({var_count} variables)")

        print(f"\nTotal Variables: {stats['total_variables']}")

        if stats["data_types"]:
            print("\nData Types:")
            # Sort by count descending
            sorted_types = sorted(stats["data_types"].items(), key=lambda x: x[1], reverse=True)
            for type_name, count in sorted_types:
                print(f"  {type_name}: {count}")

        print()
