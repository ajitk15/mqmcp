"""
Tool logging utilities for Streamlit applications.

Provides reusable functions to display MCP tool calls with REST API endpoints.
Configurable via MQ_SHOW_TOOL_LOGGING environment variable.
"""

import os

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False


def should_show_logging() -> bool:
    """Check if tool logging should be displayed based on environment variable."""
    return os.getenv("MQ_SHOW_TOOL_LOGGING", "true").lower() == "true"


def get_rest_api_url(tool_name: str, args: dict) -> str:
    """
    Construct the IBM MQ REST API URL for a given tool call.

    Matches the logic from DynamicMQClient._get_rest_api_url() to ensure consistency.

    Args:
        tool_name: Name of the MCP tool being called
        args: Arguments passed to the tool

    Returns:
        REST API endpoint URL or file path for CSV-based tools
    """
    base_url = os.getenv("MQ_URL_BASE", "https://localhost:9443/ibmmq/rest/v3/admin/")

    if tool_name == "dspmq":
        return f"{base_url}qmgr/"
    elif tool_name == "dspmqver":
        return f"{base_url}installation"
    elif tool_name == "runmqsc":
        qmgr = args.get('qmgr_name', 'UNKNOWN')
        url_with_qmgr_host = base_url.replace('localhost', qmgr)
        return f"{url_with_qmgr_host}action/qmgr/{qmgr}/mqsc"
    elif tool_name == "search_qmgr_dump":
        return "[CSV File] resources/qmgr_dump.csv"
    else:
        return "Unknown endpoint"
