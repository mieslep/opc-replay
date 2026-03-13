# Contributing to OPC Replay

## Development Setup

### Prerequisites

- Python >= 3.13
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Getting Started

1. **Clone the repository:**

   ```bash
   git clone https://github.com/mieslep/opc-replay.git
   cd opc-replay
   ```

2. **Install dependencies:**

   With uv (recommended):
   ```bash
   uv sync
   ```

   Or with pip:
   ```bash
   pip install -e .
   ```

3. **Verify installation:**

   ```bash
   ./scripts/test_install.sh
   ```

## Development Workflow

### Running Tests

We have comprehensive unit and integration tests. Run all tests:

```bash
uv run pytest tests/
```

Run specific test suites:

```bash
# Unit tests only (fast, ~0.6 seconds)
uv run pytest tests/unit -v

# Integration tests only (slower, starts OPC UA server)
uv run pytest tests/integration -v
```

For detailed testing information, see [tests/README.md](tests/README.md).

### Code Quality

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

**Check code quality:**

```bash
uv run ruff check .
```

**Auto-fix issues:**

```bash
uv run ruff check . --fix
```

**Check formatting:**

```bash
uv run ruff format --check .
```

**Auto-format code:**

```bash
uv run ruff format .
```

### Running CI Checks Locally

Before submitting a pull request, run all CI checks locally:

```bash
./scripts/run_ci_locally.sh
```

This script runs the same checks as our GitHub Actions CI:
- Unit tests
- Integration tests
- Linting
- Format checking
- Package building

## Making Changes

Follow PEP 8 conventions (enforced by ruff), use type hints, and add docstrings to public APIs. Write tests for new features - unit tests use mocks, integration tests validate the full system.

## Submitting Pull Requests

1. Create a feature branch and make your changes
2. Run `./scripts/run_ci_locally.sh` to verify tests and linting pass
3. Push your branch and open a Pull Request with a clear description
4. Respond to code review feedback

## Project Structure

```
opc-replay/
├── opc_replay/          # Main package source code
│   ├── __init__.py      # Package entry point (opc-replay command)
│   ├── server.py        # OPC UA server implementation
│   ├── client.py        # OPC UA client (opc-client command)
│   ├── inject_tags.py   # Tag injection CLI (opc-inject command)
│   └── to_nodeset.py    # NodeSet generation utilities
├── tests/               # Test suite
│   ├── unit/            # Fast unit tests with mocks
│   └── integration/     # Full system integration tests
├── examples/            # Sample data and usage examples
├── scripts/             # Development and utility scripts
├── .github/             # GitHub Actions CI/CD workflows
└── docs/                # Additional documentation
```
