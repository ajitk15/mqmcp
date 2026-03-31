# IBM MQ AI Gateway API

This directory contains the central **UI-Agnostic API** built with **FastAPI** and **LangGraph**. It serves as the single brain and entrypoint for *any* frontend application (Streamlit, React, MS Teams) to interact with IBM MQ using natural language.

## 📦 1. Installation

This API requires a specific set of dependencies related to building REST endpoints and maintaining the LangGraph conversational agent.

From the `api` directory, run:
```bash
pip install -r requirements.txt
```

> **Note:** Ensure your root `.env` file is properly configured with your `OPENAI_API_KEY` and IBM MQ connection details (`MQ_URL_BASE`, `MQ_USER_NAME`, `MQ_PASSWORD`).

## 🚀 2. Running the API

Start the FastAPI application using `uvicorn`. The `--reload` flag is highly recommended for development as it automatically restarts the server when you make code changes.

From the **root project directory** (one level up from this folder), run:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Once running, you can access:
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Use this to manually test the API endpoint!)

## 🎨 3. The Static Web Frontend (Decoupled)
This API is completely decoupled from the UI. To use the included zero-dependency HTML/CSS/JavaScript frontend, you must launch it as a separate application:

1. Keep the API running in the background.
2. Open a new terminal in the root project directory.
3. Run `.\run_frontend.bat` (which serves the `frontend/` directory on port 8001).
4. Access the UI at: **http://127.0.0.1:8001/**

This purely static frontend sends raw CORS `fetch()` POST requests back to the API Backend at `http://127.0.0.1:8000/api/v1/chat`.

## 🧪 4. Testing the API Programmatically

### Method A: Using the included test script
A simple Python test script is provided in the root directory to verify end-to-end connectivity.
```bash
# From the root project directory
python test_api.py
```

### Method B: Using cURL
You can simulate a frontend application sending a message from the command line:

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "session_id": "my-test-session-123",
  "message": "List all queue managers available."
}'
```

### Response Format
All frontends must parse this standard JSON format returned by `/api/v1/chat`:
```json
{
  "reply": "Here are the queue managers... 1. QM1 - Status: running",
  "tools_used": ["dspmq"],
  "error": null
}
```

## 📁 4. Architecture Overview

- **`main.py`**: The FastAPI application and core HTTP routes. Handles session memory.
- **`models.py`**: Pydantic schemas validating the request/response payloads.
- **`agent.py`**: The LangGraph AI configuration. Routes human requests to the LLM and manages tool execution conditional edges.
- **`mcp_tools.py`**: Native LangChain tool definitions that wrap standard IBM MQ HTTP REST requests, avoiding the overhead of STDIO process spinning.
