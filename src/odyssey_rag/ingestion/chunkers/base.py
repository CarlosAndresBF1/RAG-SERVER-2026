"""Abstract chunker interface and Chunk data transfer object.

Chunkers consume ParsedSection lists and produce Chunk objects that are
ready for embedding and storage. Each chunker strategy is optimized for
a specific document type.

Note: This ``Chunk`` dataclass is the *ingestion* DTO. The SQLAlchemy ORM
model is ``odyssey_rag.db.models.Chunk`` and must be imported with aliasing
when both are needed in the same module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from odyssey_rag.ingestion.parsers.base import ParsedSection


def count_tokens(text: str) -> int:
    """Approximate token count for a text string.

    Uses tiktoken (cl100k_base) when available; falls back to a char-based
    approximation (1 token ≈ 4 characters) otherwise.

    Args:
        text: Text to count tokens for.

    Returns:
        Integer token estimate.
    """
    try:
        import tiktoken  # type: ignore[import-untyped]

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


@dataclass
class Chunk:
    """A text chunk ready for embedding and storage.

    Attributes:
        content:     The chunk text (may include heading prefix).
        token_count: Approximate token count.
        section:     Inherited from ParsedSection.section.
        subsection:  Inherited from ParsedSection.subsection.
        chunk_index: Position of this chunk within the document (0-based).
        metadata:    Inherited/augmented metadata hints from the parser.
    """

    content: str
    token_count: int
    section: Optional[str] = None
    subsection: Optional[str] = None
    chunk_index: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


class BaseChunker(ABC):
    """Abstract base class for all chunking strategies.

    Attributes:
        max_tokens:     Maximum tokens per chunk (default 512).
        overlap_tokens: Token overlap between adjacent chunks (default 64).
    """

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> None:
        """Initialise chunker with size constraints.

        Args:
            max_tokens:     Target maximum tokens per chunk.
            overlap_tokens: Overlap tokens carried from the previous chunk.
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    @abstractmethod
    def chunk(self, sections: list[ParsedSection]) -> list[Chunk]:
        """Split a list of parsed sections into chunks.

        Args:
            sections: Ordered list of ParsedSection objects from a parser.

        Returns:
            Ordered list of Chunk objects with sequential chunk_index values.
        """
