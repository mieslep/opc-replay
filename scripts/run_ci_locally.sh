#!/bin/bash
# Run all CI/CD checks locally (same as GitHub Actions)

set -e  # Exit on any error

echo "[*] Checking Version Consistency..."
./scripts/check_version_sync.sh

echo ""
echo "[*] Running Unit Tests..."
uv run pytest tests/unit -v --tb=short

echo ""
echo "[*] Running Integration Tests..."
uv run pytest tests/integration -v --tb=short

echo ""
echo "[*] Running Linting..."
uv run ruff check .

echo ""
echo "[*] Checking Formatting..."
uv run ruff format --check .

echo ""
echo "[*] Building Package..."
uv run python -m build

echo ""
echo "[OK] All CI/CD checks passed! Ready to push."

