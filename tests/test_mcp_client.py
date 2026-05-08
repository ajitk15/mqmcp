"""
Simple MCP test client — connects to the SSE server and calls tools.

Usage:
    python tests/test_mcp_client.py                     # interactive mode
    python tests/test_mcp_client.py --tool find_mq_object --args '{"search_string":"QL.IN.APP1"}'
    python tests/test_mcp_client.py --list               # just list tools
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client

# ---------------------------------------------------------------------------
# Load .env so we pick up auth credentials automatically
# ---------------------------------------------------------------------------
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)

MCP_AUTH_USER = os.getenv("MCP_AUTH_USER", "")
MCP_AUTH_PASSWORD = os.getenv("MCP_AUTH_PASSWORD", "")
MCP_PORT = os.getenv("MQ_MCP_PORT", "5000")

SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:5000/sse")


def _auth_headers() -> dict[str, str]:
    """Build Basic Auth headers if credentials are configured."""
    if MCP_AUTH_USER and MCP_AUTH_PASSWORD:
        creds = base64.b64encode(f"{MCP_AUTH_USER}:{MCP_AUTH_PASSWORD}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}
    return {}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def print_tools(tools) -> list[str]:
    """Pretty-print tool list and return tool names."""
    print("\n" + "=" * 60)
    print("  AVAILABLE TOOLS")
    print("=" * 60)
    for tool in tools:
        params = []
        if tool.inputSchema and "properties" in tool.inputSchema:
            for name, prop in tool.inputSchema["properties"].items():
                required = name in tool.inputSchema.get("required", [])
                marker = " *" if required else ""
                params.append(f"    - {name}{marker}: {prop.get('type', '?')}")

        desc = (tool.description or "")[:100]
        print(f"\n  📌 {tool.name}")
        print(f"     {desc}...")
        if params:
            print("     Parameters:")
            print("\n".join(params))
    print("\n" + "=" * 60)
    return [t.name for t in tools]


async def call_tool(session: ClientSession, tool_name: str, arguments: dict):
    """Call a tool and print the result."""
    print(f"\n🔧 Calling: {tool_name}({json.dumps(arguments)})")
    print("-" * 50)
    try:
        result = await session.call_tool(tool_name, arguments)
        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)
            else:
                print(content)
        if result.isError:
            print("\n⚠️  Tool returned an error.")
    except Exception as e:
        print(f"\n❌ Error: {e}")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

async def interactive_mode():
    """Run an interactive REPL to test tools."""
    print(f"\n🚀 Connecting to MCP server at {SERVER_URL} ...")

    headers = _auth_headers()

    try:
        async with sse_client(url=SERVER_URL, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected!\n")

                # List tools
                result = await session.list_tools()
                tool_names = print_tools(result.tools)

                print("\nType a tool name and JSON arguments to test:")
                print("  list     — show all tools")
                print("  quit     — exit\n")
                print('Example: find_mq_object {"search_string": "QL.IN.APP1"}')
                print("Example: dspmq {}")
                print()

                while True:
                    try:
                        user_input = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: input("mcp> ").strip()
                        )
                    except (EOFError, KeyboardInterrupt):
                        break

                    if not user_input:
                        continue
                    if user_input.lower() in ("quit", "exit", "q"):
                        break
                    if user_input.lower() == "list":
                        result = await session.list_tools()
                        print_tools(result.tools)
                        continue

                    # Parse: tool_name {json_args}
                    parts = user_input.split(None, 1)
                    tool_name = parts[0]

                    if tool_name not in tool_names:
                        print(f"❌ Unknown tool '{tool_name}'. Type 'list' to see available tools.")
                        continue

                    args = {}
                    if len(parts) > 1:
                        try:
                            args = json.loads(parts[1])
                        except json.JSONDecodeError as e:
                            print(f"❌ Invalid JSON: {e}")
                            continue

                    await call_tool(session, tool_name, args)
                    print()

    except Exception as e:
        import traceback
        print(f"\n❌ Failed to connect: {type(e).__name__}: {e}")
        traceback.print_exc()
        return

    print("\n👋 Disconnected.")


async def single_call(tool_name: str, arguments: dict):
    """Connect, call one tool, print result, disconnect."""
    print(f"\n🚀 Connecting to MCP server at {SERVER_URL} ...")

    headers = _auth_headers()

    try:
        async with sse_client(url=SERVER_URL, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected!")
                await call_tool(session, tool_name, arguments)
    except Exception as e:
        print(f"\n❌ Failed: {e}")


async def list_only():
    """Connect, list tools, disconnect."""
    print(f"\n🚀 Connecting to MCP server at {SERVER_URL} ...")

    headers = _auth_headers()

    try:
        async with sse_client(url=SERVER_URL, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                print_tools(result.tools)
    except Exception as e:
        print(f"\n❌ Failed: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simple MCP test client")
    parser.add_argument("--tool", help="Tool name to call (skips interactive mode)")
    parser.add_argument("--args", default="{}", help='JSON arguments, e.g. \'{"search_string":"QL.IN"}\'')
    parser.add_argument("--list", action="store_true", help="Just list available tools and exit")
    args = parser.parse_args()

    if args.tool:
        try:
            tool_args = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in --args: {e}")
            sys.exit(1)
        asyncio.run(single_call(args.tool, tool_args))
    elif args.list:
        asyncio.run(list_only())
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
