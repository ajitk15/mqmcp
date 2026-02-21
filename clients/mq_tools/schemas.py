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
        "description": "List QMs and status.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "dspmqver",
        "description": "Get MQ version details.",
        "parameters": {},
        "required": [],
    },
    {
        "name": "runmqsc",
        "description": "Run MQSC command.",
        "parameters": {
            "qmgr_name": {
                "type": "string",
                "description": "QM name",
            },
            "mqsc_command": {
                "type": "string",
                "description": "MQSC cmd",
            },
            "hostname": {
                "type": "string",
                "description": "Host from search_qmgr_dump",
            },
        },
        "required": ["qmgr_name", "mqsc_command"],
    },
    {
        "name": "search_qmgr_dump",
        "description": "Search QM dump for object host.",
        "parameters": {
            "search_string": {
                "type": "string",
                "description": "String to search",
            },
            "object_type": {
                "type": "string",
                "description": "Optional: QMGR, QLOCAL, QREMOTE, QMODEL, QALIAS, CHANNEL, QUEUES (all Q* types), etc.",
            },
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
