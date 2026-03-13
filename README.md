# OPC Replay Server

[![CI](https://github.com/mieslep/opc-replay/actions/workflows/ci.yml/badge.svg)](https://github.com/mieslep/opc-replay/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/opc-replay.svg)](https://pypi.org/project/opc-replay/)
[![Python Version](https://img.shields.io/pypi/pyversions/opc-replay.svg)](https://pypi.org/project/opc-replay/)

A Python-based OPC UA replay server for replaying historical timestamped tag data from CSV or Parquet files. Perfect for testing, simulation, and development scenarios where you need to reproduce specific OPC UA data sequences.

## Features

- 🔄 **Replay Historical Data** - CSV/Parquet files with configurable speed (1x to 100x+), offset, and loop mode
- 🏷️ **Auto-Generate NodeSets** - Create OPC UA address space automatically from your data files
- 🎯 **Real-Time Tag Injection** - HTTP REST API for overriding values on-the-fly with scheduled/delayed activation
- 🛡️ **Robust & Compliant** - Proper OPC UA timestamps, namespace remapping, graceful error handling

## Installation

### From PyPI (Recommended)

```bash
pip install opc-replay
```

Requires Python 3.13 or later.

### From Source (For Development)

```bash
git clone https://github.com/mieslep/opc-replay.git
cd opc-replay
pip install -e .
```

### With uv (Recommended for Development)

```bash
git clone https://github.com/mieslep/opc-replay.git
cd opc-replay
uv sync
```

For development setup and contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick Start

### 30-Second Demo

The easiest way to get started - auto-generate the NodeSet from your data:

```bash
# Start replay server (auto-generates NodeSet and loops continuously)
opc-replay --data examples/simple-data.csv --ts-col TS --auto-nodeset --loop

# In another terminal, monitor with the OPC client
opc-client

# In another terminal, inject an override
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30
```

### With Pre-Generated NodeSet

If you have an existing NodeSet XML:

```bash
opc-replay \
    --nodeset examples/simple-nodeset.xml \
    --data examples/simple-data.csv \
    --ts-col TS \
    --loop
```

## Core Commands

### `opc-replay` - Replay Server

Start an OPC UA server that replays historical data:

```bash
# Basic usage with auto-generated NodeSet
opc-replay --data mydata.csv --ts-col TIMESTAMP --auto-nodeset

# With existing NodeSet
opc-replay --nodeset nodeset.xml --data mydata.csv --ts-col TS

# Advanced options
opc-replay \
    --data mydata.parquet \
    --ts-col TIMESTAMP \
    --auto-nodeset \
    --speed 10 \
    --loop \
    --offset 3600 \
    --api-port 8080
```

**Key Options:**
- `--data FILE` - CSV or Parquet data file
- `--ts-col COLUMN` - Name of timestamp column
- `--auto-nodeset` - Auto-generate NodeSet from data (recommended)
- `--nodeset FILE` - Use existing NodeSet XML
- `--speed N` - Playback speed multiplier (default: 1.0)
- `--loop` - Loop playback forever
- `--offset N` - Skip first N seconds
- `--api-port PORT` - HTTP API port for tag injection (default: 8080, 0 to disable)
- `--allow-non-canonical` - Allow non-canonical NodeIds without auto-conversion (advanced)

### `opc-inject` - Tag Injection

Override tag values in real-time while the server is running:

```bash
# Single tag injection
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30

# Delayed injection (starts after 10 seconds)
opc-inject --tag "ns=2;s=Pressure" --value 200.5 --offset 10 --duration 20

# Batch injection from file
opc-inject --file injections.json

# List active overrides
opc-inject --list

# Clear all overrides
opc-inject --clear
```

### `opc-client` - Monitoring Client

Connect to an OPC UA server and monitor tag changes (polls continuously by default):

```bash
# Connect to local server (polls forever)
opc-client

# Connect to remote server
opc-client --endpoint opc.tcp://192.168.1.100:4840/

# Monitor specific namespace with limited polls
opc-client --namespace 2 --poll-count 10 --poll-interval 1
```

## Data Format

Your CSV or Parquet file needs these columns:

| Column | Aliases | Description |
|--------|---------|-------------|
| `TAGNAME` | `TAG_NAME` | Node identifier (e.g., `ns=2;s=Temperature`) |
| `TAGVALUE` | `VALUE` | Tag value |
| `DATATYPE` | - | OPC UA data type (Float, Int32, Boolean, String, etc.) |
| Timestamp | (specified via `--ts-col`) | ISO format timestamp |

**Example CSV:**
```csv
TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:00Z
ns=2;s=Flow,15.2,Float,2026-01-01T10:00:00Z
```

### Auto-Conversion of NodeIds

By default, `opc-replay` automatically converts non-canonical TAGNAMEs to canonical OPC UA format:

```csv
# Input data with mixed formats:
TAGNAME,TAGVALUE,DATATYPE,TS
Temperature,20.5,Float,2026-01-01T10:00:00Z           # Auto-converted to: ns=2;s=Temperature
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:00Z      # Already canonical, used as-is
PET001.Flow,15.2,Float,2026-01-01T10:00:00Z           # Auto-converted to: ns=2;s=PET001.Flow
```

**Canonical Format:** `ns=<namespace>;[isgb]=<identifier>`
- `ns=` - Namespace index (e.g., `ns=2`)
- Identifier type: `s=` (string), `i=` (integer), `g=` (GUID), `b=` (bytestring)
- Example: `ns=2;s=Tank.Level.Current`

**Benefits:**
- Works with legacy data that uses simple tag names
- No need to pre-process your CSV files
- Proper OPC UA compliance by default

**Advanced:** Use `--allow-non-canonical` to disable auto-conversion if your OPC UA client supports non-standard NodeIds.

## Use Cases

### Testing & Development
- **Replay specific sequences** at high speed for rapid testing
- **Simulate sensor failures** with tag injection
- **Test alarm logic** by injecting extreme values

### Integration Testing
- **Reproduce bugs** by replaying exact data sequences
- **Validate HMI/SCADA** behavior with known data patterns
- **Load testing** with continuous loop mode

### Training & Demos
- **Demonstrate systems** without live equipment
- **Interactive control** via tag injection API
- **Scenario replay** with historical data

## HTTP REST API

The built-in REST API enables programmatic control from any language:

```bash
# Inject a tag override
curl -X POST http://localhost:8080/inject \
  -H "Content-Type: application/json" \
  -d '{"tagname": "ns=2;s=Temperature", "value": 99.9, "duration_s": 30}'

# List active overrides
curl http://localhost:8080/inject

# Clear all overrides
curl -X DELETE http://localhost:8080/inject
```

## Documentation

- **[examples/](examples/)** - Sample data files and demonstration scripts
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes

## Architecture

```
┌─────────────────┐
│   Data File     │  CSV/Parquet with timestamped tag values
│ (CSV/Parquet)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  opc-replay     │  Replay server with HTTP API
│   (Server)      │  • Auto-generates NodeSet
└────────┬────────┘  • Replays data at configurable speed
         │           • Exposes OPC UA endpoint
         │           • HTTP REST API for tag injection
         ├──────────────────────┬─────────────────────┐
         ▼                      ▼                     ▼
┌─────────────────┐    ┌─────────────────┐   ┌─────────────────┐
│   opc-client    │    │   opc-inject    │   │  OPC UA Client  │
│  (Monitor)      │    │   (Control)     │   │ (UAExpert, etc) │
└─────────────────┘    └─────────────────┘   └─────────────────┘
```

## Requirements

- Python >= 3.13
- Dependencies: opcua, pandas, pyarrow (auto-installed)

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing guidelines, and how to submit pull requests.

## License

See [LICENSE](LICENSE) file for details.

## Credits

- Tag injection feature developed by Branislav
- Built with [python-opcua](https://github.com/FreeOpcUa/python-opcua)
