"""Anthropic (Claude) LLM provider via langchain-anthropic.

Alternate provider — swap via LLM_PROVIDER=anthropic in environment.
Requires ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import structlog

from odyssey_rag.exceptions import OdysseyRagError
from odyssey_rag.llm.provider import BaseLLMProvider, ChatMessage

logger = structlog.get_logger(__name__)

DEFAULT_MODEL: str = "claude-sonnet-4-20250514"


class LLMError(OdysseyRagError):
    """LLM API call failed."""


class AnthropicLLMProvider(BaseLLMProvider):
    """Anthropic Claude LLM provider backed by langchain-anthropic.

    Attributes:
        _api_key: Anthropic API key.
        _model: Claude model identifier.
        _temperature: Sampling temperature.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        """Initialize the Anthropic LLM provider.

        Args:
            api_key: Anthropic API key (required).
            model: Claude model identifier.
            temperature: Sampling temperature for generation.
        """
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    async def complete(self, messages: list[ChatMessage]) -> str:
        """Generate a completion using Claude via langchain-anthropic.

        Args:
            messages: Ordered list of chat messages (role + content dicts).

        Returns:
            Assistant response text.

        Raises:
            LLMError: If the Anthropic API call fails.
        """
        try:
            from langchain_anthropic import ChatAnthropic
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

            llm = ChatAnthropic(
                anthropic_api_key=self._api_key,  # type: ignore[arg-type]
                model_name=self._model,
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
            msg = f"Anthropic completion failed: {exc}"
            raise LLMError(msg) from exc

    def model_name(self) -> str:
        """Return the Claude model name.

        Returns:
            Model name string (e.g. "claude-sonnet-4-20250514").
        """
        return self._model
