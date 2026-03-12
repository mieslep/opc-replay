# OPC Replay Server

A Python-based OPC UA replay server that replays historical timestamped tag data from CSV or Parquet files. Perfect for testing, simulation, and development scenarios where you need to reproduce specific OPC UA data sequences.

## Features

- 🔄 **Replay Historical Data** - Replay timestamped OPC UA tag data at real-time speed or accelerated
- 🎯 **Real-Time Tag Injection** - Override tag values on-the-fly via HTTP REST API while server is running
- 📊 **Multiple Formats** - Support for both CSV and Parquet data files
- 🏷️ **NodeSet Import** - Import OPC UA NodeSet2 XML files to define address space
- ⚡ **Speed Control** - Adjust playback speed (1x real-time, 10x, 100x, etc.)
- 🔁 **Loop Mode** - Continuously replay data for long-running tests
- 🛡️ **Robust Handling** - Skip invalid NodeIds and gracefully handle errors
- 🔧 **Namespace Mapping** - Automatic namespace index remapping when needed
- 🌐 **HTTP REST API** - Language-agnostic tag injection interface (default port 8080)
- ⏱️ **Scheduled Overrides** - Set time-delayed injections with configurable duration
- 📝 **Proper OPC UA Timestamps** - Sets SourceTimestamp and ServerTimestamp for compliance

## Installation

### Clone and Run (Development)

```bash
git clone <repository-url>
cd opc-replay
uv sync
```

### Install as Package

```bash
pip install opc-replay
```

Or with uv:

```bash
uv pip install opc-replay
```

## Quick Start

### Basic Usage

Run the replay server with example data:

```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --speed 10
```

This will:
- Start an OPC UA server at `opc.tcp://0.0.0.0:4840/`
- Load the NodeSet XML to define tags
- Replay the CSV data at 10x speed

### Using Parquet Files

The server also supports Parquet format for larger datasets:

```bash
opc-replay \
    --nodeset your-nodeset.xml \
    --data your-data.parquet \
    --ts-col TIMESTAMP \
    --speed 10
```

## Command-Line Options

### Required Arguments

- `--nodeset FILE` - NodeSet2 XML file defining the OPC UA address space
- `--data FILE` - Data file (.csv or .parquet) with timestamped tag values
- `--ts-col COLUMN` - Name of the timestamp column (e.g., `TS`, `TIMESTAMP`)

### Playback Control

- `--speed N` - Playback speed multiplier (default: 1.0 for real-time)
  - `--speed 10` = 10x faster
  - `--speed 0.5` = half speed
- `--loop` - Loop playback forever
- `--offset N` - Skip first N seconds from start (e.g., `3600` skips first hour)
- `--max-rows N` - Limit number of rows for quick testing

### Server Configuration

- `--endpoint URL` - OPC UA endpoint (default: `opc.tcp://0.0.0.0:4840/`)
- `--server-name NAME` - Server name (default: `ReplayServer`)
- `--api-port PORT` - HTTP port for tag injection API (default: `8080`, set to `0` to disable)

### Error Handling

- `--drop-bad-nodeset-nodeids` - Drop nodes with invalid NodeIds from NodeSet (prevents import crash)
- `--skip-bad-csv` - Skip data rows with invalid NodeIds or write failures
- `--allow-ns-mismatch` - Enable automatic namespace index remapping

### Other Options

- `--warmup N` - Wait N seconds before starting replay
- `--quiet` - Reduce per-update logging

## Real-Time Tag Injection

The server includes a built-in HTTP REST API for injecting override values to tags while the server is running. This is perfect for:
- Testing edge cases and failure scenarios
- Simulating sensor malfunctions or anomalies
- Injecting events at specific times
- Interactive simulation control

### Quick Start with Tag Injection

```bash
# Terminal 1: Start the replay server (API enabled by default on port 8080)
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --loop

# Terminal 2: Inject a single tag override
opc-inject \
    --tag "ns=2;s=Temperature" \
    --value 99.9 \
    --duration 30

# Or inject a batch of overrides from a file
opc-inject --file examples/simple-injection.json
```

### Tag Injection CLI (`opc-inject`)

The `opc-inject` command provides a convenient CLI for injecting tag overrides:

