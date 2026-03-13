# GitHub Copilot Instructions for OPC Replay

## Project Overview

OPC Replay is a Python-based OPC UA replay server for replaying historical timestamped tag data from CSV or Parquet files. It's designed for testing, simulation, and development scenarios where you need to reproduce specific OPC UA data sequences.

**Core Features:**
- Replay historical data from CSV/Parquet files with configurable speed (1x to 100x+)
- Auto-generate OPC UA NodeSets from data files
- Real-time tag injection via HTTP REST API
- Proper OPC UA timestamps and namespace remapping

## Technology Stack

- **Language:** Python 3.13+ (minimum version enforced)
- **OPC UA Library:** `opcua` (python-opcua)
- **Data Processing:** `pandas`, `pyarrow`
- **Testing:** `pytest`, `pytest-mock`
- **Code Quality:** `ruff` (linting and formatting)
- **Package Management:** `uv`
- **Build System:** `hatchling`

## Code Style & Conventions

### General Guidelines
- Follow PEP 8 conventions (enforced by ruff)
- Use type hints for all function parameters and return values
- Maximum line length: 100 characters
- Target version: Python 3.13

### Naming Conventions
- **Functions/Variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private members:** Prefix with single underscore `_private_method`

### Documentation
- Add docstrings to all public APIs (modules, classes, functions)
- Use triple quotes `"""` for docstrings
- Include usage examples for CLI commands in docstrings

### Type Hints
Always use type hints:
```python
def load_data(file_path: str, ts_col: str) -> pd.DataFrame:
    """Load data from CSV or Parquet file."""
    pass
```

### Linting & Formatting
- Use `uv run ruff check .` to lint code
- Use `uv run ruff format .` to format code
- Ruff is configured in `[tool.ruff]` section of `pyproject.toml`
- Enabled rules: pycodestyle (E/W), pyflakes (F), isort (I), flake8-bugbear (B), comprehensions (C4), pyupgrade (UP)

### Multi-Platform Compatibility
- **CRITICAL**: Avoid Unicode characters (✓, ✗, →, ⚠️, 🚀, 🛑, etc.) in `print()` statements
- Windows console uses cp1252 encoding which cannot render these characters
- Use ASCII alternatives: `[OK]`, `[ERROR]`, `[WARNING]`, `->`, `[*]`, `[!]`
- Unicode in comments is fine, but not in runtime output
- Test on multiple platforms (Linux, macOS, Windows) via GitHub Actions

## Project Architecture

### Core Modules

1. **`opc_replay/__init__.py`**
   - Package entry point
   - CLI command: `opc-replay`
   - Handles argument parsing for the main replay server

2. **`opc_replay/server.py`**
   - Main OPC UA server implementation
   - Data loading from CSV/Parquet files
   - Replay logic with speed control and looping
   - HTTP REST API for tag injection
   - Namespace remapping and NodeSet import

3. **`opc_replay/client.py`**
   - Basic OPC UA client for monitoring
   - CLI command: `opc-client`
   - Subscribes to tag updates and displays values

4. **`opc_replay/inject_tags.py`**
   - Tag injection CLI
   - CLI command: `opc-inject`
   - Sends injection requests to the server's REST API

5. **`opc_replay/to_nodeset.py`**
   - NodeSet XML generation utilities
   - Creates OPC UA address space from data files
   - Handles namespace definitions and node creation

### Key Concepts

**OPC UA Node IDs:**
- Format: `ns=<namespace>;s=<identifier>` (e.g., `ns=2;s=Temperature`)
- Namespace 0: OPC UA base namespace
- Namespace 1: Server namespace
- Namespace 2+: Custom namespaces (typically data tags)

**Variant Types:**
- Maps string data types to OPC UA VariantType enum
- Defined in `VARIANT_TYPE` dictionary in `server.py`
- Supported types: Boolean, SByte, Byte, Int16, UInt16, Int32, UInt32, Int64, UInt64, Float, Double, String, DateTime

**Timestamp Handling:**
- Data files must have a timestamp column specified via `--ts-col`
- Uses pandas datetime parsing
- Maintains original timestamps for OPC UA SourceTimestamp
- Uses current time for ServerTimestamp

**Tag Injection/Override:**
- HTTP POST to `/inject` endpoint
- Can schedule activation for future time
- Supports temporary overrides with automatic expiration
- Cleared via `/clear` endpoint

## Testing Strategy

### Test Organization

**Unit Tests (`tests/unit/`)**
- Fast tests (~0.6 seconds total)
- Use mocks and fixtures
- Test individual functions and classes in isolation
- Marked with `@pytest.mark.unit`

