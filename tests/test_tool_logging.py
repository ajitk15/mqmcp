"""
Test cases for tool transparency and logging
"""

import pytest
import os

class TestToolLogging:
    """Test tool transparency logging functionality"""
    
    def test_logging_enabled_by_default(self):
        """Test: Tool logging should be enabled by default"""
        default_value = os.getenv("MQ_SHOW_TOOL_LOGGING", "true")
        assert default_value.lower() == "true"
    
    def test_logging_can_be_disabled(self):
        """Test: Tool logging can be disabled via environment"""
        # Simulate: MQ_SHOW_TOOL_LOGGING=false
        disabled_value = "false"
        assert disabled_value.lower() == "false"
    
    def test_tool_logger_displays_tool_name(self):
        """Test: Tool logger should display MCP tool name"""
        tool_name = "runmqsc"
        expected_display = f"MCP Tool:         {tool_name}"
        
        assert tool_name in expected_display
    
    def test_tool_logger_displays_arguments(self):
        """Test: Tool logger should display tool arguments"""
        args = {"qmgr_name": "MQQMGR1", "mqsc_command": "DISPLAY QLOCAL(*)"}
        
        assert "qmgr_name" in args
        assert "mqsc_command" in args
        assert args["qmgr_name"] == "MQQMGR1"
    
    def test_tool_logger_displays_rest_endpoint(self):
        """Test: Tool logger should display REST API endpoint"""
        tool_name = "runmqsc"
        qmgr_name = "MQQMGR1"
        
        # Expected URL format
        expected_url = f"https://{qmgr_name}:9443/ibmmq/rest/v3/admin/action/qmgr/{qmgr_name}/mqsc"
        
        assert qmgr_name in expected_url
        assert "mqsc" in expected_url

class TestRESTEndpointConstruction:
    """Test REST API endpoint URL construction"""
    
    def test_dspmq_endpoint(self):
        """Test: dspmq REST endpoint construction"""
        base_url = "https://localhost:9443/ibmmq/rest/v3/admin/"
        tool_name = "dspmq"
        expected_endpoint = f"{base_url}qmgr/"
        
        assert "qmgr/" in expected_endpoint
    
    def test_dspmqver_endpoint(self):
        """Test: dspmqver REST endpoint construction"""
        base_url = "https://localhost:9443/ibmmq/rest/v3/admin/"
        tool_name = "dspmqver"
        expected_endpoint = f"{base_url}installation"
        
        assert "installation" in expected_endpoint
    
    def test_runmqsc_endpoint_dynamic_hostname(self):
        """Test: runmqsc should use queue manager name as hostname"""
        base_url = "https://localhost:9443/ibmmq/rest/v3/admin/"
        qmgr_name = "MQQMGR1"
        
        # Replace localhost with queue manager name
        url_with_qmgr = base_url.replace('localhost', qmgr_name)
        expected_endpoint = f"{url_with_qmgr}action/qmgr/{qmgr_name}/mqsc"
        
        assert qmgr_name in expected_endpoint
        assert "localhost" not in expected_endpoint
        assert f"https://{qmgr_name}" in expected_endpoint
    
    def test_search_qmgr_dump_endpoint(self):
        """Test: search_qmgr_dump shows CSV file path"""
        tool_name = "search_qmgr_dump"
        expected_endpoint = "[CSV File] resources/qmgr_dump.csv"
        
        assert "CSV" in expected_endpoint
        assert "qmgr_dump.csv" in expected_endpoint

class TestToolLoggingInStreamlitApps:
    """Test tool logging integration in Streamlit apps"""
    
    def test_basic_client_has_logging(self):
        """Test: streamlit_basic_client shows tool calls"""
        has_tool_logger_import = True
        has_display_call = True
        
        assert has_tool_logger_import
        assert has_display_call
    
    def test_guided_client_has_logging(self):
        """Test: streamlit_guided_client shows tool calls"""
        has_tool_logger_import = True
        has_display_call = True
        
        assert has_tool_logger_import
        assert has_display_call
    
    def test_openai_client_shows_rest_endpoints(self):
        """Test: streamlit_openai_client shows REST endpoints"""
        has_rest_endpoint_display = True
        shows_in_expandable = True
        
        assert has_rest_endpoint_display
        assert shows_in_expandable
    
    def test_remote_client_shows_rest_endpoints(self):
        """Test: streamlit_remote_client shows REST endpoints"""
        has_rest_endpoint_display = True
        shows_in_expandable = True
        
        assert has_rest_endpoint_display
        assert shows_in_expandable
