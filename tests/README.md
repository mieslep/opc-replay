# OPC Replay Test Suite

Comprehensive pytest-based test suite for the opc-replay project, organized into unit and integration tests.

## Test Structure

```
tests/
├── unit/                         # Unit tests (mocked dependencies)
│   ├── conftest.py              # Shared pytest fixtures
│   ├── test_override_store.py   # OverrideStore thread safety (21 tests)
│   ├── test_type_casting.py     # Type casting functions (42 tests)
│   ├── test_nodeid_functions.py # NodeId validation/remapping (31 tests)
│   ├── test_data_loading.py     # CSV/Parquet data loading (30 tests)
│   ├── test_injection_handler.py # HTTP API handler (18 tests)
│   └── test_mqtt_publisher.py   # MQTT PubSub publisher (38 tests)
└── integration/                  # Integration tests (automated server)
    ├── conftest.py              # Server lifecycle fixture
    ├── fixtures/                # Test data for integration tests
    │   ├── test-data.csv        # Minimal 3-tag, 10-second dataset
    │   └── README.md
    ├── test_client.py           # OPC UA client monitoring
    ├── test_load_logic.py       # Data loading with real files
    ├── test_mqtt_integration.py  # MQTT PubSub integration (7 tests)
    ├── test_load_logic.py       # Data loading with real files
    ├── test_mqtt_integration.py  # MQTT PubSub integration (7 tests)
    └── test_override.py         # End-to-end override injection
```

## Running Tests

```bash
# Run all tests (unit + integration if server available)
uv run pytest tests/

# Run only unit tests (fast, no server required)
uv run pytest tests/unit/

# Run only integration tests (requires OPC UA server)
uv run pytest tests/integration/

# Run with verbose output
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/unit/test_override_store.py

# Run tests with specific marker
uv run pytest -m unit
uv run pytest -m integration
uv run pytest -m threading

# Run with coverage report
uv run pytest tests/unit/ --cov=opc_replay --cov-report=html

# Skip integration tests even if server is available
uv run pytest tests/ -m "not integration"
```

## Test Markers

- `@pytest.mark.unit` - Unit tests with mocked dependencies (fast, no external services)
- `@pytest.mark.integration` - Integration tests requiring OPC UA server (auto-skip if unavailable)
- `@pytest.mark.threading` - Thread safety and concurrency tests
- `@pytest.mark.slow` - Tests that take more than 1 second

## Integration Test Requirements

**Fully automated** - Integration tests automatically start and stop the OPC UA server with test data.

### How it works

The `opcua_test_server` pytest fixture (in `tests/integration/conftest.py`):
1. **Checks** if a server is already running on `localhost:4840`
   - If yes: uses the existing server
   - If no: starts a new server with test data
2. **Starts** the OPC UA server: `opc-replay --data tests/integration/fixtures/test-data.csv --ts-col TS --auto-nodeset --loop --speed 10`
3. **Waits** for server to be ready (port check with 10s timeout)
4. **Yields** server info (`endpoint`, `api_base`, `process`) to tests
5. **Shuts down** the server cleanly after all tests complete

### Test data

- **Minimal dataset**: 3 tags (Temperature, Pressure, Flow), 10 seconds, 30 rows
- **Location**: `tests/integration/fixtures/test-data.csv`
- **Purpose**: Fast, reproducible integration testing without large data files

### Manual server (optional)

You can still run the tests with your own server if preferred:

```bash
# Start your server in one terminal
uv run opc-replay --data examples/simple-data.csv --ts-col TS --auto-nodeset --loop --speed 10

# Run tests in another terminal (will use existing server)
uv run pytest tests/integration/ -v -s
```

The fixture detects the 80nning server and uses it instead of starting a new one.

## Unit Test Coverage (180 tests)

### test_override_store.py (21 tests)
**Critical** - Thread-safe tag override management

- Basic add/get/clear operations
- Timing logic (activation, expiration)
- Multiple overlapping overrides
- **Thread safety**: Concurrent add/get/clear operations
- Edge cases: zero duration, negative offset, remapped NodeIds

### test_type_casting.py (42 tests)
Type coercion for all OPC UA datatypes

- Basic casting: Float, Double, Int32, Int64, Boolean, String, DateTime
- Edge cases: NaN, None, boolean string variations
- Variant inference with/without explicit dtype
- Large numbers, scientific notation, whitespace handling