**Integration Tests (`tests/integration/`)**
- Slower tests (start actual OPC UA server)
- Test full system behavior
- Use fixtures in `tests/integration/fixtures/`
- Marked with `@pytest.mark.integration`

### Test Fixtures

Located in `tests/*/conftest.py`:
- Shared fixtures for setup/teardown
- Mock data generators
- OPC UA server/client instances

Test data in `tests/integration/fixtures/`:
- `test-data.csv`: Sample time-series data
- Used by integration tests

### Running Tests

```bash
# All tests (using uv)
uv run pytest tests/

# Unit tests only (fast)
uv run pytest tests/unit -v

# Integration tests only
uv run pytest tests/integration -v

# Specific test file
uv run pytest tests/unit/test_data_loading.py -v

# Run CI checks locally
./scripts/run_ci_locally.sh
```

### Writing New Tests

- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Use `pytest.fixture` for reusable setup
- Mock external dependencies (OPC UA server, file I/O) in unit tests
- Use `pytest.mark` decorators for test categorization
- Follow AAA pattern: Arrange, Act, Assert

Example:
```python
@pytest.mark.unit
def test_load_csv_data_with_valid_file_returns_dataframe(tmp_path):
    # Arrange
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("TS,Tag1\n2024-01-01 00:00:00,42.0\n")
    
    # Act
    df = load_data(str(csv_file), ts_col="TS")
    
    # Assert
    assert len(df) == 1
    assert "Tag1" in df.columns
```

## Common Patterns

### Loading Data Files

```python
def load_data(file_path: str, ts_col: str) -> pd.DataFrame:
    """Load CSV or Parquet file and parse timestamp column."""
    if file_path.endswith('.parquet'):
        df = pd.read_parquet(file_path)
    else:
        df = pd.read_csv(file_path)
    
    # Parse timestamp column
    df[ts_col] = pd.to_datetime(df[ts_col])
    return df
```

### Creating OPC UA Variables

```python
# Get or create folder structure
folder = get_or_create_folder(server, parent, folder_name)

# Add variable with data type
var = folder.add_variable(
    f"ns={namespace};s={tag_name}",
    tag_name,
    initial_value,
    varianttype=variant_type
)
var.set_writable()  # Allow writes for injection
```

### Thread-Safe Tag Injection

```python
# Use threading.Lock for concurrent access
injection_lock = threading.Lock()
injection_store = {}  # Thread-safe with lock

with injection_lock:
    injection_store[node_id] = {
        "value": value,
        "activate_at": activate_time,
        "expire_at": expire_time
    }
```

### Error Handling

```python
try:
    # OPC UA operations
    server.start()
except Exception as e:
    print(f"Error starting OPC UA server: {e}")
    server.stop()
    raise
```

## CLI Commands & Entry Points

All three commands are defined in `[project.scripts]` in `pyproject.toml`:

### `opc-replay`
Main replay server:
```bash
opc-replay --data mydata.csv --ts-col TS --auto-nodeset [--speed 10] [--loop] [--offset 3600]
```

### `opc-client`
Monitoring client:
```bash
opc-client [--endpoint opc.tcp://localhost:4840]
```

### `opc-inject`
Tag injection:
```bash
opc-inject --tag "ns=2;s=Temperature" --value 99.9 [--duration 30] [--delay 5]
```

## Development Workflow

### Setup
```bash
# Clone and install
git clone https://github.com/mieslep/opc-replay.git
cd opc-replay
uv sync  # or: pip install -e .

# Verify installation
./scripts/test_install.sh
```

### Before Committing
```bash
# Run all CI checks locally
./scripts/run_ci_locally.sh

# Or run individually (always use 'uv run'):
uv run ruff check . --fix
uv run ruff format .
uv run pytest tests/
```

### Making Changes
1. Create feature branch
2. Make changes with type hints and docstrings
3. Write/update tests (aim for unit tests when possible)
4. Run `./scripts/run_ci_locally.sh`
5. Commit and push
6. Open Pull Request

## Dependencies & Imports

### Core Dependencies
```python
import pandas as pd              # Data manipulation
from opcua import Server, ua     # OPC UA server and types
import threading                 # Thread-safe operations
from datetime import datetime    # Timestamp handling
import argparse                  # CLI argument parsing
```

### Conditional Imports
- CSV: `pd.read_csv()`
- Parquet: `pd.read_parquet()` (requires pyarrow)

### Testing Dependencies
```python
import pytest                    # Test framework
from pytest_mock import mocker   # Mocking utilities
```

## File Format Expectations

### CSV Data Files
```csv
TS,Tag1,Tag2,Tag3
2024-01-01 00:00:00,42.0,true,hello
2024-01-01 00:00:01,43.5,false,world
```

### Parquet Data Files
- Same structure as CSV
- Timestamp column name specified via `--ts-col`

