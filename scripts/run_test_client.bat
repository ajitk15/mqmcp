@echo off
REM Quick launcher for the MCP Test Client
REM This script activates the virtual environment and runs the test client

echo ========================================
echo IBM MQ MCP Server - Test Client Launcher
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "..\venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then run: .\venv\Scripts\Activate.ps1
    echo Then run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call ..\venv\Scripts\activate.bat

REM Check if dependencies are installed
python -c "import mcp" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: Dependencies not installed!
    echo Installing dependencies...
    pip install -r ..\requirements.txt
    echo.
)

REM Run the test client
echo.
echo Starting interactive test client...
echo.
python ..\clients\test_mcp_client.py

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat

echo.
pause
