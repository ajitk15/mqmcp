"""
Dynamic MCP tool converters.

Used by SSE/remote clients that fetch tools at runtime from the MCP server.
For static stdio mode, use mq_tools.schemas instead.

Import example:
    from mq_tools.converters import to_openai_schema, to_anthropic_schema
    from mq_tools.converters import to_gemini_declarations  # needs google-generativeai
"""

from __future__ import annotations
from typing import Any


def to_openai_schema(mcp_tools: list) -> list[dict]:
    """Convert a list of MCP Tool objects to OpenAI function-calling format."""
    result = []
    for tool in mcp_tools:
        parameters = (
            tool.inputSchema
            if hasattr(tool, "inputSchema") and tool.inputSchema
            else {"type": "object", "properties": {}}
        )
        result.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or f"Execute {tool.name}",
                    "parameters": parameters,
                },
            }
        )
    return result


def to_anthropic_schema(mcp_tools: list) -> list[dict]:
    """Convert a list of MCP Tool objects to Anthropic tool format."""
    result = []
    for tool in mcp_tools:
        input_schema = (
            tool.inputSchema
            if hasattr(tool, "inputSchema") and tool.inputSchema
            else {"type": "object", "properties": {}}
        )
        result.append(
            {
                "name": tool.name,
                "description": tool.description or f"Execute {tool.name}",
                "input_schema": input_schema,
            }
        )
    return result


def to_gemini_declarations(mcp_tools: list) -> Any:
    """
    Convert a list of MCP Tool objects to a Gemini Tool with FunctionDeclarations.

    Requires google-generativeai to be installed.
    Returns a list containing one genai.protos.Tool object.
    """
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is required for Gemini support. "
            "Run: pip install google-generativeai"
        ) from exc

    declarations = []
    for tool in mcp_tools:
        schema = tool.inputSchema if hasattr(tool, "inputSchema") and tool.inputSchema else {}
        props = schema.get("properties", {})
        required = schema.get("required", [])
        declarations.append(
            genai.protos.FunctionDeclaration(
                name=tool.name,
                description=tool.description or f"Execute {tool.name}",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: genai.protos.Schema(
                            type=genai.protos.Type.STRING,
                            description=v.get("description", "") if isinstance(v, dict) else "",
                        )
                        for k, v in props.items()
                    },
                    required=required,
                )
                if props
                else genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
            )
        )
    return [genai.protos.Tool(function_declarations=declarations)]
