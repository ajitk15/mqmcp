#!/bin/bash
# Launcher for Streamlit Basic Client
echo "========================================"
echo "Starting Streamlit Basic MQ Assistant..."
echo "========================================"

# Check if venv exists
if [ -f "../venv/bin/activate" ]; then
    VENV_PATH="../venv/bin/activate"
elif [ -f "../venv/Scripts/activate" ]; then
    VENV_PATH="../venv/Scripts/activate"
else
    echo "ERROR: Virtual environment not found in root!"
    exit 1
fi

# Activate venv and run streamlit
source "$VENV_PATH"
streamlit run ../clients/streamlit_basic_client.py
