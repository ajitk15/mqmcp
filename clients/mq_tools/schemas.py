"""
Canonical MQ tool definitions for each LLM provider format.

These are the *static* schemas used by llm_client.py (stdio mode).
For SSE/remote mode — where tools are fetched dynamically from the server —
use mq_tools.converters instead.

Import examples:
    from mq_tools.schemas import TOOLS_OPENAI
    from mq_tools.schemas import TOOLS_ANTHROPIC
    from mq_tools.schemas import TOOLS_GEMINI
"""

# ---------------------------------------------------------------------------
# Shared tool definitions (provider-agnostic core data)
# ---------------------------------------------------------------------------
_TOOLS_CORE = [
    {
        "name": "dspmq",
        "description": "List all IBM MQ queue managers and their running status (running/stopped)",
        "parameters": {},
        "required": [],
    },
    {
        "name": "dspmqver",
        "description": "Get IBM MQ version, build level, and installation path details",
        "parameters": {},
        "required": [],
    },
    {
        "name": "runmqsc",
        "description": (
            "Execute an MQSC command on a specific IBM MQ queue manager. "
            "Use this for operations like checking queue depth, listing queues, "
            "displaying channels, etc."
        ),
        "parameters": {
            "qmgr_name": {
                "type": "string",
                "description": "Name of the queue manager (e.g., 'QM1', 'PROD_QM')",
            },
            "mqsc_command": {
                "type": "string",
                "description": (
                    "MQSC command to execute. Examples: "
                    "'DISPLAY QLOCAL(*)' to list all queues, "
                    "'DISPLAY QLOCAL(MYQUEUE) CURDEPTH' to check queue depth, "
                    "'DISPLAY CHANNEL(*)' to list channels"
                ),
            },
        },
        "required": ["qmgr_name", "mqsc_command"],
    },
    {
        "name": "search_qmgr_dump",
        "description": "Search the queue manager dump for a specific string across all columns",
        "parameters": {
            "search_string": {
                "type": "string",
                "description": "The string to search for in the queue manager data",
            }
        },
        "required": ["search_string"],
    },
]


# ---------------------------------------------------------------------------
# OpenAI function-calling format
# ---------------------------------------------------------------------------
def _to_openai(tool: dict) -> dict:
    properties = {
        k: {"type": v["type"], "description": v["description"]}
        for k, v in tool["parameters"].items()
    }
    schema: dict = {"type": "object", "properties": properties}
    if tool["required"]:
        schema["required"] = tool["required"]
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": schema,
        },
    }


TOOLS_OPENAI: list[dict] = [_to_openai(t) for t in _TOOLS_CORE]


# ---------------------------------------------------------------------------
# Anthropic tool format
# ---------------------------------------------------------------------------
def _to_anthropic(tool: dict) -> dict:
    properties = {
        k: {"type": v["type"], "description": v["description"]}
        for k, v in tool["parameters"].items()
    }
    input_schema: dict = {"type": "object", "properties": properties}
    if tool["required"]:
        input_schema["required"] = tool["required"]
    return {
        "name": tool["name"],
        "description": tool["description"],
        "input_schema": input_schema,
    }


TOOLS_ANTHROPIC: list[dict] = [_to_anthropic(t) for t in _TOOLS_CORE]


# ---------------------------------------------------------------------------
# Gemini / Google Generative AI format (plain dict — no SDK objects here)
# ---------------------------------------------------------------------------
def _to_gemini(tool: dict) -> dict:
    properties = {
        k: {"type": "STRING", "description": v["description"]}
        for k, v in tool["parameters"].items()
    }
    params: dict = {"type": "OBJECT", "properties": properties}
    if tool["required"]:
        params["required"] = tool["required"]
    return {
        "name": tool["name"],
        "description": tool["description"],
        "parameters": params,
    }


TOOLS_GEMINI: list[dict] = [_to_gemini(t) for t in _TOOLS_CORE]
