@echo off
echo Starting Standalone UI-Agnostic MQ Frontend...
echo.
echo Running on HTTP server port: 8001
echo Target API Gateway: http://127.0.0.1:8000/api/v1/chat
echo.
python -m http.server 8001 --directory frontend
