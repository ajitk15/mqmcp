# 📘 IBM MQ MCP Ecosystem - Technical Guide

This document provides a deep dive into the architecture, implementation details, and best practices for the IBM MQ MCP ecosystem.

---

## 🏗️ Architecture & Flow

### System Overview
The ecosystem consists of a **FastMCP Server** that interfaces with the **IBM MQ REST API**, and various clients that interact with the server via the **Model Context Protocol (stdio)**.

```text
User Input → Client (Guided/AI/Basic) → MCP Protocol (stdio) 
                                            ↓
                                        MCP Server
                                            ↓
                                    IBM MQ REST API
                                            ↓
                                      Queue Manager
```

### Component Breakdown
*   **`mqmcpserver.py`**: The "Brain". Handles tool registration and REST API orchestration.
*   **`dynamic_client.py`**: The "Router". Provides regex-based intent detection.
*   **`llm_client.py`**: The "Intelligence". Integrates with OpenAI/Anthropic for natural language tool selection.

### Server Execution
*   **Dynamic Clients (Basic/Guided/AI)**: Automatically launch their own private server instance.
*   **SSE Client**: Requires a standalone server. You can start it manually using `scripts/run_mq_api.bat` (Option 1).

### Server Execution Modes
The server (`mqmcpserver.py`) supports two distinct modes, controlled via `.env`:

1.  **Stdio Mode (Default)**:
    -   Activated when `MQ_MCP_TRANSPORT=stdio` (or unset).
    -   Used by local clients (`dynamic_client.py`) for process isolation.

2.  **SSE Mode (Server-Sent Events)**:
    -   Activated when `MQ_MCP_TRANSPORT=sse`.
    -   Binds to `MQ_MCP_HOST` (default `0.0.0.0`) and `MQ_MCP_PORT` (default `5000`).
    -   Ideal for remote access or decoupled architectures.

---

## 🔍 Dynamic Intent Detection

We support three primary strategies for translating natural language into MQ commands:

### 1. Pattern matching (Regex)
Used in the **Basic Assistant**. It is fast, predictable, and free.
*   **Pros**: Instant response, no API keys, easy to test.
*   **Best for**: Common operations like "List queues" or "Check depth".

### 2. Tool Calling (LLM)
Used in the **AI Assistant**. It uses models like GPT-4 or Claude 3.5 Sonnet to decide which tool to call.
*   **Pros**: Understands complex synonyms, extracts parameters intelligently.
*   **Best for**: Unstructured requests like "Are there any issues with my production queues?"

### 3. Hybrid Strategy (Recommended)
The **Guided Assistant** combines specific task definitions with the dynamic client to provide a reliable "one-click" experience while still supporting natural language commands.

---

## 🧠 Smart Workflows (Auto-Locate)

The ecosystem implements "Smart Queue" logic to simplify user interaction.

### The Problem
Traditionally, MQ admins must know *exactly* which Queue Manager hosts a queue before querying it (e.g., `DISPLAY QLOCAL(Q1)` needs a target QMGR).

### The Solution
Our clients (Dynamic, SSE, & AI) automatically solve this using a multi-step workflow:
1.  **Search**: When a user asks about a queue (e.g., "Check Q1"), the system first calls `search_qmgr_dump` to find it globally.
2.  **Identify**: It parses the results to find **ALL** Queue Managers hosting that queue (supports Multi-Instance and Clusters).
3.  **Execute**: It runs the requested command (Depth/Status) against *every* found Queue Manager using `runmqsc`.
4.  **Cluster Aware**: The AI client specifically checks for `CLUSTER` attributes and lists the hosting Queue Managers for you.

---

## ⚙️ Connectivity Prerequisites

Before the ecosystem can function, the underlying **IBM MQ REST API** must be operational. 

### Validating `dspmqweb`
The MCP server communicates with MQ via the REST interface. You must ensure this service is started on the MQ installation:

1.  **Status Check**: Run `dspmqweb status`. It should report that the web server is running.
2.  **Activation**: If stopped, run `strmqweb`.
3.  **Network Visibility**: Ensure the `MQ_URL_BASE` configured in `.env` is reachable from the machine running the MCP server (check firewalls and port 9443/appropriate port).

---

## 🛠️ Dependency & Troubleshooting

### Required Packages
*   `httpx`: Async HTTP client for MQ REST interactions.
*   `mcp`: The core protocol library.
*   `streamlit`: The web interface framework.
*   `python-dotenv`: Management of environment variables.

### Troubleshooting Common Issues

| Issue | Potential Cause | Solution |
| :--- | :--- | :--- |
| `UnicodeEncodeError` | Emojis in terminal | Ensure the latest `dynamic_client.py` is used (emojis removed). |
| `Connection Error` | Invalid `.env` path | The server searches current and parent directories for `.env`. |
| `ModuleNotFoundError` | Virtual Env inactive | Ensure `venv` is activated before running clients. |
| `Unknown Tool` | Server/Client mismatch | All clients now use `sys.executable` to ensure environment parity. |

