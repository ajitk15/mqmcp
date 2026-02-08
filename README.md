# 🚀 IBM MQ MCP Ecosystem

A powerful and user-friendly **Model Context Protocol (MCP)** server for IBM MQ, providing seamless natural language interaction with your Queue Managers. Manage, monitor, and troubleshoot IBM MQ infrastructure through AI-powered assistants or simple web interfaces.

---

## ✨ Core Features

*   🔍 **Infrastructure Discovery**: Instantly list all queue managers and their statuses.
*   📊 **Deep Monitoring**: Check queue depths, message status, and channel health with natural language.
*   🛡️ **Installation Auditing**: Retrieve detailed MQ version, build, and installation path info.
*   🧠 **Multiple Interfaces**: Choose between Pattern-based (Basic), AI-powered (OpenAI/Anthropic), or Guided (One-click) interfaces.
*   🌐 **Universal REST Support**: Fully integrated with the IBM MQ REST API (mqweb), supporting both Distributed and z/OS managers.

---

## 🛠️ The MQ Toolset

The server exposes three primary tools to any connected MCP client:

1.  **`dspmq`**: Lists available queue managers and their current state (Running/Ended).
2.  **`dspmqver`**: Provides detailed IBM MQ version, build level, and installation platform details.
3.  **`runmqsc`**: The powerhouse tool—executes any MQSC command (e.g., `DISPLAY QLOCAL`, `DISPLAY CHSTATUS`) and returns formatted results.

---

## 📂 Project Architecture

```text
mq/
├── server/
│   └── mqmcpserver.py      # ⚡ FastMCP Server (The Core)
├── clients/
│   ├── streamlit_guided_client.py  # 🧭 Guided Assistant (Recommended)
│   ├── streamlit_basic_client.py   # 🤖 Pattern-based Web UI
│   ├── streamlit_openai_client.py # 🧠 AI Assistant (LLM-powered)
│   ├── dynamic_client.py           # 📜 Pattern Detection Library
│   ├── llm_client.py               # 🔗 LLM Integration Library
│   └── test_mcp_client.py          # 🧪 Developer CLI Menu
├── .env                            # 🔐 Secrets & Configuration
└── requirements.txt                # 📦 Dependencies
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

# Install Dependencies
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Create a `.env` file in the root directory (or update the existing one):

```env
MQ_URL_BASE=https://your-host:9443/ibmmq/rest/v3/admin/
MQ_USER_NAME=mqreader
MQ_PASSWORD=your_password
OPENAI_API_KEY=sk-... (Optional: for AI Assistant)
```

### 3. Launching the Assistant

Choose your preferred flavor of the assistant:

| Assistant | Command | Best For... |
| :--- | :--- | :--- |
| **Guided Assistant** | `streamlit run clients/streamlit_guided_client.py` | One-click ops & guided troubleshooting. |
| **AI Assistant** | `streamlit run clients/streamlit_openai_client.py` | Natural conversations & complex queries. |
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

*   **Process Isolation**: Clients launch the MCP server as a dedicated subprocess utilizing the active virtual environment.
*   **Error Handling**: Built-in protection against Windows encoding issues (`UnicodeEncodeError`) and robust `.env` discovery.
*   **Stderr Debugging**: All server-side logs are routed to `stderr` to prevent corruption of the MCP JSON-RPC protocol on `stdout`.

---

## 📜 Legal & License

*   **Copyright**: © 2025 IBM Corp.
*   **License**: Licensed under the Apache License, Version 2.0.

*Disclaimer: This is a community project and not an official IBM product. For production environments, ensure you enable SSL verification and use secure credential management.*
