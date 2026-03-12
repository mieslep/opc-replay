# Integration Test Fixtures

Test data files for integration tests. These are minimal datasets designed for automated testing.

## test-data.csv

Minimal OPC UA replay data:
- **3 tags**: Temperature, Pressure, Flow
- **10 seconds** of data (1Hz sampling)
- **30 total rows**

Used by the automated server fixture that starts/stops `opc-replay` during integration tests.

### Usage

The `opcua_test_server` fixture in `conftest.py` automatically:
1. Starts server with this data: `opc-replay --data test-data.csv --ts-col TS --auto-nodeset --loop --speed 10`
2. Waits for server to be ready (port 4840)
3. Runs tests
4. Cleanly shuts down server

This makes integration tests fully automated - no manual server setup required.
