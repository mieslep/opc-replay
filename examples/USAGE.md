# OPC Replay Examples

This directory contains simple example files for testing the OPC Replay server.

## Example Files

- `simple-nodeset.xml` - Simple OPC UA NodeSet XML with 3 tags (Temperature, Pressure, Flow)
- `simple-data.csv` - Sample CSV data with timestamped tag values (18 rows, 6 seconds of data)

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
- `--drop-bad-nodeset-nodeids` - Drop invalid NodeIds from NodeSet
- `--skip-bad-csv` - Skip data rows with invalid NodeIds
- `--allow-ns-mismatch` - Enable automatic namespace remapping

