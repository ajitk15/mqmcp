#!/bin/bash

# Launcher for Streamlit Remote MQ Assistant
echo "==========================================="
echo "Starting Streamlit Remote MQ Assistant..."
echo "==========================================="
echo ""

# Check if venv exists
if [ -f "../venv/bin/activate" ]; then
    VENV_PATH="../venv/bin/activate"
elif [ -f "../venv/Scripts/activate" ]; then
    VENV_PATH="../venv/Scripts/activate"
else
    echo "ERROR: Virtual environment not found in root!"
    echo "Please run setup first."
    read -n 1 -s -r -p "Press any key to continue..."
    echo ""
    exit 1
fi

# Activate venv and run streamlit
source "$VENV_PATH"
streamlit run ../clients/streamlit_remote_client.py --server.port 8506

read -n 1 -s -r -p "Press any key to continue..."
echo ""
