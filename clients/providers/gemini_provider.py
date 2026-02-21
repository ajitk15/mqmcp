"""
Google Gemini provider for MQ assistant.
"""

from __future__ import annotations

from typing import Callable, Awaitable

from .base import LLMProvider

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

import os
_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiProvider(LLMProvider):
    """Calls Google Gemini via the google-generativeai SDK with function calling."""

    @property
    def name(self) -> str:
        return "Gemini"

    def _build_tool_declarations(self, tools: list):
        """
        Convert the plain-dict TOOLS_GEMINI schema (from mq_tools.schemas)
        into genai.protos.Tool objects expected by the SDK.
        """
        declarations = []
        for t in tools:
            props = t.get("parameters", {}).get("properties", {})
            required = t.get("parameters", {}).get("required", [])
            declarations.append(
                genai.protos.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            k: genai.protos.Schema(
                                type=genai.protos.Type.STRING,
                                description=v.get("description", ""),
                            )
                            for k, v in props.items()
                        },
                        required=required,
                    )
                    if props
                    else genai.protos.Schema(
                        type=genai.protos.Type.OBJECT, properties={}
                    ),
                )
            )
        return [genai.protos.Tool(function_declarations=declarations)]

    async def chat(
        self,
        user_input: str,
        conversation_history: list,
        tools: list,
        call_tool: Callable[[str, dict], Awaitable[str]],
        tools_used: list,
    ) -> tuple[str, dict]:
        if not HAS_GEMINI:
            return (
                "❌ Google Generative AI library not installed. "
                "Run: pip install google-generativeai",
                {}
            )

        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "❌ GEMINI_API_KEY environment variable not set", {}

        from mq_tools.prompts import MQ_SYSTEM_PROMPT

        genai.configure(api_key=api_key)

        tool_declarations = self._build_tool_declarations(tools)

        model = genai.GenerativeModel(
            model_name=_MODEL,
            system_instruction=MQ_SYSTEM_PROMPT,
            tools=tool_declarations,
        )

        # Reconstruct Gemini-format history from generic conversation_history
        gemini_history = []
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            if isinstance(msg["content"], str):
                gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=gemini_history)

        # Track user message in shared history
        conversation_history.append({"role": "user", "content": user_input})

        # Prune history — keep last 10 messages (user/assistant)
        if len(conversation_history) > 10:
            conversation_history[:] = conversation_history[-10:]

        print(f"🤖 Asking {self.name} ({_MODEL})…")
        max_iterations = 10
        current_message: object = user_input
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        for iteration in range(1, max_iterations + 1):
            print(f"   [Iteration {iteration}]")

            response = chat.send_message(current_message)
            
            # Accumulate usage
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                total_usage["prompt_tokens"] += response.usage_metadata.prompt_token_count
                total_usage["completion_tokens"] += response.usage_metadata.candidates_token_count
                total_usage["total_tokens"] += response.usage_metadata.total_token_count

            part = response.candidates[0].content.parts[0]

            if not (hasattr(part, "function_call") and part.function_call.name):
                # Plain text — done
                final_text = part.text
                conversation_history.append({"role": "assistant", "content": final_text})
                return final_text, total_usage

            fn = part.function_call
            tool_name = fn.name
            tool_args = dict(fn.args)
            tools_used.append({"name": tool_name, "args": tool_args})
            print(f"   📞 Calling: {tool_name}({tool_args})")

            tool_result = await call_tool(tool_name, tool_args)

            # Feed result back as a function response
            current_message = genai.protos.Content(
                parts=[
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )
                ]
            )

        return "❌ Maximum tool call iterations reached.", total_usage
