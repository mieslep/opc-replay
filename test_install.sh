#!/bin/bash
# Quick test script to verify the OPC Replay server installation

echo "🧪 Testing OPC Replay Server Installation..."
echo ""

# Test 1: Check uv is available
echo "✓ Checking if uv is available..."
if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Please install uv first: https://github.com/astral-sh/uv"
    exit 1
fi
echo "✓ uv found"
echo ""

# Test 2: Help works
echo "✓ Testing opc-replay --help..."
if ! uv run opc-replay --help > /dev/null 2>&1; then
    echo "❌ opc-replay --help failed"
    echo "   Try running: uv sync"
    exit 1
fi
echo "✓ Help option works"
echo ""

# Test 3: Example files exist
echo "✓ Checking example files..."
if [ ! -f "examples/simple-nodeset.xml" ]; then
    echo "❌ Example NodeSet file missing"
    exit 1
fi
if [ ! -f "examples/simple-data.csv" ]; then
    echo "❌ Example CSV file missing"
    exit 1
fi
echo "✓ Example files present"
echo ""

echo "✅ All tests passed!"
echo ""
echo "To run the replay server with example data:"
echo ""
echo "  uv run opc-replay \\"
echo "      --nodeset examples/simple-nodeset.xml \\"
echo "      --data examples/simple-data.csv \\"
echo "      --ts-col TS \\"
echo "      --speed 10 \\"
echo "      --max-rows 10"
echo ""
echo "Then connect an OPC UA client to: opc.tcp://localhost:4840/"
