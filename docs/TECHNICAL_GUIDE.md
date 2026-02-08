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

---

## 🔍 Dynamic Intent Detection

We support three primary strategies for translating natural language into MQ commands:

### 1. Pattern matching (Regex)
Used in the **Basic Assistant**. It is fast, predictable, and free.
*   **Pros**: Instant response, no API keys, easy to test.
*   **Best for**: Common operations like "List queues" or "Check depth".

### 2. LLM Tool Calling
Used in the **AI Assistant**. It uses models like GPT-4 or Claude 3.5 Sonnet to decide which tool to call.
*   **Pros**: Understands complex synonyms, extracts parameters intelligently.
*   **Best for**: Unstructured requests like "Are there any issues with my production queues?"

### 3. Hybrid Strategy (Recommended)
The **Guided Assistant** combines specific task definitions with the dynamic client to provide a reliable "one-click" experience while still supporting natural language commands.

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

## 🚀 Use Cases

1.  **DevOps Monitoring**: Quickly check queue health without logging into the MQ Explorer.
2.  **Incident Response**: Use the AI assistant to search for issues across multiple queue managers.
3.  **Audit & Compliance**: Retrieve installation details and versions using `dspmqver` with a single click.
4.  **Self-Service**: Allow non-MQ experts to perform basic queries using natural language.

---

*© 2025 IBM Corp. | Technical Reference for the IBM MQ MCP Ecosystem.*
