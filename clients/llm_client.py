#!/usr/bin/env python3
"""
LLM-Based Dynamic Tool Calling — MQ Assistant

Connects to the MCP server over stdio and uses a pluggable LLM provider
(OpenAI, Anthropic, or Gemini) to answer natural-language MQ queries.

Setup:
  1. pip install -r requirements-llm.txt
  2. Set one of: OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY
  3. Run: python llm_client.py

Provider selection:
  - Defaults to OpenAI if OPENAI_API_KEY is set.
  - Falls back to Anthropic if only ANTHROPIC_API_KEY is set.
  - Override with --provider openai|anthropic|gemini.
"""

import asyncio
import json
import os
import sys
import atexit

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

try:
    from metrics_logger import get_metrics_logger, MetricsTracker
except ImportError:
    from .metrics_logger import get_metrics_logger, MetricsTracker

from mq_tools.schemas import TOOLS_OPENAI, TOOLS_ANTHROPIC, TOOLS_GEMINI
from providers import get_provider, available_providers

# Load environment variables
load_dotenv()
logger = get_metrics_logger("mq-llm-client")

# Provider → tool schema mapping
_TOOL_SCHEMAS: dict[str, list] = {
    "openai":    TOOLS_OPENAI,
    "anthropic": TOOLS_ANTHROPIC,
    "gemini":    TOOLS_GEMINI,
}


class LLMToolCaller:
    """
    Orchestrates an MCP stdio session and delegates LLM interaction
    to the appropriate provider module.

    All provider-specific logic (API calls, tool-call loops, prompt) lives
    in clients/providers/<name>_provider.py.  This class is responsible only
    for:
      - Connecting to the MCP server process
      - Routing handle_user_input() to the right provider
      - Maintaining conversation_history and tools_used lists
      - Lifecycle management (connect / disconnect / cleanup)
    """

    def __init__(self, server_script: str | None = None, provider: str = "openai"):
        if server_script is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

        self.server_script = server_script
        self.session: ClientSession | None = None
        self.provider = provider
        self.conversation_history: list = []
        self.tools_used: list = []
        self._cleanup_done = False
        self._process = None

        atexit.register(self.cleanup)

    # ------------------------------------------------------------------
    # MCP connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Spawn the MCP server subprocess and initialise the session."""
        print("🔌 Connecting to MCP server…")

        if not os.path.exists(self.server_script):
            raise FileNotFoundError(f"Server script not found: {self.server_script}")

        print(f"   Server script: {self.server_script}")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )

        try:
            self.client_context = stdio_client(server_params)
            read, write = await asyncio.wait_for(
                self.client_context.__aenter__(), timeout=15.0
            )
            print("   ✅ Server process started")

            if hasattr(self.client_context, "_process"):
                self._process = self.client_context._process

            self.session_context = ClientSession(read, write)
            self.session = await asyncio.wait_for(
                self.session_context.__aenter__(), timeout=15.0
            )
            print("   ✅ Session created")

            await asyncio.wait_for(self.session.initialize(), timeout=15.0)
            print("✅ Connected to MCP server\n")
        except asyncio.TimeoutError:
            raise Exception("Connection timeout: Server took too long to respond (15s)")
        except Exception as e:
            raise Exception(f"Failed to connect to MCP server: {e}")

    async def disconnect(self) -> None:
        """Close the MCP session and client context."""
        try:
            if hasattr(self, "session_context") and self.session_context:
                await self.session_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"DEBUG: Error closing session: {e}")

        try:
            if hasattr(self, "client_context") and self.client_context:
                await self.client_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"DEBUG: Error closing client: {e}")

    def cleanup(self) -> None:
        """Force-clean resources (synchronous, for atexit / signal handlers)."""
        if self._cleanup_done:
            return

        print("🧹 Cleaning up MCP client…")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.disconnect())
            else:
                loop.run_until_complete(self.disconnect())
        except Exception as e:
            print(f"DEBUG: Error during graceful disconnect: {e}")

        if self._process and hasattr(self._process, "poll"):
            try:
                if self._process.poll() is None:
                    print("   ⚠️ Subprocess still running, terminating…")
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=3)
                    except Exception:
                        print("   ⚠️ Subprocess didn't terminate, killing…")
                        self._process.kill()
                        self._process.wait()
                    print("   ✅ Subprocess terminated")
            except Exception as e:
                print(f"DEBUG: Error terminating subprocess: {e}")

        self._cleanup_done = True
        print("✅ Cleanup complete")

    def __del__(self) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    # Core conversation entry point
    # ------------------------------------------------------------------

    async def handle_user_input(self, user_input: str) -> str:
        """
        Route the user's message to the configured LLM provider.

        Returns the final text response after all tool calls have been
        resolved.
        """
        print(f"\n💬 User: {user_input}")
        print("-" * 70)

        # Reset per-request tool tracking; history is preserved across turns
        self.tools_used = []

        provider_impl = get_provider(self.provider)
        tools = _TOOL_SCHEMAS.get(self.provider, TOOLS_OPENAI)

        async def call_tool(tool_name: str, tool_args: dict) -> str:
            with MetricsTracker(
                logger, tool_name, {"provider": self.provider, "args": tool_args}
            ):
                result = await self.session.call_tool(tool_name, tool_args)
            return result.content[0].text

        return await provider_impl.chat(
            user_input=user_input,
            conversation_history=self.conversation_history,
            tools=tools,
            call_tool=call_tool,
            tools_used=self.tools_used,
        )

    # ------------------------------------------------------------------
    # Interactive REPL
    # ------------------------------------------------------------------

    async def interactive_mode(self) -> None:
        """Run a simple REPL loop."""
        print("=" * 70)
        print("🤖 LLM-Based MQ Assistant")
        print(f"   Provider: {self.provider.upper()}")
        print("=" * 70)
        print("\nI can help you with IBM MQ operations using natural language!")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "bye"):
                    print("\n👋 Goodbye!")
                    break
                response = await self.handle_user_input(user_input)
                print(f"\n🤖 Assistant:\n{response}")
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                import traceback
                print(f"\n❌ Error: {e}")
                traceback.print_exc()


async def main() -> None:
    """Detect provider from env and start the assistant."""
    provider = "openai"
    if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        provider = "anthropic"
    elif os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        provider = "gemini"

    print(f"\n🔍 Using provider: {provider.upper()}")

    client = LLMToolCaller(provider=provider)
    try:
        await client.connect()
        await client.interactive_mode()
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║  LLM-Based Dynamic Tool Calling                                  ║
║                                                                  ║
║  Supported providers: openai · anthropic · gemini               ║
║                                                                  ║
║  Setup:                                                          ║
║  1. pip install -r requirements-llm.txt                        ║
║  2. Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY    ║
║  3. Run this script                                            ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
