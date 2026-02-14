@echo off
REM Quick cleanup script for hung Streamlit processes

echo Terminating Streamlit and Python processes...

REM Kill Streamlit processes
taskkill /F /IM streamlit.exe 2>nul
if %ERRORLEVEL% == 0 (
    echo   ✓ Streamlit terminated
) else (
    echo   - No Streamlit process found
)

REM Kill Python processes running mqmcpserver.py
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /C:"PID:"') do (
    wmic process where "ProcessId=%%a AND CommandLine LIKE '%%mqmcpserver.py%%'" delete 2>nul
)

echo.
echo Cleanup complete. You can now restart Streamlit.
pause
