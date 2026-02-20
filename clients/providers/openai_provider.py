"""
OpenAI GPT provider for MQ assistant.
"""

from __future__ import annotations

import json
from typing import Callable, Awaitable

from .base import LLMProvider

try:
    import openai as _openai_sdk
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

_MODEL = "gpt-4-turbo-preview"


class OpenAIProvider(LLMProvider):
    """Calls OpenAI chat completions with a multi-turn tool-calling loop."""

    @property
    def name(self) -> str:
        return "OpenAI"

    async def chat(
        self,
        user_input: str,
        conversation_history: list,
        tools: list,
        call_tool: Callable[[str, dict], Awaitable[str]],
        tools_used: list,
    ) -> str:
        if not HAS_OPENAI:
            return "❌ OpenAI library not installed. Run: pip install openai"

        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "❌ OPENAI_API_KEY environment variable not set"

        from mq_tools.prompts import MQ_SYSTEM_PROMPT

        client = _openai_sdk.OpenAI(api_key=api_key)

        # Add user message to history
        conversation_history.append({"role": "user", "content": user_input})

        print(f"🤖 Asking {self.name} ({_MODEL})…")
        max_iterations = 10

        for iteration in range(1, max_iterations + 1):
            print(f"   [Iteration {iteration}]")

            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": MQ_SYSTEM_PROMPT},
                    *conversation_history,
                ],
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message

            if not message.tool_calls:
                # Final text response
                final_text = message.content or ""
                conversation_history.append({"role": "assistant", "content": final_text})
                return final_text

            print(f"🔧 {self.name} decided to call tools…")
            conversation_history.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tools_used.append({"name": tool_name, "args": tool_args})
                print(f"   📞 Calling: {tool_name}({tool_args})")

                tool_result = await call_tool(tool_name, tool_args)

                conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": tool_result,
                    }
                )

        return "❌ Maximum tool call iterations reached."
