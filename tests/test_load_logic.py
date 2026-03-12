#!/usr/bin/env python3
"""Quick test to verify the load_and_prepare_data logic"""
import pandas as pd

# Simulate the function
def test_load_logic():
    # Load parquet
    df = pd.read_parquet('PETALL_20251214_20251221.parquet')
    print(f"1. Initial load: {len(df)} rows")
    
    # Normalize columns
    if 'TAG_NAME' in df.columns:
        df = df.rename(columns={'TAG_NAME': 'TAGNAME', 'VALUE': 'TAGVALUE'})
    
    # Sort by timestamp
    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'], utc=True)
    df = df.sort_values('TIMESTAMP')
    print(f"2. After sort: {len(df)} rows")
    print(f"   Time range: {df['TIMESTAMP'].min()} to {df['TIMESTAMP'].max()}")
    
    # Apply offset 3600s
    first_ts = df['TIMESTAMP'].iloc[0]
    offset_ts = first_ts + pd.Timedelta(seconds=3600)
    df_offset = df[df['TIMESTAMP'] >= offset_ts].copy()
    print(f"\n3. After offset 3600s: {len(df_offset)} rows")
    print(f"   New start: {df_offset['TIMESTAMP'].iloc[0]}")
    
    # Apply max_rows 100
    df_limited = df_offset.head(100)
    print(f"\n4. After max_rows 100: {len(df_limited)} rows")
    print(f"   Time range: {df_limited['TIMESTAMP'].min()} to {df_limited['TIMESTAMP'].max()}")
    duration = (df_limited['TIMESTAMP'].max() - df_limited['TIMESTAMP'].min()).total_seconds()
    print(f"   Duration: {duration:.1f}s ({duration/60:.1f} min)")
    
if __name__ == '__main__':
    test_load_logic()
