@echo off
REM Launcher for Streamlit Guided Assistant
echo ===========================================
echo Starting Streamlit Guided MQ Assistant...
echo ===========================================
echo.

REM Check if venv exists
if not exist "..\venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found in root!
    echo Please run setup first.
    pause
    exit /b 1
)

REM Activate venv and run streamlit
call ..\venv\Scripts\activate.bat
streamlit run ..\clients\streamlit_guided_client.py --server.port 8502
pause
