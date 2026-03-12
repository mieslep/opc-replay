"""
OPC UA Replay Server

A Python package for replaying OPC UA historical data from CSV or Parquet files.
"""

__version__ = "0.3.0"

from .server import main

__all__ = ["main"]
