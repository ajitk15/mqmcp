"""
Anthropic Claude provider for MQ assistant.
"""

from __future__ import annotations

from typing import Callable, Awaitable

from .base import LLMProvider

try:
    import anthropic as _anthropic_sdk
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

import os
_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


class AnthropicProvider(LLMProvider):
    """Calls Anthropic Messages API with a multi-turn tool-use loop."""

    @property
    def name(self) -> str:
        return "Anthropic"

    async def chat(
        self,
        user_input: str,
        conversation_history: list,
        tools: list,
        call_tool: Callable[[str, dict], Awaitable[str]],
        tools_used: list,
    ) -> tuple[str, dict]:
        if not HAS_ANTHROPIC:
            return "❌ Anthropic library not installed. Run: pip install anthropic", {}

        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return "❌ ANTHROPIC_API_KEY environment variable not set", {}

        from mq_tools.prompts import MQ_SYSTEM_PROMPT

        client = _anthropic_sdk.Anthropic(api_key=api_key)

        # Track user message in shared history
        conversation_history.append({"role": "user", "content": user_input})

        # Prune history — keep last 10 messages (user/assistant)
        if len(conversation_history) > 10:
            conversation_history[:] = conversation_history[-10:]

        print(f"🤖 Asking {self.name} ({_MODEL})…")
        max_iterations = 10
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for iteration in range(1, max_iterations + 1):
            print(f"   [Iteration {iteration}]")

            response = client.messages.create(
                model=_MODEL,
                max_tokens=2048,
                system=MQ_SYSTEM_PROMPT,
                tools=tools,
                messages=conversation_history,
            )
            
            # Accumulate usage
            if hasattr(response, 'usage') and response.usage:
                total_usage["prompt_tokens"] += response.usage.input_tokens
                total_usage["completion_tokens"] += response.usage.output_tokens
                total_usage["total_tokens"] = total_usage["prompt_tokens"] + total_usage["completion_tokens"]

            has_tool_use = any(block.type == "tool_use" for block in response.content)

            if not has_tool_use:
                final_text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                conversation_history.append({"role": "assistant", "content": final_text})
                return final_text, total_usage

            print(f"🔧 {self.name} decided to call tools…")

            # Append full assistant message (may contain text + tool_use blocks)
            conversation_history.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tools_used.append({"name": tool_name, "args": tool_input})
                print(f"   📞 Calling: {tool_name}({tool_input})")

                tool_result = await call_tool(tool_name, tool_input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result,
                    }
                )

            conversation_history.append({"role": "user", "content": tool_results})

        return "❌ Maximum tool call iterations reached.", total_usage
