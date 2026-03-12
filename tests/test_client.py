#!/usr/bin/env python3
"""Test OPC UA client to verify nodes are accessible"""

from opcua import Client
import time
import argparse
from datetime import datetime

parser = argparse.ArgumentParser(description="Test OPC UA client")
parser.add_argument("--tag-read-count", type=int, default=25, help="Number of changed tags to display per poll (default: 25)")
parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between polls (default: 2.0)")
parser.add_argument("--poll-count", type=int, default=5, help="Number of times to poll (default: 5, use 0 for infinite)")
args = parser.parse_args()

client = Client("opc.tcp://localhost:4840")
client.connect()

try:
    # Check namespace array
    namespaces = client.get_namespace_array()
    print("Namespaces on server:")
    for i, ns in enumerate(namespaces):
        print(f"  ns={i}: {ns}")
    
    # Find the index for urn:pet001:tags
    pet_ns_idx = namespaces.index("urn:pet001:tags")
    print(f"\nurn:pet001:tags is at ns={pet_ns_idx}")
    
    # Browse to find all variable nodes in the PET001 namespace
    print(f"\nDiscovering all tags in ns={pet_ns_idx}...")
    print("-" * 80)
    
    root = client.get_root_node()
    objects = client.get_objects_node()
    
    # Recursively browse to find ALL variable nodes in the PET001 namespace
    def browse_variables(node, target_ns, found_vars=None):
        if found_vars is None:
            found_vars = []
            
        try:
            for child in node.get_children():
                try:
                    # Check if it's a variable node in the target namespace
                    node_class = child.get_node_class()
                    if node_class.name == "Variable" and child.nodeid.NamespaceIndex == target_ns:
                        found_vars.append(child)
                    # Recursively browse folders/objects
                    browse_variables(child, target_ns, found_vars)
                except Exception:
                    continue
        except Exception:
            pass
        return found_vars
    
    variables = browse_variables(objects, pet_ns_idx)
    
    print(f"Found {len(variables)} total variables\n")
    
    # Store previous values
    prev_values = {}
    
    # Poll loop
    poll_num = 0
    try:
        while args.poll_count == 0 or poll_num < args.poll_count:
            poll_num += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # Read all variables and track changes
            changed_vars = []
            for var in variables:
                try:
                    node_id = var.nodeid.to_string()
                    browse_name = var.get_browse_name().Name
                    value = var.get_value()
                    
                    # Check if value changed
                    if node_id not in prev_values or prev_values[node_id] != value:
                        read_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        changed_vars.append({
                            'timestamp': read_time,
                            'node_id': node_id,
                            'browse_name': browse_name,
                            'value': value,
                            'prev_value': prev_values.get(node_id, 'N/A')
                        })
                        prev_values[node_id] = value
                except Exception:
                    continue
            
            # Display changed values (up to tag-read-count)
            print(f"\n{'='*110}")
            print(f"Poll #{poll_num} at {timestamp} - {len(changed_vars)} tag(s) changed")
            print(f"{'='*110}")
            
            if changed_vars:
                print(f"{'#':<4} {'Timestamp':<23} {'NodeID':<50} {'Value':<30}")
                print(f"{'-'*110}")
                
                for i, item in enumerate(changed_vars[:args.tag_read_count], 1):
                    value_str = str(item['value'])[:28]  # Truncate long values
                    print(f"{i:<4} {item['timestamp']:<23} {item['browse_name']:<50} {value_str:<30}")
                
                if len(changed_vars) > args.tag_read_count:
                    print(f"\n... and {len(changed_vars) - args.tag_read_count} more changed tags (use --tag-read-count to see more)")
            else:
                print("No changes detected")
            
            if args.poll_count == 0 or poll_num < args.poll_count:
                print(f"\nWaiting {args.poll_interval}s before next poll... (Ctrl+C to stop)")
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    print(f"\n✓ Completed {poll_num} polls")
    
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    client.disconnect()
