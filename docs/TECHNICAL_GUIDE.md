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

#### Server
*   **`mqmcpserver.py`**: The "Brain". Handles tool registration, REST API orchestration, and CSV-backed queue dump search. Uses stdlib `logging` and a module-level CSV cache for performance.

#### Shared MQ Knowledge (`clients/mq_tools/`)
*   **`prompts.py`**: Single source of truth for `MQ_SYSTEM_PROMPT` — consumed by all LLM providers.
*   **`schemas.py`**: Canonical tool definitions (`TOOLS_OPENAI`, `TOOLS_ANTHROPIC`, `TOOLS_GEMINI`) built from one shared `_TOOLS_CORE` list so they never drift.
*   **`converters.py`**: Converts live MCP tool objects to provider-specific schemas (`to_openai_schema`, `to_anthropic_schema`, `to_gemini_declarations`) — used by SSE/remote mode.

#### LLM Providers (`clients/providers/`)
*   **`base.py`**: Abstract `LLMProvider` class — enforces a uniform `chat()` interface: `(user_input, history, tools, call_tool, tools_used) → str`.
*   **`openai_provider.py`** / **`anthropic_provider.py`** / **`gemini_provider.py`**: Self-contained handlers for each provider's API, tool-call loop, and response parsing.
*   **`__init__.py`**: Registry — `get_provider("openai" | "anthropic" | "gemini")` returns the right handler. Adding a new provider = one file + one registry line.

#### Orchestrators
*   **`llm_client.py`**: Thin orchestrator (~230 lines). Manages the MCP stdio session and routes `handle_user_input()` calls to the correct provider module.
*   **`dynamic_client.py`**: The regex-based "Router". Provides fast, deterministic intent detection without LLM overhead.

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
    -   Supports optional **HTTP Basic Authentication** via `MCP_AUTH_USER` and `MCP_AUTH_PASSWORD` in `.env`.
    -   Ideal for remote access or decoupled architectures.

---

## 🔍 Dynamic Intent Detection

We support three primary strategies for translating natural language into MQ commands:

### 1. Pattern matching (Regex)
Used in the **Basic Assistant**. It is fast, predictable, and free.
*   **Pros**: Instant response, no API keys, easy to test.
*   **Best for**: Common operations like "List queues" or "Check depth".

### 2. Tool Calling (LLM)
Used in the **AI Assistant** and the **Remote AI Assistant**. It supports three providers — OpenAI GPT-4, Anthropic Claude, and Google Gemini.
*   **Pros**: Understands complex synonyms, extracts parameters intelligently.
*   **Best for**: Unstructured requests like "Are there any issues with my production queues?"
*   **Provider selection**: All providers share the same `MQ_SYSTEM_PROMPT` and the same four MQ tools — provider-specific schema conversion is handled transparently by `mq_tools/converters.py`.

### 3. Hybrid Strategy (Recommended)
The **Guided Assistant** combines specific task definitions with the dynamic client to provide a reliable "one-click" experience while still supporting natural language commands.

---

## 🧠 Smart Workflows (Auto-Locate)

The ecosystem implements "Smart Queue" logic to simplify user interaction.

### The Problem
Traditionally, MQ admins must know *exactly* which Queue Manager hosts a queue before querying it (e.g., `DISPLAY QLOCAL(Q1)` needs a target QMGR).

### The Solution
The MCP server provides two approaches for solving this:

#### Approach 1: Composite Tools (Recommended)
The server exposes **workflow-aware composite tools** that embed the entire search-and-execute workflow in a single tool call:

| Tool | What it does automatically |
| :--- | :--- |
| `run_mqsc_for_object` | Search → find all QMs → run MQSC on each → return consolidated results |
| `get_queue_depth` | Search → resolve aliases (QA*→QL*) → get CURDEPTH from all QMs |
| `get_channel_status` | Search → get CHSTATUS from all QMs |

