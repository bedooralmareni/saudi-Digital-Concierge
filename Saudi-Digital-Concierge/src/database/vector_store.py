"""Vector store abstraction.

Defines the minimal interface the rest of the project depends on. Swap in a
concrete backend (Chroma, FAISS, pgvector, ...) by implementing these methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class SearchResult:
    """A single retrieved chunk and its similarity score."""

    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore(ABC):
    """Minimal vector-store interface used by the retrieval layer."""

    @abstractmethod
    def add(
        self,
        texts: Sequence[str],
        metadatas: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        """Embed and store a batch of texts with optional metadata."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        """Return the ``k`` most similar chunks to ``query``."""
        raise NotImplementedError
