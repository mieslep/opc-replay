#!/usr/bin/env python3
"""
Generate sample data for OPC replay demonstrations.

Creates a CSV file with 5 minutes of data (300 seconds) with realistic
varying sensor values.
"""

import pandas as pd
from datetime import datetime, timedelta
import math

def generate_sample_data():
    """Generate 5 minutes of sample data with realistic variations."""
    
    # Start time
    start_time = datetime(2026, 1, 1, 10, 0, 0)
    
    # Generate timestamps (1 reading per second for 5 minutes)
    timestamps = [start_time + timedelta(seconds=i) for i in range(300)]
    
    data = []
    
    for i, ts in enumerate(timestamps):
        # Temperature: oscillates between 20-22°C with slow sine wave
        temp = 21.0 + math.sin(i / 30.0) * 1.0 + (i * 0.001)
        
        # Pressure: oscillates between 100-102 with different frequency
        pressure = 101.0 + math.sin(i / 20.0) * 1.0 + math.cos(i / 50.0) * 0.3
        
        # Flow: oscillates between 14-16 with some randomness simulation
        flow = 15.0 + math.sin(i / 25.0) * 1.0 + math.cos(i / 15.0) * 0.5
        
        # Add three tags per timestamp
        data.append({
            'TAGNAME': 'ns=2;s=Temperature',
            'TAGVALUE': round(temp, 2),
            'DATATYPE': 'Float',
            'TS': ts.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
        
        data.append({
            'TAGNAME': 'ns=2;s=Pressure',
            'TAGVALUE': round(pressure, 2),
            'DATATYPE': 'Float',
            'TS': ts.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
        
        data.append({
            'TAGNAME': 'ns=2;s=Flow',
            'TAGVALUE': round(flow, 2),
            'DATATYPE': 'Float',
            'TS': ts.strftime('%Y-%m-%dT%H:%M:%SZ')
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    return df


if __name__ == '__main__':
    df = generate_sample_data()
    
    # Save to CSV
    output_file = 'examples/simple-data.csv'
    df.to_csv(output_file, index=False)
    
    print(f"✓ Generated {len(df)} rows of data")
    print(f"✓ Saved to {output_file}")
    print(f"✓ Duration: 5 minutes (300 seconds)")
    print(f"✓ Tags: Temperature, Pressure, Flow")
    print(f"✓ Time range: {df['TS'].iloc[0]} to {df['TS'].iloc[-1]}")
