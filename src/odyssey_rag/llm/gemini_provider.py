"""Google Gemini LLM provider via langchain-google-genai.

Alternate provider — swap via LLM_PROVIDER=gemini in environment.
Requires GOOGLE_API_KEY environment variable.
"""

from __future__ import annotations

import structlog

from odyssey_rag.exceptions import OdysseyRagError
from odyssey_rag.llm.provider import BaseLLMProvider, ChatMessage

logger = structlog.get_logger(__name__)

DEFAULT_MODEL: str = "gemini-2.5-pro"


class LLMError(OdysseyRagError):
    """LLM API call failed."""


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini LLM provider backed by langchain-google-genai.

    Attributes:
        _api_key: Google API key.
        _model: Gemini model identifier.
        _temperature: Sampling temperature.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> None:
        """Initialize the Gemini LLM provider.

        Args:
            api_key: Google API key (required).
            model: Gemini model identifier.
            temperature: Sampling temperature for generation.
        """
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    async def complete(self, messages: list[ChatMessage]) -> str:
        """Generate a completion using Gemini via langchain-google-genai.

        Args:
            messages: Ordered list of chat messages (role + content dicts).

        Returns:
            Assistant response text.

        Raises:
            LLMError: If the Google API call fails.
        """
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
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

            llm = ChatGoogleGenerativeAI(
                google_api_key=self._api_key,  # type: ignore[arg-type]
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
            msg = f"Gemini completion failed: {exc}"
            raise LLMError(msg) from exc

    def model_name(self) -> str:
        """Return the Gemini model name.

        Returns:
            Model name string (e.g. "gemini-2.5-pro").
        """
        return self._model
