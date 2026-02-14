@echo off
echo Killing all Python and Streamlit processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM streamlit.exe /T 2>nul
echo Done. You will need to verify if 'run_mq_api.bat' needs to be restarted.
pause
