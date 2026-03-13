"""
Backward compatibility shim for opc_replay.client.

The client has been refactored into a subpackage (opc_replay/client/).
This file maintains backward compatibility for any direct imports.
"""

from opc_replay.client import main

if __name__ == "__main__":
    main()
