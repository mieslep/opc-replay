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

### Manual Release Process (Required with Branch Protection)

Since the repository has branch protection requiring PRs, the release process must be done manually through feature branches. The `prepare_release.sh` script is available for reference but assumes direct push access to `main`.

### Release Workflow Steps

**IMPORTANT:** With branch protection enabled, releases must go through PRs. The workflow is:
1. Create release branch with version updates → PR to main → merge
2. Tag the merged commit on main → push tag
3. Create GitHub Release → triggers PyPI publish
4. Create dev version bump branch → PR to main → merge

**1. Prepare Release Branch**
```bash
# Ensure you're on updated main
git checkout main
git pull origin main

# Create release branch
git checkout -b release/v0.X.Y

# Update versions to 0.X.Y (remove -dev suffix)
# Edit: pyproject.toml, opc_replay/__init__.py

# Update CHANGELOG.md:
# - Change [Unreleased] to [0.X.Y] - YYYY-MM-DD
# - Add new empty [Unreleased] section above it
# - Update version comparison links

# Verify consistency
./scripts/check_version_sync.sh

# Commit
git add -A
git commit -m "Release v0.X.Y"

# Push and create PR
git push origin release/v0.X.Y
# Create PR on GitHub: release/v0.X.Y → main
```

**2. After PR Merged, Tag the Release**
```bash
# Switch to main and pull the merged changes
git checkout main
git pull origin main

# Create and push annotated tag
git tag -a v0.X.Y -m "Release v0.X.Y"
git push origin v0.X.Y
```

**3. Monitor GitHub Actions**
- Wait for [pre-release-check workflow](workflows/pre-release-check.yml) to complete
- This validates version consistency and changelog
- If it fails, fix issues and re-tag

**4. Create GitHub Release**

*Manually via GitHub UI:*
- Go to GitHub → Releases → "Draft a new release"
- Select the tag (e.g., `v0.11.0`)
- Title: `Release v0.11.0`
- Copy the v0.X.Y section from CHANGELOG.md as the description
- Click "Publish release"
- This triggers [publish workflow](workflows/publish.yml) → uploads to PyPI

**5. Verify Publication**
- Check PyPI page: https://pypi.org/project/opc-replay/
- Test fresh install in a new environment: `pip install opc-replay==X.Y.Z`
- Verify CLI commands work after install: `opc-replay --help`, `opc-replay-client --help`, `opc-replay-inject --help`
- Back in repo, run examples: `cd examples && uv run python demo_client.py`

**6. Bump to Next Dev Version**
```bash
# Create dev version branch
git checkout main
git pull origin main
git checkout -b bump-dev-version

# Update versions to 0.(X+1).0-dev
# Edit: pyproject.toml, opc_replay/__init__.py

# Verify and commit
./scripts/check_version_sync.sh
git add -A
git commit -m "Bump version to 0.(X+1).0-dev"

# Push and create PR
git push origin bump-dev-version
# Create PR on GitHub: bump-dev-version → main
```

**7. Post-Release Tasks**
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

**IMPORTANT:** The `main` branch is protected and requires PR reviews:

- All changes must go through Pull Requests (no direct pushes)
- Require at least 1 approval (configure in GitHub settings)
- Require status checks to pass (CI workflow)
- Tags can be pushed directly after the release PR is merged

**Release Workflow with Branch Protection:**
1. Create feature/release branch from `main`
2. Make changes and commit
3. Push branch and create PR to `main`
4. Get approval and merge PR
5. For releases: checkout `main`, pull, tag, push tag

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

### Troubleshooting Releases

**Version mismatch detected by CI:**
```bash
./scripts/check_version_sync.sh  # See what's wrong
# Manually sync opc_replay/__init__.py with pyproject.toml
```

**Pre-release check fails:**
- Check the GitHub Actions log
- Common issues: missing CHANGELOG entry, version mismatch
- Fix in release branch, update PR, re-merge
- If tag was pushed, delete and recreate: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
- After fix merged, re-tag on main: `git checkout main && git pull && git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z`

**Need to abort release after tagging:**
```bash
# Delete local tag
git tag -d vX.Y.Z

# Delete remote tag (if pushed)
git push origin :refs/tags/vX.Y.Z

# If needed, revert the release PR merge via GitHub UI
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

### Copilot Assistance for Releases

**When assisting with releases, Copilot should:**

1. **Verify pre-release checklist** - Check if all items are satisfied
2. **Run validation** - Execute `./scripts/run_ci_locally.sh`
3. **Guide through manual PR-based workflow** - Follow the branch protection workflow (release branch → PR → merge → tag on main → dev version branch → PR)
4. **Create release branches** - Use naming convention `release/v0.X.Y` and `bump-dev-version`
5. **Update files correctly** - Modify pyproject.toml, __init__.py, and CHANGELOG.md with proper formatting
6. **Review changelog** - Ensure format follows Keep a Changelog conventions
7. **Check version consistency** - Run `./scripts/check_version_sync.sh` after each version update
8. **Validate semantic versioning** - Confirm version bump type matches changes (breaking = minor, fixes = patch in 0.x)
9. **Create commits** - Use conventional messages: "Release v0.X.Y" and "Bump version to 0.X.Y-dev"
10. **Guide PR creation** - Remind user to push branches and create PRs before tagging
11. **Monitor workflows** - Check GitHub Actions status after tag is pushed
12. **Verify PyPI** - Confirm package appears on PyPI with correct version after release
13. **Test installation** - Guide user through fresh install test

**Copilot should NOT:**
- Push to `main` directly (violates branch protection)
- Create tags before the release PR is merged
- Automatically push branches/tags without user confirmation
- Skip validation checks to "save time"
- Make manual changelog edits without user review
- Proceed with release if CI checks fail
- Use the `prepare_release.sh` script (it assumes direct push access to main)

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