---
 
 ## 🧪 Standalone Testing & Validation
 
 ### MCP Inspector (Debug Mode)
 For isolated server testing without a full client, use the MCP Inspector. It launches the server and opens a local web UI where you can manually invoke tools and inspect JSON-RPC message flow.
 
 ```powershell
 # Run from the root directory
 npx @modelcontextprotocol/inspector python server/mqmcpserver.py
 ```
 *Technical Note: The inspector captures `stdout` for the protocol and displays `stderr` in the terminal console, allowing you to see the "DEBUG" messages.*
 
 ### Process-Level Configuration
 When running as a standalone server (e.g., in Claude Desktop), the server needs to know where its dependencies and environment variables are.
 
 1.  **Environment Variables**: The server looks for a `.env` file in its current directory or one level up. If you are hosting it elsewhere, ensure you pass the `env` dictionary in your MCP config file.
 2.  **Working Directory**: On Windows, ensure paths use forward slashes `/` or double backslashes `\\` in JSON configurations to avoid escape character issues.
 
 ---

## 📊 Metrics & Logging (Splunk Compatible)

### Console Output (Transparency)
The `dynamic_client.py` provides transparent logging to `stdout` so you can see exactly what the assistant is doing:
*   **Endpoint**: Shows the full path to the MCP server script being executed.
*   **Tools**: Displays the exact Tool Name and Arguments (including raw MQSC commands) for every operation.

### Metrics Logger
The ecosystem includes a dedicated **Metrics Logger** (`clients/metrics_logger.py`) that generates structured JSON logs specifically formatted for **Splunk** ingestion.

#### How it works
The logger is placed on the **Client side** (e.g., in `DynamicMQClient`). This allows us to capture end-to-end metrics without modifying the core MCP server code.

1.  **Structured JSON**: Logs are output to `sys.stderr` as single-line JSON objects.
2.  **Context Tracking**: The `MetricsTracker` context manager automatically calculates execution time and captures success/failure status.

### Meaningful Metrics
The following metrics are automatically captured for every tool call:
*   `metrics.tool`: The name of the MQ tool called.
*   `metrics.execution_time_ms`: Time taken for the MCP server to respond.
*   `metrics.status`: `success` or `error`.
*   `context.qmgr`: The target Queue Manager name (where applicable).
*   `context.cmd`: The raw MQSC command being executed.

### Configuration
*   **Log to stderr**: (Default) Best for containerized environments.
*   **Log to File**: Set the `MQ_LOG_FILE` environment variable in your `.env` (e.g., `MQ_LOG_FILE=logs/mqmcp_metrics.log`).

---

## 💡 Best Practices

### Intent Precision
*   **DO**: Use word boundaries (`\b`) in regex to prevent command collisions (e.g., `dspmq` vs `dspmqver`).
*   **DO**: Include mandatory keywords for critical operations (e.g., requiring the word "queue" for queue status).

### User Experience
*   **DO**: Display the **Tool Name** and **Raw MQ Command** to build user trust and aid debugging.
*   **DO**: Handle `KeyboardInterrupt` and errors gracefully to provide a professional feel.

### Security
*   **DON'T**: Hardcode credentials in scripts; always use `.env`.
*   **DON'T**: Expose the MCP server directly to the public internet without an orchestrator/proxy.

---

## 🔒 Security Configuration (Production Readiness)

For production deployments, the MCP endpoint must be secured using SSL/TLS and Authentication. Since `FastMCP`'s standard run method is simplified, these features require specific implementation patterns.

### 1. Enable SSL/TLS (HTTPS)
To serve traffic securely, you must bypass the standard `mcp.run()` and use `uvicorn` directly with your certificate files.

**Implementation Pattern (`server/mqmcpserver.py`):**
```python
if transport == "sse":
    import uvicorn
    # Get the underlying Starlette app
    app = mcp.sse_app()
    
    # Run with SSL
    uvicorn.run(
        app,
        host=mcp_host,
        port=mcp_port,
        ssl_keyfile=os.getenv("MQ_MCP_SSL_KEY"),  # e.g., "key.pem"
        ssl_certfile=os.getenv("MQ_MCP_SSL_CERT") # e.g., "cert.pem"
    )
```

### 2. API Key Authentication
The simplest security layer is a middleware that enforces an `X-API-Key` header.

**Implementation Pattern (`server/mqmcpserver.py`):**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        api_key = os.getenv("MQ_MCP_API_KEY")
        if api_key and request.headers.get("X-API-Key") != api_key:
            return Response("Unauthorized", status_code=401)
        return await call_next(request)

# Add to app before running
app.add_middleware(AuthMiddleware)
```

---

## 🚀 Use Cases

1.  **DevOps Monitoring**: Quickly check queue health without logging into the MQ Explorer.
2.  **Incident Response**: Use the AI assistant to search for issues across multiple queue managers.
3.  **Audit & Compliance**: Retrieve installation details and versions using `dspmqver` with a single click.
4.  **Self-Service**: Allow non-MQ experts to perform basic queries using natural language.

---

## 🚀 Speed Launch

You can launch **ALL** assistants simultaneously using the provided batch script:

```powershell
.\run_all_assistants.bat
```

This will open 4 separate terminal windows, one for each client (Basic, Guided, AI, SSE), each on its own port.

---

*© 2025 IBM Corp. | Technical Reference for the IBM MQ MCP Ecosystem.*
