# M4 submission — Baseline running

Repository: [Saudi Digital Concierge](https://github.com/bedooralmareni/saudi-Digital-Concierge).

The deliverable is a single-model baseline that accepts a travel request, retrieves
Saudi tourism KB evidence, generates an answer, and displays the result. Two notebook
alternatives are included, with setup steps in the [main README](README.md).

| Required deliverable | Repository location |
| --- | --- |
| Local model baseline | [Qwen notebook](notebooks/single_model_colab.ipynb) |
| API single-agent baseline | [OpenAI notebook](notebooks/Saudi_Digital_Concierge_OpenAI_API_Clean.ipynb) |
| Third-party setup instructions | [README](README.md) |
| One dependency file | [requirements.txt](../requirements.txt) |
| Offline validation | [tests](../tests/test_baseline.py), [verification record](VERIFICATION.md) |
| KB inputs and implementation | `data/processed/`, `src/database/`, `src/vector_store/` |

Both versions print evidence and answers and export JSON results. The local version
uses Qwen3-8B on a Colab GPU. The API version uses the existing gpt-4o-mini model,
CPU embeddings, and hotel/place/event tools. It needs the reviewer's own API key and
credits. These versions use different models and retrieval workflows; they do not
establish a controlled comparison or complete the planned multi-agent evaluation.

## Before sharing

1. Run each updated notebook in a fresh Colab runtime using the README steps.
2. Confirm a nonempty answer, evidence IDs, and a downloaded JSON result for each.
3. Inspect the answer's price/rating claims against the retrieved records. Save the
   executed notebooks/results as demonstration evidence with the model identified.
4. Publish the prepared repository changes. The README's Colab links point to
   `main` and display the previous version until those changes are pushed.
5. Confirm the recipient can open the repository link. For a private repository,
   provide access through GitHub before sending the link.

The offline tests cannot replace the fresh-runtime checks. The current verification
record explicitly distinguishes automated checks from live model execution.

## Suggested message to the supervisor

Dear Doctor,

I am submitting M4 — Baseline running for Saudi Digital Concierge.

Repository: https://github.com/bedooralmareni/saudi-Digital-Concierge

The repository contains two single-model baseline notebooks: local Qwen3-8B and an
OpenAI API version. Each accepts a travel request, retrieves evidence from the
Saudi tourism knowledge base, generates an answer, displays it, and saves the result.
The README inside `M4 - Baseline running` explains how to run both versions in Google Colab and lists their
runtime requirements. The local version needs a GPU; the API version requires
an OpenAI API key and credits. The M4 guide links the implementation and validation.

Best regards,
Bedoor
