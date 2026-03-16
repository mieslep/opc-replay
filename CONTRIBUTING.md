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

## Branch Protection & Workflow

### Overview

The `main` branch is the primary development branch and should be protected to maintain code quality. All changes must go through Pull Requests with review and CI checks before merging.

### Branch Protection Rules

**For Repository Administrators:**

The `main` branch should have the following protection rules enabled on GitHub:

1. **GitHub UI Setup:**
   - Navigate to: Repository → Settings → Branches
   - Click "Add branch protection rule"
   - Branch name pattern: `main`
   
2. **Required Settings:**
   - ✓ **Require a pull request before merging**
     - Require approvals: 1 or more
     - Dismiss stale reviews when new commits are pushed
   - ✓ **Require status checks to pass before merging**
     - Require branches to be up to date before merging
     - Required status checks: `version-check`, `test`, `lint`, `build`
   - ✓ **Do not allow bypassing the above settings** (recommended)
   - ✓ **Allow force pushes** - Only for: Tags only
   
3. **Additional Recommended Settings:**
   - ✓ Require linear history (prevents merge commits)
   - ✓ Require deployments to succeed before merging (if applicable)

**Via GitHub CLI (alternative):**
```bash
# Enable branch protection
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["version-check","test","lint","build"]}' \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field enforce_admins=true \
  --field restrictions=null
```

### Development Workflow

**Standard Feature Development:**

```bash
# 1. Start from latest main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/my-feature-name

# 3. Make changes and commit
git add .
git commit -m "Add feature description"

# 4. Run CI checks locally
./scripts/run_ci_locally.sh

# 5. Push branch to GitHub
git push origin feature/my-feature-name

# 6. Create Pull Request on GitHub
# - Add clear title and description
# - Link related issues if applicable
# - Wait for CI checks to pass
# - Request review from maintainers

# 7. After approval and passing checks, merge via GitHub UI
# - Use "Squash and merge" or "Merge commit" as preferred
# - Delete the feature branch after merging
```

**Hotfix Workflow:**

For urgent fixes that need to be released quickly:

```bash
# 1. Create hotfix branch from the release tag
git checkout -b hotfix/0.10.1 v0.10.0

# 2. Make fix and test thoroughly
git add .
git commit -m "Fix critical bug description"

# 3. Push and create PR targeting main
git push origin hotfix/0.10.1

# 4. After review and merge, create hotfix release
./scripts/prepare_release.sh  # Select custom version

# 5. Ensure hotfix is merged back to main
git checkout main
git merge hotfix/0.10.1
git push origin main
```

### Exceptions & Special Cases

**Release Tags:**
- Tags are allowed to be pushed directly (not subject to PR workflow)
- Only maintainers should push tags
- Use `./scripts/prepare_release.sh` which handles tagging automatically

**Emergency Access:**
- Repository administrators can bypass branch protection if absolutely necessary
- Document the reason for bypass in commit messages
- Create a follow-up PR to review the emergency changes

### Why Branch Protection?

Branch protection ensures:
- **Code quality** - All code is reviewed and tested before merging
- **Collaboration** - Team members review each other's work
- **Documentation** - PR descriptions provide context for changes
- **Safety** - Prevents accidental force pushes or deletions
- **CI/CD** - Automated checks must pass before merging
- **History** - Clean, reviewable commit history

## Submitting Pull Requests

1. Create a feature branch and make your changes
2. Run `./scripts/run_ci_locally.sh` to verify tests and linting pass
3. Push your branch and open a Pull Request with a clear description
4. Respond to code review feedback

## Releases

Releases are managed by project maintainers and follow a documented process including version bumping, CHANGELOG updates, and automated PyPI publication. For complete details, see [RELEASE_PROCESS.md](RELEASE_PROCESS.md).

Contributors should focus on submitting well-tested, documented pull requests. Release timing and versioning decisions are made by maintainers.

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
