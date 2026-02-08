@echo off
echo ========================================================
echo Launching all IBM MQ Assistants on dedicated ports...
echo ========================================================
echo.
echo [1] Basic Assistant:   http://localhost:8501
echo [2] Guided Assistant:  http://localhost:8502
echo [3] AI Assistant:      http://localhost:8503
echo.
echo Press any key to start all three in separate windows...
pause > nul

start cmd /k "cd scripts && run_streamlit_basic.bat"
start cmd /k "cd scripts && run_streamlit_guided.bat"
start cmd /k "cd scripts && run_streamlit_openai.bat"

echo All launching! Check your browser.
exit