```bash
# Single tag injection
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30 --dtype Float

# Delayed injection (starts after 10 seconds)
opc-inject --tag "ns=2;s=Pressure" --value 200.5 --offset 10 --duration 20

# Batch injection from JSON
opc-inject --file examples/simple-injection.json

# Batch injection from CSV
opc-inject --file examples/simple-injection.csv

# List active overrides
opc-inject --list

# Clear all overrides
opc-inject --clear

# Target different server
opc-inject --url http://localhost:8080 --tag "ns=2;s=Flow" --value 50.0
```

#### CLI Options

- `--tag NODEID` - Tag NodeId to inject (e.g., `ns=2;s=Temperature`)
- `--value VALUE` - Override value to inject
- `--offset SECONDS` - Delay before activation (default: 0)
- `--duration SECONDS` - How long to hold override (default: 60)
- `--dtype TYPE` - Optional data type hint (Float, Int32, Boolean, String, etc.)
- `--file PATH` - Load injections from CSV or JSON file
- `--list` - List all active/pending overrides
- `--clear` - Clear all overrides
- `--url URL` - Target server URL (default: `http://localhost:8080`)

### HTTP REST API

The injection API provides three endpoints:

#### POST /inject - Add Override(s)

Inject a single tag override:
```bash
curl -X POST http://localhost:8080/inject \
  -H "Content-Type: application/json" \
  -d '{
    "tagname": "ns=2;s=Temperature",
    "value": 99.9,
    "time_offset_s": 0,
    "duration_s": 30,
    "dtype": "Float"
  }'
```

Inject multiple overrides at once:
```bash
curl -X POST http://localhost:8080/inject \
  -H "Content-Type: application/json" \
  -d '{
    "injections": [
      {"tagname": "ns=2;s=Temperature", "value": 99.9, "time_offset_s": 0, "duration_s": 30},
      {"tagname": "ns=2;s=Pressure", "value": 200.5, "time_offset_s": 5, "duration_s": 20}
    ]
  }'
```

**Request Fields:**
- `tagname` (required): NodeId in canonical format (`ns=X;s=...`)
- `value` (required): Override value (number, string, or boolean)
- `time_offset_s` (optional): Seconds to wait before activating (default: 0)
- `duration_s` (optional): Seconds to hold override (default: 60)
- `dtype` (optional): Data type hint (Float, Int32, Boolean, String, etc.)

**Response:** `200 OK` with confirmation message

#### GET /inject - List Overrides

List all active and pending overrides:
```bash
curl http://localhost:8080/inject
```

**Response:**
```json
{
  "active": [
    {
      "tagname": "ns=2;s=Temperature",
      "value": 99.9,
      "dtype": "Float",
      "activated_at": "2026-03-12T14:30:00.123Z",
      "expires_at": "2026-03-12T14:30:30.123Z"
    }
  ],
  "pending": [
    {
      "tagname": "ns=2;s=Pressure",
      "value": 200.5,
      "dtype": "Float",
      "activates_at": "2026-03-12T14:30:05.123Z",
      "expires_at": "2026-03-12T14:30:25.123Z"
    }
  ]
}
```

#### DELETE /inject - Clear All Overrides

Remove all active and pending overrides:
```bash
curl -X DELETE http://localhost:8080/inject
```

**Response:** `200 OK` with count of cleared overrides

### Injection File Formats

#### JSON Format

```json
{
  "injections": [
    {
      "tagname": "ns=2;s=Temperature",
      "value": 99.9,
      "time_offset_s": 0,
      "duration_s": 30,
      "dtype": "Float"
    },
    {
      "tagname": "ns=2;s=Pressure",
      "value": 200.5,
      "time_offset_s": 5,
      "duration_s": 20,
      "dtype": "Float"
    }
  ]
}
```

#### CSV Format

```csv
tagname,value,time_offset_s,duration_s,dtype
ns=2;s=Temperature,99.9,0,30,Float
ns=2;s=Pressure,200.5,5,20,Float
ns=2;s=Flow,50.0,10,15,Float
```

### Python Integration Example

```python
import requests
import time

API_URL = "http://localhost:8080/inject"

# Inject a single override
response = requests.post(API_URL, json={
    "tagname": "ns=2;s=Temperature",
    "value": 99.9,
    "duration_s": 30
})
print(response.json())

# Inject multiple overrides
response = requests.post(API_URL, json={
    "injections": [
        {"tagname": "ns=2;s=Temperature", "value": 99.9, "time_offset_s": 0, "duration_s": 30},
        {"tagname": "ns=2;s=Pressure", "value": 200.5, "time_offset_s": 5, "duration_s": 20}
    ]
})

# Wait and check active overrides
time.sleep(1)
response = requests.get(API_URL)
print(response.json())

# Clear all overrides
response = requests.delete(API_URL)
print(response.json())
```

