# IBM MQ MCP Server (`mqmcpserver.py`) Technical Reference

## 1. Problem Statement
Monitoring, querying, and administering IBM MQ infrastructure typically involves context-switching between different administrative consoles (like MQ Explorer or `runmqsc` terminals) and reading obscure IBM documentation. For modern AI assistants to seamlessly interact with MQ environments without hallucination, a bridge is required. The challenge is connecting AI agents (which speak JSON/Text natively) to IBM MQ (which communicates via MQSC commands and REST interfaces) while enforcing security, limiting blast radius, and resolving distributed MQ objects reliably.

## 2. Solution
`mqmcpserver.py` is a specialized Model Context Protocol (MCP) server built with `FastMCP` that acts as a secure, intelligent bridge between AI assistants and the IBM MQ REST API. 
It encapsulates deep MQ knowledge by:
- Providing intelligent "search & execute" composite tools that automatically resolve logical queue names (like Alias queues) to physical destinations before running queries.
- Looking up queue managers, types, and hostnames dynamically using an offline manifest cache (`qmgr_dump.csv`).
- Exposing simple, declarative tools (`dspmq`, `dspmqver`, `get_queue_depth`, `get_channel_status`, `run_mqsc_for_object`) that AI models can invoke.
- Offering self-contained error handling that translates cryptic HTTP/MQ errors into human/AI-friendly actionable explanations.

## 2.1 Available MCP Tools (Reference)

| Tool | Description | How It Works |
|------|-------------|--------------|
| `find_mq_object` | Searches the offline dump for objects and returns hosting queue managers. | Performs a pandas DataFrame lookup against `qmgr_dump.csv`, applying optional object type filters, before enforcing the `ALLOWED_HOSTNAME_PREFIXES` guard. |
| `dspmq` | Lists all queue managers and their statuses. | Constructs a `GET` request to the `/qmgr/` IBM MQ REST API. Optionally resolves by QM name first to dynamically target the correct hostname. |
| `dspmqver` | Displays MQ version and architecture install information. | Constructs a `GET` request to the `/installation` IBM MQ REST API. |
| `runmqsc` | Runs **read-only** MQSC commands against an explicitly named queue manager. Modification commands (ALTER, DEFINE, DELETE, etc.) are blocked. | Wraps an MQSC command inside a JSON payload and `POST`s it to the `/action/qmgr/{qm}/mqsc` REST API. It resolves the hostname internally. Before execution, the command is checked against `_MODIFY_VERBS`; if it's a modification command, a polite redirect to the support team is returned instead. |
| `run_mqsc_for_object` | **Composite Tool:** Discovers an object globally and runs a **read-only** MQSC command on all hosts. Modification commands are blocked. | First checks the command against `_MODIFY_VERBS`. If allowed, executes internal `_search_objects_structured` to find all authorized target QMs. Iteratively loops over them, calling `_run_mqsc_raw` on each to accumulate results. |
| `get_queue_depth` | **Composite Tool:** Intelligently fetches queue depths globally, including resolving Aliases. | Locates the queue. If the queue is an Alias (`QA.*`), it automatically fires a background `DISPLAY QALIAS` to parse the `TARGET()` property *before* querying the actual physical local depth. |
| `get_channel_status` | **Composite Tool:** Aggregates channel status across instances. | First searches for the channel name explicitly filtered by `CHANNEL` type. Iterates through the discovered queue managers running `DISPLAY CHSTATUS`. |

## 3. Benefits
- **AI-Native Administration**: AI models like Claude or Cursor can directly query and triage MQ issues natively using standardized tools.
- **Workflow Automation**: Replaces multi-step manual investigations (e.g., searching for a queue -> resolving its alias target -> finding its hostname -> running depth queries) with single intelligent composite functions.
- **Reduced Alert Fatigue**: Automatically gathers contextual diagnostics when an issue occurs, significantly lowering Time to Resolution (MTTR).
- **Blast Radius Containment**: Uses prefix-based allow-lists to strictly prevent the MCP server from accidentally tampering with or querying restricted production queue managers.
- **Protocol Agnostic Interface**: Supports both `stdio` (for local desktop application integration) and HTTP `sse` (Server-Sent Events) for remote API connectivity.

## 4. Required Python Packages
To run this MCP server, the following packages must be installed. They are typically installed via:

