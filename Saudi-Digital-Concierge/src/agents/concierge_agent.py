"""The Saudi Digital Concierge agent.

Ties the retrieval layer to a language model. The LLM call is left as a
``generate`` hook so any provider can be plugged in without touching the RAG
logic.
"""

from __future__ import annotations

from typing import Callable

from src.retrieval.retriever import Retriever

SYSTEM_PROMPT = (
    "You are the Saudi Digital Concierge, a helpful assistant for visitors to "
    "Saudi Arabia. Answer using only the provided context about places, events, "
    "entertainment and tourism. If the context does not contain the answer, say "
    "so honestly. Reply in the same language as the question (Arabic or English)."
)


class ConciergeAgent:
    """Retrieval-augmented question answering agent."""

    def __init__(
        self,
        retriever: Retriever,
        generate: Callable[[str], str],
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.retriever = retriever
        self.generate = generate
        self.system_prompt = system_prompt

    def build_prompt(self, question: str) -> str:
        """Assemble the full prompt: system + retrieved context + question."""
        context = self.retriever.as_context(question)
        return (
            f"{self.system_prompt}\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            f"Answer:"
        )

    def answer(self, question: str) -> str:
        """Answer a visitor question using retrieved context."""
        return self.generate(self.build_prompt(question))
