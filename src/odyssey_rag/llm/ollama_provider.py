"""Ollama LLM provider using local Ollama instance.

Local LLM provider — swap via LLM_PROVIDER=ollama in environment.
Requires Ollama running locally (no API key needed).
"""

from __future__ import annotations

import structlog

from odyssey_rag.exceptions import OdysseyRagError
from odyssey_rag.llm.provider import BaseLLMProvider, ChatMessage

logger = structlog.get_logger(__name__)

DEFAULT_MODEL: str = "llama3.1:latest"
DEFAULT_BASE_URL: str = "http://host.docker.internal:11434"


class LLMError(OdysseyRagError):
    """LLM API call failed."""


class OllamaLLMProvider(BaseLLMProvider):
    """Ollama LLM provider backed by local Ollama instance via langchain-ollama.

    Attributes:
        _base_url: Ollama server URL.
        _model: Model name string.
        _temperature: Sampling temperature (0.0 = deterministic).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._temperature = temperature

    async def complete(self, messages: list[ChatMessage]) -> str:
        """Generate a completion using the local Ollama instance.

        Args:
            messages: Ordered list of chat messages (role + content dicts).

        Returns:
            Assistant response text.

        Raises:
            LLMError: If the Ollama API call fails.
        """
        try:
            from langchain_ollama import ChatOllama
            from langchain.schema import AIMessage, HumanMessage, SystemMessage

            lc_messages = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "user":
                    lc_messages.append(HumanMessage(content=content))
                else:
                    lc_messages.append(AIMessage(content=content))

            llm = ChatOllama(
                base_url=self._base_url,
                model=self._model,
                temperature=self._temperature,
            )
            response = await llm.ainvoke(lc_messages)
            content = response.content
            if isinstance(content, str):
                return content
            return str(content)
        except LLMError:
            raise
        except Exception as exc:
            msg = f"Ollama completion failed: {exc}"
            raise LLMError(msg) from exc

    def model_name(self) -> str:
        """Return the Ollama model name."""
        return self._model