### Disabling the API

If you don't need the injection API, you can disable it:

```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --api-port 0
```

## Data Format Requirements

### CSV/Parquet Data Files

Required columns (flexible naming):

| Column | Aliases | Description |
|--------|---------|-------------|
| `TAGNAME` | `TAG_NAME` | Node identifier (e.g., `ns=2;s=System.Temperature`) |
| `TAGVALUE` | `VALUE` | Tag value |
| `DATATYPE` | - | OPC UA data type (see below) |
| Timestamp | (specified via `--ts-col`) | ISO format timestamp |

### Supported Data Types

- Numeric: `Float`, `Double`, `Int16`, `UInt16`, `Int32`, `UInt32`, `Int64`, `UInt64`, `SByte`, `Byte`
- Other: `Boolean`, `String`, `DateTime`

### Example CSV Format

```csv
TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:00Z
ns=2;s=Flow,15.2,Float,2026-01-01T10:00:00Z
ns=2;s=Temperature,20.6,Float,2026-01-01T10:00:01Z
ns=2;s=Pressure,101.4,Float,2026-01-01T10:00:01Z
ns=2;s=Flow,15.3,Float,2026-01-01T10:00:01Z
```

## Creating NodeSet XML from Tag Catalog

If you have a tag catalog CSV, you can generate a NodeSet XML:

```bash
python -m opc_replay.csv_to_nodeset \
    --csv tag-catalog.csv \
    --out nodeset.xml \
    --root-name MySystem \
    --split-regex '\.'
```

Tag catalog format:
```csv
TAGNAME,TAGVALUE,DATATYPE
Temperature,20.5,Float
Pressure,101.3,Float
Flow,15.2,Float
```

## Testing with Client

Connect to the replay server using the included test client:

```bash
python tests/test_client.py \
    --tag-read-count 15 \
    --poll-count 5 \
    --poll-interval 2
```

Or use any OPC UA client (UAExpert, Prosys OPC UA Browser, etc.) and connect to `opc.tcp://localhost:4840/`

## Example Scenarios

### Development Testing

Replay specific sequences at high speed for rapid testing:

```bash
opc-replay \
    --nodeset nodeset.xml \
    --data test-scenario.csv \
    --ts-col TS \
    --speed 100 \
    --max-rows 1000
```

### Long-Running Simulation

Continuously replay data for stress testing:

```bash
opc-replay \
    --nodeset nodeset.xml \
    --data production-data.parquet \
    --ts-col TIMESTAMP \
    --speed 1 \
    --loop
```

### Skip to Specific Time

Jump to an interesting part of the data:

```bash
opc-replay \
    --nodeset nodeset.xml \
    --data data.csv \
    --ts-col TS \
    --offset 7200 \
    --speed 5
```

(Starts replay 2 hours into the data at 5x speed)

## Troubleshooting

### Import Errors with NodeSet

If you see errors during NodeSet import about invalid NodeIds:

```bash
opc-replay --nodeset nodeset.xml --data data.csv --ts-col TS \
    --drop-bad-nodeset-nodeids \
    --skip-bad-csv
```

### Namespace Mismatch

If your CSV uses different namespace indices than the NodeSet:

```bash
opc-replay --nodeset nodeset.xml --data data.csv --ts-col TS \
    --allow-ns-mismatch
```

### Performance Tips

- Use Parquet files instead of CSV for large datasets (faster loading)
- Use `--max-rows` during development to limit data size
- Use `--quiet` to reduce logging overhead
- Consider `--offset` to skip to relevant portions of data

## Architecture

```
opc-replay/
├── opc_replay/              # Main package
│   ├── __init__.py          # Package initialization
│   ├── server.py            # Main replay server
│   └── csv_to_nodeset.py    # NodeSet generator utility
├── examples/                # Example data files
├── tests/                   # Test utilities
├── pyproject.toml          # Package configuration
└── README.md               # This file
```

## Contributing

Contributions welcome! Please feel free to submit issues or pull requests.

## License

See LICENSE file for details.

## Requirements

- Python >= 3.13
- Dependencies: opcua, pandas, pyarrow

All dependencies are automatically installed when you install the package.
