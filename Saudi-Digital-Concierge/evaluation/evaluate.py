"""Evaluation harness for the concierge pipeline.

Runs a set of question/expected-answer pairs through an agent and reports simple
retrieval and answer-quality metrics. Extend with your preferred metrics
(faithfulness, context recall, exact match, ...).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalCase:
    """A single evaluation example."""

    question: str
    expected_keywords: list[str]


def keyword_recall(answer: str, expected_keywords: list[str]) -> float:
    """Fraction of expected keywords present in ``answer`` (case-insensitive)."""
    if not expected_keywords:
        return 1.0
    answer_lc = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lc)
    return hits / len(expected_keywords)


def evaluate(agent, cases: list[EvalCase]) -> dict[str, float]:
    """Run ``agent`` over ``cases`` and return aggregate metrics."""
    scores = [keyword_recall(agent.answer(c.question), c.expected_keywords) for c in cases]
    return {
        "num_cases": len(cases),
        "avg_keyword_recall": sum(scores) / len(scores) if scores else 0.0,
    }


if __name__ == "__main__":
    print("Provide an agent and evaluation cases, then call evaluate(agent, cases).")