```bash
pip install mcp
pip install mcp[fastmcp]  # or simply fastmcp
pip install python-dotenv
pip install pandas
pip install httpx
pip install uvicorn       # Required if running in SSE transport mode
```
*(Optionally consolidate these in a `requirements.txt` file)*

## 5. Security Aspects
* **Restricted Allow-list**: Implements a strict `ALLOWED_HOSTNAME_PREFIXES` guard. The server intercepts requests and entirely denies access to hostnames that aren't defined in this list (e.g., exclusively allowing `lod`, `loq`, `lot` development tiers to prevent production outages).
* **HTTP Basic Authentication for SSE**: If running remotely over Server-Sent Events (`sse`), it implements an ASGI middleware block to enforce Basic Authentication (`MCP_AUTH_USER` / `MCP_AUTH_PASSWORD`) mitigating unauthorized external exploitation.
* **REST API Credentials**: Communicates with the MQ REST endpoint exclusively through TLS (supported) using basic auth service credentials injected via environment variables.
* **Read-only Enforcement (Modification Blocking)**: The server enforces a strict read-only policy. A set of 14 MQSC modification verbs (`ALTER`, `DEFINE`, `DELETE`, `CLEAR`, `MOVE`, `SET`, `RESET`, `START`, `STOP`, `PURGE`, `REFRESH`, `RESOLVE`, `ARCHIVE`, `BACKUP`) is maintained in `_MODIFY_VERBS`. Before any MQSC command is executed via `runmqsc` or `run_mqsc_for_object`, the helper `_is_modification_command()` checks the first word of the command. If it matches a modification verb, the command is **not executed** and a polite message is returned directing the user to:
  1. Reach out to the support team (configured via `MQ_SUPPORT_TEAM` in `.env`), or
  2. Raise a ticket from **ServiceNow** → go/gen → assign to the admin group (configured via `MQ_ADMIN_GROUP` in `.env`).

  The support team name and admin group are **not hardcoded** — they are loaded from environment variables at startup.

## 6. Logging
The project employs a robust, structured JSON logging engine specifically designed for telemetry generation. `mqmcpserver.py` initializes its logger via the custom `utils.logger.get_mcp_logger()` component.

### 6.1 100% JSON Formatted Logs
A custom `JSONFormatter` enforces that every log entry is written as a structured JSON object. 
Example standard MCP log:
```json
{
  "timestamp": "2026-04-11T09:05:00.123",
  "level": "INFO",
  "logger": "mcp_server",
  "message": "run_mqsc_for_object called",
  "context": {"object": "QL.IN.APP1", "command": "DISPLAY QLOCAL(QL.IN.APP1)"}
}
```
*This design natively supports shipping logs to SIEM platforms like Splunk or Datadog.*

### 6.2 Context Injection
Tool execution data (like what queue name the LLM is querying) is injected into the logging object via the `extra` parameter. The JSON logger automatically extracts this `extra` context dictionary and embeds it cleanly into the final JSON payload.

### 6.3 Dual-Channel Output
By default, the logging engine streams output to:
1. **Console (`sys.stderr`)**: For live debugging and standard output visibility.
2. **File (`logs/mcpserver.log`)**: For persistent disk storage.

### 6.4 Environment Variables for Logging
Logging behavior can be directly controlled via `.env`:
* **`MQ_LOG_LEVEL`**: Controls project verbosity (Defaults to `"INFO"`). Setting this to `"DEBUG"` reveals connection/authentication steps.
* **`MQ_MCP_LOG_FILE`**: Determines where the MCP Server logs are stored (Defaults to `logs/mcpserver.log`).

## 7. Sample `.env` Configuration
The following represents `.env` variables strictly utilized by `mqmcpserver.py`:

```dotenv
# --- IBM MQ Connection Details ---
MQ_URL_BASE="https://api.internal.example.com/ibmmq/rest/v2/"
MQ_USER_NAME="svc_mq_api_user"
MQ_PASSWORD="super_secret_password"

# --- Security Allow List ---
# Comma separated hostname prefixes permitted for communication
MQ_ALLOWED_HOSTNAME_PREFIXES="lod,loq,lot"

# --- Support Contact Details (shown when modification commands are blocked) ---
MQ_SUPPORT_TEAM="InfraSupport"
MQ_ADMIN_GROUP="MQACE_ADMIN"

# --- MCP Transport Options ---
# Options: "stdio" (local client direct) or "sse" (network connected)
MQ_MCP_TRANSPORT="stdio"
MQ_MCP_HOST="127.0.0.0"
MQ_MCP_PORT="8000"

# --- Network Authentication (Only applies if MQ_MCP_TRANSPORT=sse) ---
MCP_AUTH_USER="admin"
MCP_AUTH_PASSWORD="admin_password"
```

