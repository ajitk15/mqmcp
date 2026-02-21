@echo off
setlocal
cd /d "%~dp0"
cd ..\clients

echo Starting Streamlit Client (SSE)...
echo Ensure the MCP Server is running first! (run_mq_api.bat -^> Option 1)
echo.

streamlit run streamlit_sse_client.py --server.port 8504
pause
