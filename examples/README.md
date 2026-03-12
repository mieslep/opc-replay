# OPC Replay Examples

This directory contains example files for testing and demonstrating the OPC Replay server.

## Example Files

### Data Files

- **simple-data.csv** - Sample CSV data with 3 tags (Temperature, Pressure, Flow)
  - 18 rows covering 6 seconds of data
  - Perfect for quick testing and demos
  - Tags: `ns=2;s=Temperature`, `ns=2;s=Pressure`, `ns=2;s=Flow`

- **simple-nodeset.xml** - OPC UA NodeSet2 XML defining the 3 simple tags
  - Matches the tags in simple-data.csv
  - Namespace URI: `http://example.com/simple`
  - Creates a folder structure: `SimpleTags/`

### Injection Files

- **simple-injection.json** - Example batch injection in JSON format
  - 3 tag overrides with staggered timing
  - Demonstrates scheduled injections

- **simple-injection.csv** - Example batch injection in CSV format
  - Same content as JSON version
  - Alternative format for convenience

### Scripts

- **demo_client.py** - Simple Python script demonstrating OPC UA client usage
  - Shows how to connect and read tags
  - Minimal example for learning

## Quick Start

### 1. Start the Replay Server

```bash
# From the repository root
opc-replay --data examples/simple-data.csv --ts-col TS --auto-nodeset --loop --speed 10
```

This will:
- Auto-generate a NodeSet from the data
- Start replaying at 10x speed
- Loop continuously for testing

### 2. Monitor with the Client

In another terminal:

```bash
opc-client
```

You'll see the three tags (Temperature, Pressure, Flow) changing values as the data replays.

### 3. Inject Overrides

In another terminal:

```bash
# Single tag injection
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30

# Or batch injection from file
opc-inject --file examples/simple-injection.json
```

Watch the client to see the injected values appear immediately!

### 4. Run the Demo Client Script

```bash
python examples/demo_client.py
```

This simple script connects to the server and reads the current values of all three tags.

## Using Your Own Data

To use your own data with opc-replay:

1. **Prepare your data file** (CSV or Parquet) with these columns:
   - `TAGNAME` or `TAG_NAME` - Node identifiers (e.g., `ns=2;s=YourTag`)
   - `TAGVALUE` or `VALUE` - Tag values
   - `DATATYPE` - OPC UA data types (Float, Int32, Boolean, String, etc.)
   - Timestamp column (name specified via `--ts-col`)

2. **Start the server** with auto-generated NodeSet:
   ```bash
   opc-replay --data your-data.csv --ts-col TIMESTAMP --auto-nodeset
   ```

3. **Or pre-generate a NodeSet**:
   ```bash
   python -m opc_replay.csv_to_nodeset \
       --csv your-data.csv \
       --out your-nodeset.xml \
       --root-name YourSystem
   
   opc-replay --nodeset your-nodeset.xml --data your-data.csv --ts-col TIMESTAMP
   ```

## Documentation

For detailed usage, command reference, and advanced scenarios, see:

- **[USAGE.md](USAGE.md)** - Comprehensive usage guide
- **[../README.md](../README.md)** - Project overview and installation

## File Format Reference

### simple-data.csv Format

```csv
TAGNAME,TAGVALUE,DATATYPE,TS
ns=2;s=Temperature,20.5,Float,2026-01-01T10:00:00Z
ns=2;s=Pressure,101.3,Float,2026-01-01T10:00:00Z
ns=2;s=Flow,15.2,Float,2026-01-01T10:00:00Z
...
```

### simple-injection.json Format

```json
{
  "injections": [
    {
      "tagname": "ns=2;s=Temperature",
      "value": 99.9,
      "time_offset_s": 0,
      "duration_s": 30,
      "dtype": "Float"
    }
  ]
}
```

### simple-injection.csv Format

```csv
tagname,value,time_offset_s,duration_s,dtype
ns=2;s=Temperature,99.9,0,30,Float
ns=2;s=Pressure,200.5,5,20,Float
```

## Tips

- **Start simple**: Use the example files to learn how everything works
- **Speed control**: Adjust `--speed` (1-100+) to match your testing needs
- **Loop mode**: Use `--loop` for continuous testing
- **Max rows**: Use `--max-rows 100` to limit data during early testing
- **Quiet mode**: Use `--quiet` to reduce logging noise

## Support

For issues or questions:
- Check the [troubleshooting guide](USAGE.md#troubleshooting) in USAGE.md
- Visit the [GitHub repository](https://github.com/phil/opc-replay)
- Review the main [README](../README.md)
