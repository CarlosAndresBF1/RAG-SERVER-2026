"""OpenAI LLM provider using GPT-4o via langchain-openai.

Default provider for response generation and summarization.
Requires OPENAI_API_KEY environment variable.
"""

from __future__ import annotations

import structlog

from odyssey_rag.exceptions import OdysseyRagError
from odyssey_rag.llm.provider import BaseLLMProvider, ChatMessage

logger = structlog.get_logger(__name__)

DEFAULT_MODEL: str = "gpt-4o"


class LLMError(OdysseyRagError):
    """LLM API call failed."""


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI LLM provider backed by GPT-4o via langchain-openai.

    Attributes:
        _api_key: OpenAI API key.
        _model: Model name string.
        _temperature: Sampling temperature (0.0 = deterministic).
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        """Initialize the OpenAI LLM provider.

        Args:
            api_key: OpenAI API key (required).
            model: OpenAI model name.
            temperature: Sampling temperature for generation.
        """
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    async def complete(self, messages: list[ChatMessage]) -> str:
        """Generate a completion from a conversation history using GPT-4o.

        Args:
            messages: Ordered list of chat messages (role + content dicts).

        Returns:
            Assistant response text.

        Raises:
            LLMError: If the OpenAI API call fails.
        """
        try:
            from langchain_openai import ChatOpenAI
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

            llm = ChatOpenAI(
                api_key=self._api_key,  # type: ignore[arg-type]
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
            msg = f"OpenAI completion failed: {exc}"
            raise LLMError(msg) from exc

    def model_name(self) -> str:
        """Return the OpenAI model name.

        Returns:
            Model name string (e.g. "gpt-4o").
        """
        return self._model
