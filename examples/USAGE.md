# OPC Replay Examples

This directory contains simple example files for testing the OPC Replay server.

## Example Files

- `simple-nodeset.xml` - Simple OPC UA NodeSet XML with 3 tags (Temperature, Pressure, Flow)
- `simple-data.csv` - Sample CSV data with timestamped tag values (18 rows, 6 seconds of data)
- `simple-injection.json` - Example tag injection file (JSON format)
- `simple-injection.csv` - Example tag injection file (CSV format)

## Quick Start

### Run the replay server with example data:

```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --speed 10
```

This will:
- Start an OPC UA server at `opc.tcp://0.0.0.0:4840/`
- Load 3 tags: Temperature, Pressure, Flow
- Replay 6 seconds of data at 10x speed (completes in 0.6 seconds)

### Connect a test client:

```bash
python tests/test_client.py
```

Or use any OPC UA client (UAExpert, Prosys OPC UA Browser, etc.) and connect to `opc.tcp://localhost:4840/`

## Creating Your Own NodeSet

If you have a tag catalog CSV, you can generate a NodeSet XML:

```bash
python -m opc_replay.csv_to_nodeset \
    --csv your-tag-catalog.csv \
    --out your-nodeset.xml \
    --root-name YourSystem \
    --split-regex '\.'
```

## Data Format Requirements

### CSV/Parquet columns:
- `TAGNAME` or `TAG_NAME` - Node identifier in format `ns=X;s=YourTag.Name`
- `TAGVALUE` or `VALUE` - Tag value
- `DATATYPE` - OPC UA data type (Float, Int32, Boolean, String, etc.)
- Timestamp column (specified via `--ts-col`, commonly `TS` or `TIMESTAMP`)

### Example Data Format

See `simple-data.csv`:
```csv
TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:00Z
ns=2;s=Flow,15.2,Float,2026-01-01T10:00:00Z
```

## Common Usage Patterns

### Quick Test (10 rows, fast)
```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --speed 100 \
    --max-rows 10
```

### Loop Forever
```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --speed 10 \
    --loop
```

### Quiet Mode
```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --speed 10 \
    --quiet
```

## Common Options

- `--speed N` - Playback speedup factor (1=real-time, 10=10x faster)
- `--loop` - Loop playback forever
- `--offset N` - Skip first N seconds from start
- `--max-rows N` - Limit number of rows for quick testing
- `--quiet` - Reduce per-update logging
- `--api-port PORT` - HTTP port for tag injection API (default: 8080, 0 to disable)
- `--drop-bad-nodeset-nodeids` - Drop invalid NodeIds from NodeSet
- `--skip-bad-csv` - Skip data rows with invalid NodeIds
- `--allow-ns-mismatch` - Enable automatic namespace remapping

## Tag Injection (New!)

The server includes a built-in HTTP REST API for overriding tag values in real-time while the server is running.

### Quick Start with Tag Injection

```bash
# Terminal 1: Start server with API enabled (default)
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --loop

# Terminal 2: Inject a tag override
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30
```

### Single Tag Injection

```bash
# Basic injection (60 second duration by default)
opc-inject --tag "ns=2;s=Temperature" --value 99.9

# With explicit duration
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30

# Delayed injection (starts after 10 seconds)
opc-inject --tag "ns=2;s=Pressure" --value 200.5 --offset 10 --duration 20

# With data type hint
opc-inject --tag "ns=2;s=Flow" --value 50.0 --dtype Float --duration 15
```

### Batch Injection from Files

Inject multiple overrides at once:

```bash
# From JSON file
opc-inject --file examples/simple-injection.json

# From CSV file
opc-inject --file examples/simple-injection.csv
```

### Managing Overrides

```bash
# List all active and pending overrides
opc-inject --list

# Clear all overrides
opc-inject --clear

# Target different server
opc-inject --url http://remote-server:8080 --tag "ns=2;s=Temperature" --value 99.9
```

### Injection File Formats

**JSON format** (`simple-injection.json`):
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

**CSV format** (`simple-injection.csv`):
```csv
tagname,value,time_offset_s,duration_s,dtype
ns=2;s=Temperature,99.9,0,30,Float
ns=2;s=Pressure,200.5,5,20,Float
ns=2;s=Flow,50.0,10,15,Float
```

### REST API Usage

You can also use the HTTP API directly:

```bash
# Inject a single override
curl -X POST http://localhost:8080/inject \
  -H "Content-Type: application/json" \
  -d '{
    "tagname": "ns=2;s=Temperature",
    "value": 99.9,
    "duration_s": 30
  }'

# List active overrides
curl http://localhost:8080/inject

# Clear all overrides
curl -X DELETE http://localhost:8080/inject
```

### Use Cases for Tag Injection

- **Testing edge cases**: Inject extreme values to test alarm logic
- **Simulating failures**: Override sensor values to simulate malfunctions  
- **Interactive control**: Manually control tag values during demos
- **Automated testing**: Inject values at specific times in test scripts
- **Scenario replay**: Combine historical data with injected anomalies

### Disabling the API

If you don't need the injection API:

```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --api-port 0
```

## Integration Testing

Run the comprehensive integration test suite:

```bash
# Start server first (with --loop for continuous testing)
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --loop

# In another terminal, run tests
python tests/test_override.py \
    --endpoint opc.tcp://localhost:4840/ \
    --api http://localhost:8080
```

- `--offset N` - Skip first N seconds from start
- `--max-rows N` - Limit number of rows for quick testing
- `--quiet` - Reduce per-update logging
- `--drop-bad-nodeset-nodeids` - Drop invalid NodeIds from NodeSet
- `--skip-bad-csv` - Skip data rows with invalid NodeIds
- `--allow-ns-mismatch` - Enable automatic namespace remapping

