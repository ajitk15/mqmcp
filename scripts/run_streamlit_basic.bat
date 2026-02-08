@echo off
REM Launcher for Streamlit Basic Client
echo ========================================
echo Starting Streamlit Basic MQ Assistant...
echo ========================================
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
streamlit run ..\clients\streamlit_basic_client.py
pause
