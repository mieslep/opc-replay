# Contributing to OPC Replay

Thank you for your interest in contributing to opc-replay! This guide will help you get started with development.

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
pytest tests/
```

Run specific test suites:

```bash
# Unit tests only (fast, ~0.6 seconds)
pytest tests/unit -v

# Integration tests only (require OPC UA server)
pytest tests/integration -v
```

For detailed testing information, see [tests/README.md](tests/README.md).

### Code Quality

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

**Check code quality:**

```bash
ruff check .
```

**Auto-fix issues:**

```bash
ruff check . --fix
```

**Check formatting:**

```bash
ruff format --check .
```

**Auto-format code:**

```bash
ruff format .
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

### Code Style Guidelines

- Follow PEP 8 conventions (enforced by ruff)
- Write descriptive variable and function names
- Add docstrings to public functions and classes
- Keep functions focused and reasonably sized
- Use type hints where appropriate

### Testing Guidelines

- Write tests for new features and bug fixes
- Unit tests should use mocks for external dependencies
- Integration tests should test the full system
- Aim for high test coverage of critical paths
- Tests should be fast and reliable

### Commit Messages

Write clear, descriptive commit messages:

```
Add support for Parquet data files

- Implement Parquet file reading with pyarrow
- Add auto-detection of file format from extension
- Update documentation with Parquet examples
```

## Submitting Pull Requests

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** and commit them with clear messages

3. **Run tests and linting:**

   ```bash
   ./scripts/run_ci_locally.sh
   ```

4. **Push your branch:**

   ```bash
   git push origin feature/my-new-feature
   ```

5. **Open a Pull Request** on GitHub with:
   - Clear description of the changes
   - Reference to any related issues
   - Screenshots/examples if applicable

6. **Respond to feedback** from code review

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

## Development Scripts

### scripts/generate_sample_data.py

Generate sample CSV data files for testing:

```bash
python scripts/generate_sample_data.py
```

### scripts/test_install.sh

Verify that the package is correctly installed and all commands work:

```bash
./scripts/test_install.sh
```

### scripts/run_ci_locally.sh

Run all CI checks locally:

```bash
./scripts/run_ci_locally.sh
```

## Getting Help

- **Documentation:** See [README.md](README.md) and [examples/USAGE.md](examples/USAGE.md)
- **Issues:** Browse existing [GitHub Issues](https://github.com/mieslep/opc-replay/issues)
- **Questions:** Open a new issue with the "question" label

## Code of Conduct

- Be respectful and constructive in all interactions
- Welcome newcomers and help them get started
- Focus on what is best for the project and community

## License

By contributing to opc-replay, you agree that your contributions will be licensed under the same license as the project (see [LICENSE](LICENSE)).

## Recognition

Contributors are recognized in the project's Git history and may be mentioned in release notes for significant contributions.

Thank you for contributing to opc-replay! 🚀
