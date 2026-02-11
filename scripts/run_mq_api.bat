@echo off
setlocal
cd /d "%~dp0"

echo [1] Starting MCP Server with SSE transport (Standard MCP API)...
echo Visit http://127.0.0.1:8000/sse
echo.
echo [2] Starting FastAPI Wrapper (REST API)...
echo Visit http://127.0.0.1:8001/docs
echo.

set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    python mqmcpserver_sse.py
) else if "%choice%"=="2" (
    python api_wrapper.py
) else (
    echo Invalid choice
)

pause