These tools require **no LLM prompt engineering** and **no orchestration layer** — the workflow is enforced by the tool itself.

#### Approach 2: Multi-Step (Client-Driven)
Clients (Dynamic, SSE, & AI) can also solve this using a multi-step workflow:
1.  **Search**: When a user asks about a queue (e.g., "Check Q1"), the system first calls `search_qmgr_dump` to find it globally.
2.  **Identify**: It parses the results to find **ALL** Queue Managers hosting that queue (supports Multi-Instance and Clusters).
3.  **Execute**: It runs the requested command (Depth/Status) against *every* found Queue Manager using `runmqsc`.
4.  **Cluster Aware**: The AI client specifically checks for `CLUSTER` attributes and lists the hosting Queue Managers for you.

---

## 🔒 Production Protection (Hostname Filtering)

The ecosystem implements hostname-based filtering to prevent accidental queries against production systems.

### Configuration
Define allowed hostname prefixes in `.env`:
```env
MQ_ALLOWED_HOSTNAME_PREFIXES=lod,loq,lot
```

### How It Works
1. **Server-Side Filtering**: The `search_qmgr_dump` tool filters results by hostname prefix. For allowed matches, it proceeds normally. For restricted matches, it appends them to the result list with a clear `[RESTRICTED: hostname]` tag.
2. **Pre-Execution Validation**: The `runmqsc` tool validates hostname before executing commands.
3. **Client-Side Validation**: The dynamic client performs hostname checks before calling MCP tools.
4. **AI Politeness**: The AI Assistant is explicitly instructed to recognize `[RESTRICTED]` tags and respond politely: "I found this object on [QM_NAME], but I do NOT have access to production systems for safety."

### User Experience

✅ **Allowed (Non-Production)**:
```
Step 2: Found hostname: 'lodserver1'
Step 3: ✅ Hostname check PASSED
Step 4: Calling runmqsc to list queues...
```

🚫 **Blocked (Production)**:
```
Step 2: Found hostname: 'lopserver1'
Step 3: ❌ Hostname check FAILED

🚫 Access to production systems is restricted for safety.
Allowed hostname prefixes: lod, loq, lot
```

---

##🎯 Smart Query Routing

The dynamic client implements intelligent query routing that validates hostnames before executing MQ commands.

### Smart Queue Listing Flow
When a user asks "List all the queues on MQQMGR1":

1. **CSV Lookup**: Reads `qmgr_dump.csv` to find the hostname for MQQMGR1
2. **Extract Hostname**: Gets hostname from first matching row
3. **Validate Prefix**: Checks if hostname starts with allowed prefix
4. **Block or Execute**:
   - If blocked: Returns helpful error message
   - If allowed: Calls `runmqsc` with `DISPLAY QUEUE(*) WHERE(QTYPE EQ QLOCAL)`

### Intent Pattern Improvements
Updated regex patterns for better specificity:

```python
'list_qmgrs': [
    r'list.*queue\s+managers?',  # Requires "manager" keyword
],
'list_queues': [
    r'list.*queues?\s+(?:on|from|in|for)',  # Requires context
],
```

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

### Required Packages (`requirements.txt`)
*   `httpx`: Async HTTP client for MQ REST interactions.
*   `mcp`: The core protocol library.
*   `streamlit`: The web interface framework.
*   `python-dotenv`: Management of environment variables.
*   `pandas`: CSV-backed queue dump search in `mqmcpserver.py`.

### Optional LLM Packages (`requirements-llm.txt`)
Install only the packages for the providers you plan to use:

| Package | Provider |
|---|---|
| `openai` | OpenAI GPT-4 |
| `anthropic` | Anthropic Claude |
| `google-generativeai` | Google Gemini |

```powershell
pip install -r requirements-llm.txt
```

### Troubleshooting Common Issues

