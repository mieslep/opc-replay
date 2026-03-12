# OPC Replay - Comprehensive Usage Guide

This guide provides detailed documentation on using the OPC Replay server, tag injection,
and monitoring tools for OPC UA replay scenarios.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Command Reference](#command-reference)
3. [Data Format Specifications](#data-format-specifications)
4. [NodeSet Generation](#nodeset-generation)
5. [Tag Injection Patterns](#tag-injection-patterns)
6. [Integration Testing](#integration-testing)
7. [Language-Agnostic API Examples](#language-agnostic-api-examples)
8. [Advanced Scenarios](#advanced-scenarios)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Example Files

This directory contains simple example files for testing:

- `simple-nodeset.xml` - Simple OPC UA NodeSet with 3 tags (Temperature,Pressure, Flow)
- `simple-data.csv` - Sample CSV data with timestamped tag values (18 rows, 6 seconds)
- `simple-injection.json` - Example tag injection file (JSON format)
- `simple-injection.csv` - Example tag injection file (CSV format)
- `demo_client.py` - Simple Python script showing how to read from OPC UA server

### 30-Second Demo

\`\`\`bash
# Terminal 1: Start replay server with auto-generated NodeSet
opc-replay --data examples/simple-data.csv --ts-col TS --auto-nodeset --speed 10 --loop

# Terminal 2: Monitor with OPC client
opc-client

# Terminal 3: Inject an override
opc-inject --tag "ns=2;s=Temperature" --value 99.9 --duration 30
\`\`\`

For detailed information on all commands and options, continue reading...

