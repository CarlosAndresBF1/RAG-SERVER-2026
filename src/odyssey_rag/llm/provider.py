"""Abstract LLM provider interface.

All LLM providers implement BaseLLMProvider so the rest of the system
remains decoupled from a specific LLM vendor or SDK.

Message format uses a simple dict list compatible with OpenAI's chat
completion format (role + content), which LangChain also accepts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeAlias

# Simple chat message: {"role": "system"|"user"|"assistant", "content": "..."}
ChatMessage: TypeAlias = dict[str, str]


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers.

    Concrete implementations:
    - OpenAILLMProvider    (GPT-4o via langchain-openai)
    - AnthropicLLMProvider (Claude via langchain-anthropic)
    - GeminiLLMProvider    (Gemini via langchain-google-genai)
    """

    @abstractmethod
    async def complete(self, messages: list[ChatMessage]) -> str:
        """Generate a completion from a conversation history.

        Args:
            messages: Ordered list of chat messages. Each message is a dict
                with keys ``"role"`` (system/user/assistant) and
                ``"content"`` (text).

        Returns:
            The assistant's response text.

        Raises:
            LLMError: If the provider API call fails.
        """

    @abstractmethod
    def model_name(self) -> str:
        """Return the underlying model identifier.

        Returns:
            Model name string (e.g. "gpt-4o", "claude-sonnet-4-20250514").
        """
