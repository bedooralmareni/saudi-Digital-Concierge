"""Retriever that wraps a :class:`~src.database.vector_store.VectorStore`."""

from __future__ import annotations

from src.database.vector_store import SearchResult, VectorStore


class Retriever:
    """Fetch relevant context for a query from a vector store."""

    def __init__(self, store: VectorStore, top_k: int = 5) -> None:
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        """Return the most relevant chunks for ``query``."""
        return self.store.search(query, k=top_k or self.top_k)

    def as_context(self, query: str, top_k: int | None = None) -> str:
        """Return retrieved chunks joined into a single prompt-ready string."""
        results = self.retrieve(query, top_k)
        return "\n\n".join(r.text for r in results)
