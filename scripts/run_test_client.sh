#!/bin/bash
# Quick launcher for the MCP Test Client
# This script activates the virtual environment and runs the test client

echo "========================================"
echo "IBM MQ MCP Server - Test Client Launcher"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -f "../venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    echo "Then run: source venv/bin/activate"
    echo "Then run: pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source ../venv/bin/activate

# Check if dependencies are installed
python -c "import mcp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Dependencies not installed!"
    echo "Installing dependencies..."
    pip install -r ../requirements.txt
    echo ""
fi

# Run the test client
echo ""
echo "Starting interactive test client..."
echo ""
python ../clients/test_mcp_client.py

# Deactivate virtual environment
deactivate

echo ""
