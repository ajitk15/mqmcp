# 🚀 IBM MQ MCP Ecosystem

A powerful and user-friendly **Model Context Protocol (MCP)** server for IBM MQ, providing seamless natural language interaction with your Queue Managers. Manage, monitor, and troubleshoot IBM MQ infrastructure through AI-powered assistants or simple web interfaces.

---

## ✨ Core Features

*   🔍 **Infrastructure Discovery**: Instantly list all queue managers and their statuses.
*   📊 **Deep Monitoring**: Check queue depths, message status, and channel health with natural language.
*   🧠 **Smart Workflows**: Automatically locates queues across any Queue Manager (including Clusters) without needing explicit targeting.
*   🛡️ **Installation Auditing**: Retrieve detailed MQ version, build, and installation path info.
*   🔒 **Production Protection**: Hostname-based filtering prevents accidental queries to production systems.
*   🔐 **Basic Authentication**: Optional HTTP Basic Auth for SSE transport endpoints.
*   🎯 **Intelligent Query Routing**: Smart queue listing validates hostnames before executing MQ commands.
*   🔍 **Tool Transparency**: Configurable logging shows which MCP tools are called and their REST API endpoints.
*   ⚡ **Composite Tools**: High-level workflow tools (`get_queue_depth`, `run_mqsc_for_object`, `get_channel_status`) that auto-discover queue managers — no orchestration layer needed.
*   🤖 **Multiple Interfaces**: Choose between Pattern-based (Basic), AI-powered (OpenAI / Anthropic / Gemini), Guided (One-click), or SSE (Real-time).
*   🌐 **Universal REST Support**: Fully integrated with the IBM MQ REST API (mqweb), supporting both Distributed and z/OS managers.
*   🔌 **UI-Agnostic API Gateway**: A decoupled FastAPI backend that provides a single `POST /api/v1/chat` endpoint and comes with a built-in static Web Chatbot.
*   🛡️ **User-Friendly Errors**: Connection errors are presented as clear, actionable messages instead of raw HTTP traces.

---

## 🛠️ The MQ Toolset

The server exposes **7 tools** to any connected MCP client:

### Core Tools (Low-Level)

| Tool | Description |
| :--- | :--- |
| **`find_mq_object`** | Search the offline manifest (`qmgr_dump.csv`) for any object (Queue, Channel, App ID) across all Queue Managers. |
| **`dspmq`** | List available queue managers and their current state (Running/Ended). |
| **`dspmqver`** | Display IBM MQ version, build level, and installation platform details. |
| **`runmqsc`** | Execute any MQSC command (e.g., `DISPLAY QLOCAL`, `DISPLAY CHSTATUS`) against a specific Queue Manager. |

### Composite Tools (Workflow-Aware) ⭐

These tools **embed the search-first workflow** — they automatically discover which Queue Manager(s) host an object before executing commands. No orchestration layer or LLM prompt engineering required.

| Tool | Description |
| :--- | :--- |
| **`run_mqsc_for_object`** | Search for any MQ object → run an MQSC command on **all** hosting Queue Managers → return consolidated results. |
| **`get_queue_depth`** | Search for a queue → resolve aliases (QA* → QL*) → return current depth from all hosting Queue Managers. |
| **`get_channel_status`** | Search for a channel → return `CHSTATUS` from all hosting Queue Managers. |

---

## 📂 Project Architecture

```text
mqmcp/
├── server/
│   └── mqmcpserver.py              # ⚡ FastMCP Server (The Core)
├── resources/
│   └── qmgr_dump.csv               # 📄 Offline Snapshot Data
├── clients/
│   ├── providers/                  # 🧩 LLM Provider Modules
│   │   ├── __init__.py             #    Registry — get_provider("openai"|"anthropic"|"gemini")
│   │   ├── base.py                 #    Abstract LLMProvider base class
│   │   ├── openai_provider.py      #    OpenAI GPT handler
│   │   ├── anthropic_provider.py   #    Anthropic Claude handler
│   │   └── gemini_provider.py      #    Google Gemini handler
│   ├── mq_tools/                   # 📚 Shared MQ Knowledge
│   │   ├── prompts.py              #    MQ_SYSTEM_PROMPT (single source of truth)
│   │   ├── schemas.py              #    Tool schemas for all providers (built from one list)
│   │   └── converters.py           #    Dynamic MCP → provider schema converters
│   ├── streamlit_guided_client.py  # 🧭 Guided Assistant (Recommended)
│   ├── streamlit_basic_client.py   # 🤖 Pattern-based Web UI
│   ├── streamlit_openai_client.py  # 🧠 AI Assistant (LLM-powered)
│   ├── streamlit_sse_client.py     # ⚡ SSE Client (Real-time)
│   ├── streamlit_remote_client.py  # 🌐 Remote SSE + AI Client
│   ├── llm_client.py               # 🔗 LLM Orchestrator (stdio mode)
│   ├── dynamic_client.py           # 📜 Pattern Detection Library
│   └── test_mcp_client.py          # 🧪 Developer CLI Menu
├── scripts/
│   ├── run_mq_api.bat / .sh        # 🏁 Server Launcher
│   └── run_*.bat / .sh             # 🚀 Client Launchers
├── run_all_assistants.bat          # 🚀 Unified Launch Script
├── .env                            # 🔐 Secrets & Configuration
├── requirements.txt                # 📦 Core Dependencies
└── requirements-llm.txt            # 📦 Optional LLM Dependencies
```