## 8. Helper Commands (Testing & Verification)

### Direct Python Execution (Standalone test)
```powershell
# Starts the MCP server on stdio or sse according to your .env
python server/mqmcpserver.py
```

### Manual API Testing (When running under SSE)
If `MQ_MCP_TRANSPORT="sse"` and `MQ_MCP_PORT=8000`, you can test basic availability:
```powershell
curl -I http://localhost:8000/
# If authentication is enabled:
curl -I -u "admin:admin_password" http://localhost:8000/
```

### Client Testing using MCP CLI
You can test the tools locally using `mcp-cli` (if installed globally or inside virtual environment):
```powershell
# Install npx if using node to test
npx @modelcontextprotocol/inspector python server/mqmcpserver.py
```

## 9. Best Practices
1. **Never Hardcode Secrets**: Always strictly rely on `.env` injection.
2. **Keep the CSV Dump Fresh**: The `qmgr_dump.csv` mapping layer is cached in memory. Whenever your overarching MQ topology undergoes major changes, refresh this resource CSV and occasionally restart the MCP process.
3. **Use Composite Tools**: Encourage the LLM to use composite tools (like `get_queue_depth`) rather than raw `find_mq_object` followed by `runmqsc` to avoid latency from multiple sequential roundtrips.
4. **Transport Isolation**: Run as `stdio` whenever possible (especially for local IDE integrations). Only utilize `sse` if running inside a containerized remote network architecture.

## 10. Further Enhancements
* **Dynamic Refresh Event**: Implement an API listener or chron job that auto-reloads `_load_csv_from_disk()` dynamically without rebooting the server if the topology changes.
* **Controlled Write Tools**: If selective write operations are ever needed (e.g., `clear_queue`, `reset_channel`), they should be implemented as separate tools with explicit secondary confirmation, bypassing `_MODIFY_VERBS` only for approved operations.
* **Pagination & Memory Threshold**: If `qmgr_dump.csv` scales massively, consider moving toward SQLite/duckDB instead of holding it permanently in `pandas.DataFrame` memory cache. 
* **SSL Verification Support**: Currently `verify=False` is set for `httpx.AsyncClient`. It should ideally consume a CA `.pem` file from the environment variables to enforce SSL verification.

## 11. Integration Guidelines

### Integrating with Claude Desktop
To integrate `mqmcpserver.py` locally into the Claude Desktop App via `stdio` transport:
1. Ensure your `.env` contains `MQ_MCP_TRANSPORT="stdio"`.
2. Locate Claude Desktop's `claude_desktop_config.json` file.
   - On Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - On Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Add the following entry to the `mcpServers` object:

```json
{
  "mcpServers": {
    "ibm-mq": {
      "command": "C:\\path\\to\\your\\python.exe",
      "args": [
        "C:\\Workspace\\hready\\mqmcp\\server\\mqmcpserver.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Workspace\\hready\\mqmcp"
      }
    }
  }
}
```
*(Update `command` and `args` to strictly point to your virtual environment Python executable and your actual git repository path. Ensure `PYTHONPATH` points to the project root.)*

### Integrating with Cursor IDE
Cursor allows adding MCP servers directly from its settings menu.
1. Open Cursor Settings (`Ctrl + ,` or `Cmd + ,`).
2. Navigate to **Features** -> **MCP Servers**.
3. Add a new MCP server.
4. Set the **Type** as `command`.
5. Name it something memorable like `IBM MQ Server`.
6. Use the CLI command pointing to the Python file, e.g., `python C:\Workspace\hready\mqmcp\server\mqmcpserver.py`.
7. Once successfully saved, Cursor's generic internal AI will suddenly gain abilities to diagnose your MQ infrastructure when prompted.

## 12. Standalone Migration

If you want to package `mqmcpserver.py` and run it on an entirely different machine or standalone repository, you cannot move *just* that single file. Here is the exact minimum file structure you need to migrate:

