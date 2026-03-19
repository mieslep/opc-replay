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
   - CLI command: `opc-replay-client`
   - Subscribes to tag updates and displays values

4. **`opc_replay/inject_tags.py`**
   - Tag injection CLI
   - CLI command: `opc-replay-inject`
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

**CRITICAL: Tests are mandatory for all code changes**

#### When to Write Unit Tests (`tests/unit/`)
- **Always** for new functions, classes, or methods
- When modifying existing logic
- For data processing, validation, type conversion
- For utility functions (NodeId parsing, timestamp handling, etc.)
- Tests should be fast (<0.1s each) and use mocks for external dependencies

#### When to Write Integration Tests (`tests/integration/`)
- New features involving OPC UA server startup
- HTTP API endpoints (injection/override functionality)
- End-to-end data replay scenarios
- File I/O operations (CSV/Parquet loading, NodeSet generation)
- Tests may be slower (1-5s each) and use real server instances

#### Test Naming and Structure
- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Use `pytest.fixture` for reusable setup
- Mock external dependencies (OPC UA server, file I/O) in unit tests
- Use `pytest.mark.unit` or `pytest.mark.integration` decorators
- Follow AAA pattern: Arrange, Act, Assert

#### Examples

**Unit Test Example:**
```python
@pytest.mark.unit
def test_canonicalize_nodeid_with_simple_name_adds_namespace():
    # Arrange
    tagname = "Temperature"
    
    # Act
    result = canonicalize_nodeid(tagname, default_ns=2)
    
    # Assert
    assert result == "ns=2;s=Temperature"
```

**Integration Test Example:**
```python
@pytest.mark.integration
def test_auto_conversion_with_real_server():
    # Arrange
    server = Server()
    server.set_endpoint("opc.tcp://0.0.0.0:4841")
    # ... setup server ...
    
    # Act
    server.start()
    node = server.get_node("ns=2;s=ConvertedTag")
    
    # Assert
    assert node is not None
    
    # Cleanup
    server.stop()
```

#### Test File Organization
- Unit test file: `tests/unit/test_<module_name>.py`
  - Example: `test_nodeid_functions.py` for functions in `server.py`
