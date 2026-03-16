#!/usr/bin/env bash
#
# Check that version numbers are consistent across project files.
# This script verifies that pyproject.toml and opc_replay/__init__.py
# have matching version strings to prevent version drift.
#
# Exit codes:
#   0 - Versions match
#   1 - Versions mismatch or file read error

set -e

# Color output (only if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

echo "Checking version consistency..."

# Extract version from pyproject.toml
PYPROJECT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
if [ -z "$PYPROJECT_VERSION" ]; then
    echo -e "${RED}[ERROR]${NC} Failed to extract version from pyproject.toml"
    exit 1
fi

# Extract version from opc_replay/__init__.py
INIT_VERSION=$(grep '^__version__ = ' opc_replay/__init__.py | sed 's/__version__ = "\(.*\)"/\1/')
if [ -z "$INIT_VERSION" ]; then
    echo -e "${RED}[ERROR]${NC} Failed to extract version from opc_replay/__init__.py"
    exit 1
fi

# Compare versions
if [ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]; then
    echo -e "${RED}[ERROR]${NC} Version mismatch detected:"
    echo "  pyproject.toml:           $PYPROJECT_VERSION"
    echo "  opc_replay/__init__.py:   $INIT_VERSION"
    echo ""
    echo "These versions must match. Update opc_replay/__init__.py to match pyproject.toml."
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Version consistency check passed: $PYPROJECT_VERSION"
exit 0
