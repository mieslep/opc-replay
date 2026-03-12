#!/usr/bin/env python3
"""
Simple demonstration of connecting to OPC UA server and reading values.

This is a minimal example showing how to use the opcua library directly.
For a full-featured monitoring tool, use the opc-client command instead.

Usage:
    python examples/demo_client.py
"""

from opcua import Client
import time

# Connect to server
client = Client("opc.tcp://localhost:4840")
client.connect()

try:
    print("Connected to OPC UA server")
    print()
    
    # List namespaces
    namespaces = client.get_namespace_array()
    print("Available namespaces:")
    for i, ns in enumerate(namespaces):
        print(f"  ns={i}: {ns}")
    print()
    
    # Read specific tags by NodeId
    # These are the tags from examples/simple-nodeset.xml
    tags = [
        "ns=2;s=Temperature",
        "ns=2;s=Pressure",
        "ns=2;s=Flow",
    ]
    
    print("Reading tag values:")
    print("-" * 60)
    
    for tag_id in tags:
        try:
            node = client.get_node(tag_id)
            value = node.get_value()
            browse_name = node.get_browse_name().Name
            print(f"{browse_name:20s} = {value}")
        except Exception as e:
            print(f"{tag_id:20s} = ERROR: {e}")
    
    print()
    print("✓ Demo complete")

finally:
    client.disconnect()
    print("Disconnected")