### NodeSet XML
- OPC UA NodeSet2 XML format
- Can be auto-generated with `--auto-nodeset` flag
- Created via `to_nodeset.py` utilities

### Injection JSON
```json
{
  "tag": "ns=2;s=Temperature",
  "value": 99.9,
  "duration": 30,
  "delay": 5
}
```

## Special Considerations

### Multi-Platform Compatibility (CRITICAL)
- The project runs on Linux, macOS, and Windows via GitHub Actions CI
- **Windows console uses cp1252 encoding** - it CANNOT render Unicode characters in `print()` statements
- Always use ASCII alternatives for user-facing output:
  - `[OK]` instead of ✓
  - `[ERROR]` instead of ✗
  - `[WARNING]` or `[!]` instead of ⚠️
  - `->` instead of →
  - `[*]` instead of 🚀 or 🛑
- Unicode in comments, docstrings, or file content is fine - only runtime `print()` output is problematic
- Test changes across all platforms via GitHub Actions before merging

### Python 3.13 Compatibility
- Required minimum: `requires-python = ">=3.13"`
- Be aware of deprecation warnings from `opcua` library
- Filtered in pytest config: `filterwarnings` for `datetime.datetime.utcnow()`

### Threading & Concurrency
- HTTP server runs in background thread
- Use locks for shared state (injection store)
- Server main loop runs in foreground

### Namespace Remapping
- NodeSet imports may use different namespace URIs
- Server automatically remaps to local namespace indexes
- Preserved in runtime variable metadata

### Performance
- Large datasets should use Parquet (faster loading)
- Speed parameter multiplies replay rate (e.g., 10x faster = 10)
- Integration tests may take several seconds to start servers

## Common Tasks & Hints

### Adding a New CLI Argument
1. Add to `argparse` in `__init__.py` or respective CLI file
2. Pass through to main function
3. Update README.md usage examples
4. Consider adding test coverage

### Adding a New Data Type
1. Add mapping to `VARIANT_TYPE` dictionary in `server.py`
2. Handle type casting in data loading logic
3. Add unit test in `tests/unit/test_type_casting.py` (run with `uv run pytest tests/unit/test_type_casting.py -v`)

### Adding New HTTP Endpoint
1. Add handler method in `InjectionHTTPRequestHandler` class
2. Parse request body (usually JSON)
3. Update injection store or trigger action
4. Return appropriate HTTP status and JSON response
5. Add integration test

### Debugging OPC UA Issues
- Check namespace mappings (namespace 2+ for data tags)
- Verify NodeSet XML structure if not auto-generating
- Use `opc-client` to inspect server state
- Check OPC UA timestamps (SourceTimestamp vs ServerTimestamp)

## Documentation Files

- **README.md**: User-facing documentation, installation, usage
- **CONTRIBUTING.md**: Development setup, testing, code quality guidelines
- **tests/README.md**: Testing strategy and guidelines
- **examples/README.md**: Example usage scenarios
- **CHANGELOG.md**: Version history and changes

## When Suggesting Code

1. **Respect existing patterns**: Follow established code structure
2. **Include type hints**: All new functions should have type annotations
3. **Add tests**: Suggest both unit and integration tests when appropriate
4. **Consider thread safety**: Use locks for shared state
5. **Handle errors gracefully**: Don't let OPC UA errors crash the server
6. **Update documentation**: Mention if README or docstrings need updates
7. **Check ruff compliance**: Ensure suggestions follow ruff rules (use `uv run ruff check .`)
8. **Use Python 3.13 features**: Leverage modern Python syntax when beneficial
9. **Multi-platform compatibility**: Avoid Unicode characters in print statements - use ASCII alternatives like `[OK]`, `[ERROR]`, `[WARNING]` instead of ✓, ✗, ⚠️

## Quick Reference

**Main entry point:** `opc_replay/__init__.py:main()`  
**OPC UA server logic:** `opc_replay/server.py`  
**Test everything:** `./scripts/run_ci_locally.sh`  
**Format code:** `uv run ruff format .`  
**Lint code:** `uv run ruff check . --fix`  
**Run tests:** `uv run pytest tests/`  
**Package config:** `pyproject.toml`

## Command Line Tool Usage

Always use `uv run` to execute development tools and tests:
- `uv run ruff check .` - Lint code
- `uv run ruff format .` - Format code  
- `uv run pytest tests/` - Run tests
- `uv sync` - Install/sync dependencies

For production CLI tools (after installation):
- `opc-replay --data file.csv --ts-col TS` - Start replay server
- `opc-client` - Monitor OPC UA server
- `opc-inject --tag "ns=2;s=Tag" --value 123` - Inject tag values