| Issue | Potential Cause | Solution |
| :--- | :--- | :--- |
| `⚠️ MQ is not available on 'host'` | MQ REST API down on that host | Contact MqAceInfra Support team or try again later. |
| `🔒 Authentication failed` | Wrong MQ credentials | Check `MQ_USER_NAME` and `MQ_PASSWORD` in `.env`. |
| `⏱️ Connection timed out` | Host unreachable | Check network / firewall rules. |
| `401 Unauthorized` (on MCP endpoint) | Missing/wrong MCP auth | Check `MCP_AUTH_USER` and `MCP_AUTH_PASSWORD` in `.env`. |
| `ModuleNotFoundError` | Virtual Env inactive | Ensure `venv` is activated before running clients. |
| `Unknown Tool` | Server/Client mismatch | All clients now use `sys.executable` to ensure environment parity. |

---
 
 ## 🧪 Standalone Testing & Validation
 
 ### MCP Inspector (Debug Mode)
 For isolated server testing without a full client, use the MCP Inspector. It launches a local web UI where you can manually invoke tools and inspect JSON-RPC message flow.
 
 #### Stdio Mode (Inspector launches the server)
 ```powershell
 # Run from the root directory
 npx @modelcontextprotocol/inspector python server/mqmcpserver.py
 ```
 The inspector starts the server as a subprocess and connects via stdio. No authentication is required.

 *Technical Note: The inspector captures `stdout` for the protocol and displays `stderr` in the terminal console, letting you see the server's `logging` output (level `DEBUG` by default in stdio mode).*
 
 #### SSE Mode (Connect to a running server)
 If your server is already running in SSE mode (`MQ_MCP_TRANSPORT=sse`):

 1. Launch the inspector:
    ```powershell
    npx @modelcontextprotocol/inspector
    ```
 2. In the Inspector web UI:
    - Change the **Transport Type** dropdown from `STDIO` to `SSE`
    - Enter the **URL**: `http://localhost:5000/sse`
    - If you have Basic Auth enabled, add a header:
      - Key: `Authorization`
      - Value: `Basic bXl1c2VyOm15cGFzc3dvcmQ=` (base64 of `myuser:mypassword`)
    - Click **Connect**

 To generate the base64-encoded credentials for your own username and password:
 ```powershell
 python -c "import base64; print(base64.b64encode(b'myuser:mypassword').decode())"
 ```
 Replace `myuser:mypassword` with your actual `MCP_AUTH_USER:MCP_AUTH_PASSWORD` values from `.env`.
 
 ### Process-Level Configuration
 When running as a standalone server (e.g., in Claude Desktop), the server needs to know where its dependencies and environment variables are.
 
 1.  **Environment Variables**: The server looks for a `.env` file in its current directory or one level up. If you are hosting it elsewhere, ensure you pass the `env` dictionary in your MCP config file.
 2.  **Working Directory**: On Windows, ensure paths use forward slashes `/` or double backslashes `\\` in JSON configurations to avoid escape character issues.
 
 ---

## 🔍 Tool Transparency (Streamlit Apps)

All Streamlit applications support configurable tool call logging to show exactly what MCP tools are being executed. Additionally, you can control the verbosity of the core MCP server.

### Configuration
Control logging display and verbosity via `.env`:
```env
# Client UI: Show or hide tool debugging expanders
MQ_SHOW_TOOL_LOGGING=true  # Show tool logging (default)
MQ_SHOW_TOOL_LOGGING=false # Hide for cleaner UI

# Server Console: Control MCP server stderr output
MQ_LOG_LEVEL=INFO # Default (DEBUG, WARNING, ERROR, CRITICAL)
```

### What's Displayed
When enabled, each tool call shows:
1. **MCP Tool Name** - Which tool was called (e.g., `runmqsc`, `dspmq`)
2. **Arguments** - Parameters passed to the tool (JSON format)
3. **REST API Endpoint** - The actual IBM MQ REST API URL being accessed

### Implementation
The `tool_logger.py` utility module provides:
- `get_rest_api_url(tool_name, args)` — REST endpoint construction
- `should_show_logging()` — environment-based toggle