---

## 🚀 Quick Start

### 0. MQ REST API Prerequisite
Before running the ecosystem, ensure the IBM MQ REST API (mqweb) is active on your MQ server.
- **Check Status**: Run `dspmqweb status` on the MQ server.
- **Start Service**: Run `strmqweb` if it is not already running.

### 1. Environment Setup

We recommend using a Python virtual environment:

```powershell
# Create & Activate
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate      # Linux/Mac

# Install core dependencies
pip install -r requirements.txt

# Install LLM dependencies (OpenAI / Anthropic / Gemini — pick what you need)
pip install -r requirements-llm.txt
```

### 2. Configuration (`.env`)

Create a `.env` file in the root directory (or update the existing one):

```env
MQ_URL_BASE=https://your-host:9443/ibmmq/rest/v3/admin/
MQ_USER_NAME=mqreader
MQ_PASSWORD=your_password

# Production Protection: Allowed hostname prefixes (comma-separated)
MQ_ALLOWED_HOSTNAME_PREFIXES=lod,loq,lot

# Tool Logging Display (true/false)
MQ_SHOW_TOOL_LOGGING=true

# Server Logging Level (INFO, DEBUG, WARNING, ERROR)
MQ_LOG_LEVEL=INFO

# LLM Provider API Keys (add whichever providers you plan to use)
OPENAI_API_KEY=sk-...          # OpenAI GPT-4
ANTHROPIC_API_KEY=sk-ant-...   # Anthropic Claude
GEMINI_API_KEY=AIza...         # Google Gemini

# Server Configuration (SSE mode only)
MQ_MCP_HOST=0.0.0.0
MQ_MCP_PORT=5000
MQ_MCP_TRANSPORT=stdio   # 'stdio' (default) or 'sse'

# MCP Endpoint Authentication (Basic Auth — SSE transport only)
# Leave blank to disable authentication
MCP_AUTH_USER=mcpadmin
MCP_AUTH_PASSWORD=mcpadmin
```

### 3. Launching the Assistant

Choose your preferred flavor of the assistant:

| Assistant | Command | Best For... |
| :--- | :--- | :--- |
| **API Gateway Backend** | `cd api && uvicorn main:app --reload` | Headless API serving LangGraph via `/api/v1/chat` (port 8000). |
| **Web Chatbot UI** | `.\run_frontend.bat` | **Recommended.** Decoupled HTML/JS frontend hitting the API Gateway (port 8001). |
| **Unified Launch** | `.\run_all_assistants.bat` | **Launches ALL Streamlit clients simultaneously.** |
| **Guided Assistant** | `streamlit run clients/streamlit_guided_client.py` | One-click ops & guided troubleshooting. |
| **AI Assistant (OpenAI)** | `streamlit run clients/streamlit_openai_client.py` | Natural conversations, Cluster support. |
| **Remote AI Assistant** | `streamlit run clients/streamlit_remote_client.py` | OpenAI / Anthropic / Gemini via SSE endpoint. |
| **SSE Assistant** | `streamlit run clients/streamlit_sse_client.py` | Real-time events & Smart Workflows. |
| **Basic Assistant** | `streamlit run clients/streamlit_basic_client.py` | Fast, deterministic pattern matching. |
| **CLI Tester** | `python clients/test_mcp_client.py` | Developers testing tool responses. |

---

## 🧪 Developer Testing

### 1. Built-in CLI Tester
The project includes a dedicated tester script for quick validation:
```powershell
python clients/test_mcp_client.py
```

### 2. Standalone MCP Inspector
Use the official MCP Inspector to interact with the server via a web interface. This is great for debugging tool outputs.
```powershell
# Ensure venv is active
npx @modelcontextprotocol/inspector python server/mqmcpserver.py
```

### 3. Claude Desktop Integration
To use this server with Claude Desktop, add it to your configuration:
- **Path**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ibm-mq": {
      "command": "python",
      "args": ["C:/absolute/path/to/mqmcp/server/mqmcpserver.py"],
      "env": {
        "MQ_URL_BASE": "https://host:port/ibmmq/rest/v3/admin/",
        "MQ_USER_NAME": "mq-user",
        "MQ_PASSWORD": "mq-password"
      }
    }
  }
}
```

### 4. VS Code Extensions (Cline / Roo Code)
Add the server to your extension settings using the same `command`, `args`, and `env` parameters as above. This allows you to manage MQ directly from your IDE's AI assistant.

---

## 🛡️ Security & Stability

*   **Basic Authentication**: SSE transport supports optional HTTP Basic Auth. Set `MCP_AUTH_USER` and `MCP_AUTH_PASSWORD` in `.env` to enable. Unauthenticated requests receive `401 Unauthorized`. Stdio mode (local subprocess) is unaffected.
*   **Production Protection**: Hostname-based filtering prevents accidental queries to production systems.
*   **User-Friendly Errors**: Connection errors (503, 401, timeouts, etc.) are translated into clear, actionable messages instead of raw HTTP stack traces.
*   **Process Isolation**: Clients launch the MCP server as a dedicated subprocess utilizing the active virtual environment.
*   **Logging**: Server-side diagnostic messages use Python's `logging` module and are routed to `stderr` to keep `stdout` clean for the MCP JSON-RPC protocol.
*   **Provider Modularity**: Each LLM provider lives in its own module under `clients/providers/`. Adding a new provider requires only one new file and one registry entry.