### test_nodeid_functions.py (31 tests)
NodeId validation and namespace remapping

- Canonical NodeId validation (ns=X;[isgb]=...)
- Namespace index remapping
- Edge cases: malformed NodeIds, Unicode, very long identifiers

### test_data_loading.py (30 tests)
CSV/Parquet file loading and preparation

- File format detection (CSV/Parquet)
- Column name normalization (TAG_NAME→TAGNAME, VALUE→TAGVALUE)
- Timestamp parsing and UTC conversion
- Offset and max_rows parameters
- Error handling: missing columns, invalid timestamps, UTF-8 BOM

### test_injection_handler.py (18 tests)
HTTP REST API for tag injection

- POST /inject: single and batch injections
- GET /inject: list active overrides
- DELETE /inject: clear all overrides
- JSON validation and error handling
- # test_mqtt_publisher.py (38 tests)
MQTT PubSub publisher per OPC UA Part 14

- MQTT topic construction (data and status topics)
- JSON NetworkMessage and DataSetMessage formatting
- Value serialization for all OPC UA data types
- MqttPublisher class (connect, publish, disconnect with mocked broker)
- Batch publishing, sequence number generation
- DataSetWriter ID auto-assignment

## Integration Test Coverage (10ailing slashes

### test_mqtt_publisher.py (38 tests)
MQTT PubSub publisher per OPC UA Part 14

- MQTT topic construction (data and status topics)
- JSON NetworkMessage and DataSetMessage formatting
- Value serialization for all OPC UA data types
- MqttPublisher class (connect, publish, disconnect with mocked broker)
- Batch publishing, sequence number generation
- DataSetWriter ID auto-assignment
# test_mqtt_integration.py
MQTT PubSub integration - tests CLI argument parsing, end-to-end JSON message format compliance, topic pattern validation, multi-datatype serialization, and graceful handling when paho-mqtt is missing.

##
## Integration Test Coverage (10 tests)

### test_client.py
OPC UA client connection and tag monitoring - tests browsing namespaces, discovering variables, and polling for value changes.

### test_load_logic.py
Data loading verification - tests CSV loading, column normalization, timestamp parsing, and filtering logic with real files.

### test_override.py
End-to-end override injection workflow - tests reading from OPC UA, injecting overrides via HTTP API, verifying values appear, and checking expiration.

### test_mqtt_integration.py
MQTT PubSub integration - tests CLI argument parsing, end-to-end JSON message format compliance, topic pattern validation, multi-datatype serialization, and graceful handling when paho-mqtt is missing.

## Key Testing Patterns

### Mocked Dependencies (Unit Tests)

Unit tests use mocked OPC UA objects to avoid external dependencies:

```python
def test_example(mock_opcua_server):
    # No real OPC UA server required
    server.get_node("ns=2;s=Tag").set_value(42)
```

### Thread Safety Testing

Thread safety tests use real threading to verify lock behavior:

```python
@pytest.mark.threading
def test_concurrent_access(override_store):
    threads = [threading.Thread(target=add_override) for _ in range(10)]
    # Verify no race conditions
```

### Time Mocking

Override timing tests use mocked time:

```python
def test_timing(override_store, mocker):
    current_time = [1000000.0]
    mocker.patch("time.time", side_effect=lambda: current_time[0])
    # Advance time manually
    current_ti2970] += 10
```

## Fixtures

See [conftest.py](conftest.py) for available fixtures:

- `sample_dataframe` - Pre-built pandas DataFrame with test data
- `temp_csv_file` / `temp_parquet_file` - Temporary data files
- `mock_opcua_server` / `mock_opcua_node` - Mocked OPC UA objects
- `override_store` - Fresh OverrideStore instance
- `mock_time` - Time mocking helper

## Test Results

Latest run: **297 tests passed** (100% success rate)

- test_data_loading.py: 31 passed
- test_injection_handler.py: 18 passed  
- test_nodeid_functions.py: 31 passed
- test_override_store.py: 21 passed
- test_type_casting.py: 41 passed

Run time: ~0.6 seconds (all tests are fast with mocked dependencies)

## Integration Tests

Integration tests are in [tests/integration/](integration/) and test the full system with a real OPC UA server:

- `test_override.py` - Full override injection workflow
- `test_client.py` - OPC UA client connection and tag monitoring  
- `test_load_logic.py` - Data loading validation

These are part of the pytest suite and run automatically with `uv run pytest tests/`.