### Example Output
```
🔧 Tool Call Details ▼
MCP Tool:         runmqsc
Arguments:        {"qmgr_name": "MQQMGR1", "mqsc_command": "DISPLAY QLOCAL(*)"}
REST Endpoint:    https://MQQMGR1:9443/ibmmq/rest/v3/admin/action/qmgr/MQQMGR1/mqsc
```

### Benefits
- **Debugging**: See exactly which tools are called and with what parameters
- **Learning**: Understand MCP → REST API mapping
- **Transparency**: Users know what's happening behind the scenes
- **Configurable**: Can be disabled for production or cleaner UI

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

### Provider Extensibility
*   **DO**: Add new LLM providers by creating `clients/providers/<name>_provider.py` implementing `LLMProvider.chat()` and registering it in `clients/providers/__init__.py`.
*   **DO**: Keep tool definitions in `mq_tools/schemas.py` (`_TOOLS_CORE`) — the OpenAI, Anthropic, and Gemini formats are generated automatically.
*   **DO**: Update `mq_tools/prompts.py` (`MQ_SYSTEM_PROMPT`) when refining the MQ instructions — all providers pick up the change immediately.

---

## 🔒 Security Configuration (Production Readiness)

The MCP server includes built-in security features for production deployments.

### 1. Basic Authentication (Implemented)

The SSE transport supports HTTP Basic Authentication out of the box. When credentials are configured, every HTTP request to the MCP endpoint must include a valid `Authorization: Basic <base64>` header.

**Configuration (`.env`):**
```env
# Set both to enable auth; leave blank to disable
MCP_AUTH_USER=mcpadmin
MCP_AUTH_PASSWORD=mcpadmin
```

**Behavior:**

| Transport | Auth Configured | Behavior |
| :--- | :--- | :--- |
| SSE | ✅ Yes | Basic Auth enforced — `401 Unauthorized` without valid credentials |
| SSE | ❌ No | No auth (warning logged at startup) |
| stdio | N/A | Auth not applicable (local subprocess) |

**Client Example:**
```powershell
# Without auth → 401 Unauthorized
curl http://localhost:5000/sse

# With auth → connected
curl -u mcpadmin:mcpadmin http://localhost:5000/sse
```

### 2. Enable SSL/TLS (HTTPS)
To serve traffic securely, you can bypass the standard `mcp.run()` and use `uvicorn` directly with your certificate files.

**Implementation Pattern (`server/mqmcpserver.py`):**
```python
if transport == "sse":
    import uvicorn
    app = mcp.sse_app()
    
    # Apply auth middleware if configured
    if MCP_AUTH_USER and MCP_AUTH_PASSWORD:
        app = BasicAuthMiddleware(app, MCP_AUTH_USER, MCP_AUTH_PASSWORD)
    
    # Run with SSL
    uvicorn.run(
        app,
        host=mcp_host,
        port=mcp_port,
        ssl_keyfile=os.getenv("MQ_MCP_SSL_KEY"),  # e.g., "key.pem"
        ssl_certfile=os.getenv("MQ_MCP_SSL_CERT") # e.g., "cert.pem"
    )
```

### 3. User-Friendly Error Messages

All connection errors from the MQ REST API are translated into clear, actionable messages:

| HTTP Error | User Sees |
| :--- | :--- |
| 503 Service Unavailable | ⚠️ MQ is not available on 'host'. Please report this issue to MqAceInfra Support team or try after some time. |
| 401 Unauthorized | 🔒 Authentication failed. Check MQ_USER_NAME and MQ_PASSWORD in your .env file. |
| 403 Forbidden | 🔒 Access denied. The configured user does not have permission. |
| Connection Refused | ⚠️ Cannot connect to MQ REST API. The host may be offline. |
| Timeout | ⏱️ Connection timed out. The host may be slow or unreachable. |
| SSL Error | 🔐 SSL/TLS error. There may be a certificate issue. |

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