```text
your_new_folder/
├── .env                  # Your configuration secrets (including MQ_SUPPORT_TEAM, MQ_ADMIN_GROUP)
├── server/
│   └── mqmcpserver.py    # The actual server script
├── utils/
│   ├── __init__.py       # (Empty file to make it a python module)
│   └── logger.py         # Required by mqmcpserver.py for logging
└── resources/
    └── qmgr_dump.csv     # The cached mapping manifest
```

### Why these are required:
1. **`utils/logger.py`**: `mqmcpserver.py` strictly imports `get_mcp_logger`. If you leave it behind, it will crash with a `ModuleNotFoundError` immediately upon booting.
2. **`resources/qmgr_dump.csv`**: The entire intelligent resolving mechanism natively relies on this CSV acting as an offline DB.
3. **`.env`**: Since the server parses credentials explicitly from `os.getenv`, it must be present for connectivity to the MQ REST endpoint. It also must include `MQ_SUPPORT_TEAM` and `MQ_ADMIN_GROUP` for the modification-blocked redirect message.

## 13. Code Review Findings

> [!NOTE]
> The following findings were identified during a detailed review of `mqmcpserver.py`. Items marked ✅ have been resolved. Remaining items are documented for team review.

### 13.1 ✅ Unused Imports — RESOLVED

Previously identified unused imports (`import logging`, `from typing import Any`) have been removed. The current import block is clean:

```python
import asyncio, base64, json, os, re, sys
from pathlib import Path
from urllib.parse import urlparse
import httpx, pandas as pd
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
```

---

### 13.2 ✅ Duplicated Code — MOSTLY RESOLVED

#### 13.2.1 ✅ Hostname Resolution & URL Rewriting
The duplicated `urlparse` + hostname replacement block has been extracted into a single helper:
```python
def _build_url(target_hostname: str, path: str) -> str:
    """Replace the hostname in URL_BASE with target_hostname and append path."""
    parsed = urlparse(URL_BASE)
    new_netloc = f"{target_hostname}:{parsed.port}" if parsed.port else target_hostname
    return parsed._replace(netloc=new_netloc).geturl() + path
```
All four call sites (`dspmq`, `dspmqver`, `runmqsc`, `_run_mqsc_raw`) now use this helper.

#### 13.2.2 ✅ `urlparse` Import Location
`from urllib.parse import urlparse` is now imported once at the top of the file (line 8).

#### 13.2.3 ✅ Search + Type-Inference Logic
`find_mq_object()` now delegates to the internal `_search_objects_structured()` helper, eliminating the duplicated search/filter/type-inference logic.

---

### 13.3 ✅ Questionable Patterns — RESOLVED

#### 13.3.1 ✅ Redundant `import re`
The inner `import re` inside `prettify_runmqsc()` has been removed. `re` is imported once at the top level.

#### 13.3.2 ✅ Fragile `dir()` Check
`target_hostname` is now initialized to `""` at the top of both `dspmq()` and `dspmqver()` functions, eliminating the need for the fragile `'target_hostname' in dir()` pattern.

#### 13.3.3 ✅ Unused `allowed_list` Variable
The `allowed_list` variable in `is_hostname_allowed()` is now used in the returned error message to inform users which hostname prefixes are permitted.

---

### 13.4 ✅ Optimization Opportunities — RESOLVED

#### 13.4.1 ✅ httpx Client Reuse
A shared module-level async client (`get_http_client()`) has been implemented and is now reused across all MCP tool calls, eliminating repeated TLS handshake overhead and speeding up composite tools like `get_queue_depth`.

#### 13.4.2 ✅ CSV Full-Text Search Performance
The CSV search logic in `_search_objects_structured()` has been optimized. It now uses highly performant, vectorized `pandas` operations (`str.contains`) acting strictly on the relevant data columns (`qmgr`, `hostname`, `mqsc_command`, `object_type`), rather than applying a lambda function across every column.

---

### 13.5 Summary

| Category | Count | Status |
|----------|-------|--------|
| Unused imports | 2 | ✅ Resolved |
| Duplicated code blocks | 3 patterns (8 occurrences) | ✅ Resolved |
| Questionable patterns | 3 | ✅ Resolved |
| Optimization opportunities | 2 | ✅ Resolved |

> **Conclusion**: All technical debt items, bugs, and optimization opportunities identified during the latest code review have been successfully implemented.
