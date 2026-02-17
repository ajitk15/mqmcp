@echo off
echo.
echo ========================================
echo  IBM MQ Remote AI Assistant
echo  Connects to remote MCP server via SSE
echo ========================================
echo.
echo Starting Streamlit Remote Client...
echo.

streamlit run clients\streamlit_remote_client.py

pause