- Integration test file: `tests/integration/test_<feature_name>.py`
  - Example: `test_auto_conversion.py` for auto-conversion feature

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
uv run opc-replay --data mydata.csv --ts-col TS --auto-nodeset [--speed 10] [--loop] [--offset 3600]
```

### `opc-replay-client`
Monitoring client:
```bash
uv run opc-replay-client [--endpoint opc.tcp://localhost:4840]
```

### `opc-replay-inject`
Tag injection:
```bash
uv run opc-replay-inject --tag "ns=2;s=Temperature" --value 99.9 [--duration 30] [--delay 5]
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
3. **Create tests IMMEDIATELY** (not optional):
   - **Unit tests** for any new function, class, or logic (in `tests/unit/`)
   - **Integration tests** for features involving OPC UA server, HTTP API, or file I/O (in `tests/integration/`)
   - Update existing tests when modifying functionality
4. **Run linting after code changes**: `uv run ruff check .` (and fix any issues)
5. **Verify tests pass**: Run `uv run pytest <test_file> -v` on new/affected tests
6. Run `./scripts/run_ci_locally.sh` for final validation
7. Commit and push
8. Open Pull Request

### Copilot Workflow
When making code changes as Copilot:
1. **After editing files**: Always run `uv run ruff check <file>` to verify code quality
2. **IMMEDIATELY create tests**: 
   - Write unit tests in `tests/unit/test_<module>.py` for new functions/classes
   - Write integration tests in `tests/integration/test_<feature>.py` for end-to-end features
   - Run `uv run pytest <test_file> -v` to verify tests pass
3. **Before completing the task**: Ensure all linting passes and ALL tests work
4. Use `uv run ruff format .` if formatting issues are detected
5. **Feature is NOT complete without tests** - always create them as part of the implementation

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
  - Follow [Keep a Changelog](https://keepachangelog.com/) format
  - Keep entries concise - consolidate related changes into single bullet points
  - Use bold section headers: **Added**, **Changed**, **Fixed**, **Removed**
  - Avoid excessive detail - capture the essence of changes, not implementation specifics
  - Example: Instead of 5 bullets explaining auto-conversion, use 1 clear bullet: "**Auto-conversion of non-canonical NodeIds** - Simple tag names automatically convert to OPC UA format (use `--flag` to disable)"

## When Suggesting Code

1. **Respect existing patterns**: Follow established code structure
2. **Include type hints**: All new functions should have type annotations
3. **ALWAYS create tests** (MANDATORY):
   - **Unit tests** (in `tests/unit/`) are REQUIRED for any new function, class, or logic change
   - **Integration tests** (in `tests/integration/`) are REQUIRED for new features that involve OPC UA server, HTTP API, or file I/O
   - When modifying existing code, update or add tests to maintain coverage
   - Test file naming: `test_<module_name>.py` (e.g., `test_nodeid_functions.py` for functions in `server.py`)
   - Run tests immediately after creating them: `uv run pytest <test_file> -v`
   - Never consider a feature "complete" without accompanying tests
4. **Consider thread safety**: Use locks for shared state
5. **Handle errors gracefully**: Don't let OPC UA errors crash the server
6. **Update documentation**: Mention if README or docstrings need updates
7. **Run linting after changes**: Always run `uv run ruff check <file>` after editing code and fix any issues before proceeding
8. **Use Python 3.13 features**: Leverage modern Python syntax when beneficial
9. **Multi-platform compatibility**: Avoid Unicode characters in print statements - use ASCII alternatives like `[OK]`, `[ERROR]`, `[WARNING]` instead of ✓, ✗, ⚠️

## Release Management Workflow

### When to Create a Release

**Regular Releases:**
- All planned features/fixes for the milestone are complete
- All CI checks pass on `main` branch
- Documentation is up-to-date (README.md, CHANGELOG.md)
- No known critical bugs

**Hotfix Releases:**
- Critical bug in production that can't wait for next regular release
- Requires patch version bump (e.g., 0.10.0 → 0.10.1)
- Should be based on the release tag, not latest `main`

### Pre-Release Checklist

Before starting the release process, verify:
- [ ] All features/fixes merged to `main` via PR (not direct push)
- [ ] All CI/CD checks pass on `main`
- [ ] Documentation updated (README.md, examples/)
- [ ] CHANGELOG.md has entries in `[Unreleased]` section
- [ ] Breaking changes documented clearly
- [ ] Run `./scripts/run_ci_locally.sh` successfully
- [ ] Version numbers are in sync (checked by CI)

### Automated Release Process

**Use the release preparation script for all releases:**

```bash
./scripts/prepare_release.sh
```

The script will:
1. **Prompt for version type** - Select major/minor/patch or custom (for hotfixes)
2. **Run validation** - Tests, linting, formatting, build
3. **Update versions** - Changes `pyproject.toml` and `opc_replay/__init__.py`
4. **Update CHANGELOG** - Moves `[Unreleased]` items to versioned section
5. **Pause for review** - Shows diff, allows manual edits
6. **Create commit** - Commits with message: `Release vX.Y.Z`
7. **Create tag** - Annotated tag `vX.Y.Z`
8. **Ask to push** - Confirms before pushing (triggers pre-release-check workflow)
9. **Optional: Create GitHub Release** - If `gh` CLI is available and authenticated, offers to auto-create release with changelog
10. **Prompt for next dev version** - Updates to `X.Y.Z-dev` for continued development
11. **Commit dev version** - Prepares for next development cycle

**Human validation gates:**
- After changelog generation (review and edit if needed)
- Before creating release commit
- Before pushing tag (triggers workflows)
- Before creating GitHub Release (if using gh CLI)
- Before pushing dev version bump

**Optional: GitHub CLI Integration:**
If you have [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated, the script will offer to automatically create the GitHub Release with the changelog extracted from CHANGELOG.md. This eliminates the manual step of creating the release via GitHub UI. If `gh` is not available or you decline, the script provides manual instructions.

### Release Workflow Steps

**1. Run Release Script**
```bash
./scripts/prepare_release.sh
```

Follow the interactive prompts:
- Select release type (major/minor/patch/custom)
- Review changes to CHANGELOG.md (edit if needed)
- Confirm commit creation
- Confirm tag creation
- Confirm push to GitHub

**2. Monitor GitHub Actions**
- Wait for [pre-release-check workflow](workflows/pre-release-check.yml) to complete
- This validates version consistency and changelog
- If it fails, fix issues and re-tag

**3. Create GitHub Release**

*If using automated script with gh CLI:*
- The script will offer to create the release automatically after pushing the tag
- It extracts the changelog section and creates the release with proper title and notes
- Publishing triggers [publish workflow](workflows/publish.yml) → uploads to PyPI

*If creating manually:*
- Go to GitHub → Releases → "Draft a new release"
- Select the tag (e.g., `v0.11.0`)
- Copy changelog entry for this version as the description
- Title: `Release v0.11.0`
- Click "Publish release"
- This triggers [publish workflow](workflows/publish.yml) → uploads to PyPI

**4. Verify Publication**
- Check PyPI page: https://pypi.org/project/opc-replay/
- Test fresh install in a new environment: `pip install opc-replay==X.Y.Z`
- Verify CLI commands work after install: `opc-replay --help`, `opc-replay-client --help`, `opc-replay-inject --help`
- Back in repo, run examples: `cd examples && uv run python demo_client.py`

**5. Post-Release Tasks**
- The script already bumped to next dev version
- Announce release (if applicable)
- Close related issues/milestones
- Update external documentation if needed

### Hotfix Release Process

When you need to patch a released version without including new features from `main`:

**1. Create hotfix branch from release tag**
```bash
git checkout -b hotfix/0.10.1 v0.10.0
```

**2. Apply fixes**
- Cherry-pick commits: `git cherry-pick <commit-hash>`
- Or make fixes directly on the hotfix branch
- Update CHANGELOG.md with fix description

**3. Run release script**
```bash
./scripts/prepare_release.sh
```
- Choose option 4 (custom version)
- Enter patch version (e.g., `0.10.1`)
- Follow normal release process

**4. Merge back to main**
```bash
git checkout main
git merge hotfix/0.10.1
# Resolve any conflicts, especially in version files and CHANGELOG
git push origin main
```

**5. Tag and release**
- Follow steps 2-4 from regular release workflow

### Branch Protection & PR Workflow

**IMPORTANT:** The `main` branch should be protected to require PR reviews:

- All changes must go through Pull Requests (no direct pushes)
- Require at least 1 approval (configure in GitHub settings)
- Require status checks to pass (CI workflow)
- Only tags are allowed to be pushed directly (for releases)

**Setup Branch Protection** (repo admins only):
1. GitHub repo → Settings → Branches
2. Add rule for `main` branch:
   - ✓ Require a pull request before merging
   - ✓ Require approvals (1+)
   - ✓ Require status checks to pass
   - ✓ Require branches to be up to date
   - Select required checks: `version-check`, `test`, `lint`, `build`
3. Save changes

**Workflow:**
```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Push and create PR
git push origin feature/my-feature
# Create PR on GitHub

# After review and approval, merge via GitHub UI
# Delete feature branch after merge
```

### Version Numbering Guidelines

Follow [Semantic Versioning](https://semver.org/):

- **Major (X.0.0)**: Breaking changes (incompatible API changes)
  - Remove/rename CLI arguments
  - Change default behaviors
  - Remove deprecated features
  - Incompatible OPC UA server changes

- **Minor (0.X.0)**: New features (backward compatible)
  - Add CLI arguments/options
  - Add new functionality
  - Enhance existing features
  - Add new API endpoints

- **Patch (0.0.X)**: Bug fixes (backward compatible)
  - Fix crashes or errors
  - Correct incorrect behavior
  - Performance improvements
  - Documentation fixes

**Development versions:** Always end with `-dev` suffix (e.g., `0.11.0-dev`)

### Troubleshooting Releases

**Version mismatch detected by CI:**
```bash
./scripts/check_version_sync.sh  # See what's wrong
# Manually sync opc_replay/__init__.py with pyproject.toml
```

**Pre-release check fails:**
- Check the GitHub Actions log
- Common issues: missing CHANGELOG entry, version mismatch
- Fix locally, recommit, move tag: `git tag -f vX.Y.Z`
- Force push tag: `git push origin vX.Y.Z --force`

**Need to abort release after tagging:**
```bash
# Delete local tag
git tag -d vX.Y.Z

# Delete remote tag (if pushed)
git push origin :refs/tags/vX.Y.Z

# Revert version commits
git revert HEAD  # or git reset --hard HEAD~1 if not pushed
```

**PyPI publish failed:**
- Check [publish workflow](workflows/publish.yml) logs
- Manual publish: `uv run python -m build && twine upload dist/*`
- Set up PyPI token in GitHub secrets if trusted publishing fails

**Wrong version released:**
- Cannot delete PyPI releases (immutable)
- Immediately release corrected version with patch bump
- Mark bad version as "yanked" on PyPI (removes from default search)
- Document in CHANGELOG.md

### Manual Release (Fallback)

If the script fails, follow [RELEASE_PROCESS.md](../RELEASE_PROCESS.md) for manual steps.

Key manual steps:
1. Update `pyproject.toml` version
2. Update `opc_replay/__init__.py` `__version__`
3. Update `CHANGELOG.md` with version and date
4. Commit: `git commit -m "Release vX.Y.Z"`
5. Tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
6. Push: `git push origin HEAD && git push origin vX.Y.Z`
7. Create GitHub Release
8. Bump to dev version: `X.(Y+1).0-dev`

### Copilot Assistance for Releases

**When assisting with releases, Copilot should:**

1. **Verify pre-release checklist** - Check if all items are satisfied
2. **Run validation** - Execute `./scripts/run_ci_locally.sh`
3. **Guide through script** - Explain each step of `prepare_release.sh`
4. **Review changelog** - Ensure format follows Keep a Changelog conventions
5. **Check version consistency** - Run `./scripts/check_version_sync.sh`
6. **Validate semantic versioning** - Confirm version bump type matches changes
7. **Monitor workflows** - Check GitHub Actions status after pushing
8. **Verify PyPI** - Confirm package appears on PyPI with correct version
9. **Test installation** - Guide user through fresh install test

**Copilot should NOT:**
- Automatically push tags without user confirmation
- Skip validation checks to "save time"
- Make manual changelog edits without user review
- Proceed with release if CI checks fail

## Quick Reference

**Main entry point:** `opc_replay/__init__.py:main()`  
**OPC UA server logic:** `opc_replay/server.py`  
**Test everything:** `./scripts/run_ci_locally.sh`  
**Format code:** `uv run ruff format .`  
**Lint code:** `uv run ruff check . --fix`  
**Run tests:** `uv run pytest tests/`  
**Package config:** `pyproject.toml`

## Command Line Tool Usage

**During development** (working on the codebase), always use `uv run`:
- `uv run ruff check .` - Lint code
- `uv run ruff format .` - Format code  
- `uv run pytest tests/` - Run tests
- `uv sync` - Install/sync dependencies
- `uv run opc-replay --data file.csv --ts-col TS` - Test replay server
- `uv run opc-replay-client` - Test monitoring client
- `uv run opc-replay-inject --tag "ns=2;s=Tag" --value 123` - Test tag injection

**After installation** (for end users via pip install):
- `opc-replay --data file.csv --ts-col TS` - Start replay server
- `opc-replay-client` - Monitor OPC UA server
- `opc-replay-inject --tag "ns=2;s=Tag" --value 123` - Inject tag values
