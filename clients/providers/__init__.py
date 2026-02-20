"""
providers — one module per LLM provider.

Usage:
    from providers import get_provider

    provider = get_provider("openai")   # or "anthropic" / "gemini"
    result = await provider.chat(
        user_input="What queues exist?",
        conversation_history=[],
        tools=TOOLS_OPENAI,
        call_tool=my_async_call_tool,
        tools_used=[],
    )

Each provider's chat() method is self-contained and stateless — the caller
(LLMToolCaller or streamlit_remote_client) manages conversation history.
"""

from __future__ import annotations

from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

# ---------------------------------------------------------------------------
# Registry — add a new entry here to expose a new provider to all clients
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str) -> LLMProvider:
    """
    Return an instantiated LLMProvider for the given name.

    Raises ValueError for unknown providers.
    """
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        supported = ", ".join(_REGISTRY)
        raise ValueError(f"Unknown provider '{name}'. Supported: {supported}")
    return cls()


def available_providers() -> list[str]:
    """Return the list of registered provider names."""
    return list(_REGISTRY.keys())


__all__ = ["LLMProvider", "get_provider", "available_providers"]
