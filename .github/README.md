# GitHub Actions CI/CD

This repository uses GitHub Actions for continuous integration and deployment.

## Workflows

### CI Workflow (`.github/workflows/ci.yml`)

Runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

1. **test** - Runs on Ubuntu, Windows, and macOS with Python 3.13
   - Unit tests
   - Integration tests

2. **lint** - Code quality checks with ruff
   - Linting
   - Format checking

3. **build** - Build the package
   - Creates source distribution and wheel
   - Uploads artifacts for verification

### Publish Workflow (`.github/workflows/publish.yml`)

Runs on:
- GitHub release publication
- Manual trigger via workflow_dispatch

**Jobs:**

1. **publish** - Publishes package to PyPI
   - Uses trusted publishing (recommended)
   - Or can use PyPI API token

## Setup Instructions

### For CI Testing

No setup required - the CI workflow will run automatically on push and pull requests.

### For PyPI Publishing

You have two options:

#### Option 1: Trusted Publishing (Recommended)

1. Go to [PyPI](https://pypi.org/) and log in
2. Navigate to your project settings
3. Add a "Trusted Publisher" for GitHub Actions:
   - Owner: your-username
   - Repository: opc-replay
   - Workflow: publish.yml
   - Environment: (leave empty)

#### Option 2: API Token

1. Generate an API token on [PyPI](https://pypi.org/)
2. Add it to your GitHub repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Create a new secret named `PYPI_API_TOKEN`
   - Paste your PyPI token
3. Uncomment the password line in `publish.yml`

## Running Locally

### Quick Method (Recommended)

Run all CI checks at once:

```bash
./run_ci_locally.sh
```

This script runs the exact same checks as the GitHub Actions CI workflow.

### Manual Method

Run checks individually:

```bash
# Run tests
uv run pytest tests/unit -v --tb=short
uv run pytest tests/integration -v --tb=short

# Run linting
uv run ruff check .
uv run ruff format --check .

# Build package
uv run python -m build
```

## Badge

Add this badge to your README.md to show CI status:

```markdown
[![CI](https://github.com/phil/opc-replay/actions/workflows/ci.yml/badge.svg)](https://github.com/phil/opc-replay/actions/workflows/ci.yml)
```
