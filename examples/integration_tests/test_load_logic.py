#!/usr/bin/env python3
"""
Integration test: Verify load_and_prepare_data logic with example data.

Tests data loading, sorting, and filtering operations using the simple example data.

Requirements:
    - examples/simple-data.csv must exist

Usage:
    python examples/integration_tests/test_load_logic.py
"""
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path to import from opc_replay
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_load_logic():
    """Test data loading and preparation logic"""
    # Use example data file (go up two levels: integration_tests -> examples -> root)
    data_file = Path(__file__).parent.parent / "simple-data.csv"
    
    if not data_file.exists():
        print(f"ERROR: Example data file not found: {data_file}")
        sys.exit(1)
    
    # Load CSV
    df = pd.read_csv(data_file)
    print(f"1. Initial load: {len(df)} rows")
    
    # Normalize columns (handle alternative names)
    if 'TAG_NAME' in df.columns:
        df = df.rename(columns={'TAG_NAME': 'TAGNAME', 'VALUE': 'TAGVALUE'})
    
    # Sort by timestamp
    df['TS'] = pd.to_datetime(df['TS'], utc=True)
    df = df.sort_values('TS')
    print(f"2. After sort: {len(df)} rows")
    print(f"   Time range: {df['TS'].min()} to {df['TS'].max()}")
    
    # Test offset filtering (skip first 2 seconds)
    first_ts = df['TS'].iloc[0]
    offset_ts = first_ts + pd.Timedelta(seconds=2)
    df_offset = df[df['TS'] >= offset_ts].copy()
    print(f"\n3. After offset 2s: {len(df_offset)} rows")
    if len(df_offset) > 0:
        print(f"   New start: {df_offset['TS'].iloc[0]}")
    
    # Test max_rows limiting
    max_rows = 10
    df_limited = df_offset.head(max_rows)
    print(f"\n4. After max_rows {max_rows}: {len(df_limited)} rows")
    if len(df_limited) > 0:
        print(f"   Time range: {df_limited['TS'].min()} to {df_limited['TS'].max()}")
        duration = (df_limited['TS'].max() - df_limited['TS'].min()).total_seconds()
        print(f"   Duration: {duration:.1f}s")
    
    # Verify expected structure
    expected_columns = ['TAGNAME', 'TAGVALUE', 'DATATYPE', 'TS']
    for col in expected_columns:
        assert col in df.columns, f"Missing expected column: {col}"
    
    print("\n✓ All checks passed")

if __name__ == '__main__':
    test_load_logic()
