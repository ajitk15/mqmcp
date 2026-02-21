"""
Abstract base class for all LLM providers.

Every provider must implement chat() with a uniform signature so that
LLMToolCaller and the Streamlit clients can swap providers without
changing any orchestration logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class LLMProvider(ABC):
    """
    Base class for LLM provider integrations.

    Subclasses handle all provider-specific API calls, tool-call loops,
    and response parsing.  The caller supplies:

    - conversation_history : mutable list of {"role": ..., "content": ...}
      dicts.  Provider appends to this list in-place for multi-turn support.
    - tools : provider-specific tool schema list (e.g. TOOLS_OPENAI)
    - call_tool : async callable (tool_name: str, args: dict) -> str
      that executes the actual MCP tool and returns its text output.
    - tools_used : mutable list the provider appends to for transparency
      logging.  Each item is {"name": str, "args": dict}.
    """

    @abstractmethod
    async def chat(
        self,
        user_input: str,
        conversation_history: list,
        tools: list,
        call_tool: Callable[[str, dict], Awaitable[str]],
        tools_used: list,
    ) -> tuple[str, dict]:
        """
        Run one conversational turn with the LLM.

        Returns a tuple of (final_text_response, usage_metadata) after 
        all tool calls have been resolved.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging."""
        ...
