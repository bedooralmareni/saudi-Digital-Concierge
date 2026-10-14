# M4 — Baseline running

Saudi Digital Concierge accepts a travel request, retrieves Saudi tourism
knowledge-base evidence, and uses a single agent to generate and display an answer.

Repository: [bedooralmareni/saudi-Digital-Concierge](https://github.com/bedooralmareni/saudi-Digital-Concierge).

## Submitted notebooks

| Notebook | Answer model | Runtime | API key |
| --- | --- | --- | --- |
| [Local Qwen single-agent](notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_local_Qwen_single_model_baseline.ipynb) | `Qwen/Qwen3-8B`, 4-bit | Google Colab GPU | None |
| [OpenAI API single-agent](notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_OpenAI_API_single_agent_baseline.ipynb) | `gpt-6-luna` | Google Colab CPU | Your own OpenAI key and credits |

Both notebooks use one agent with three tools: `search_hotels`, `search_places`,
and `search_events`. Hotels and events come from SQLite; places and entertainment
are ranked with multilingual E5 embeddings and FAISS. One agent can make several
model and tool calls before answering. Qwen runs on the Colab GPU; Luna generates
answers through the OpenAI API. They are alternative M4 baselines, not a completed
controlled comparison of architectures.

## Run the local Qwen notebook

1. [Open Qwen in Colab](https://colab.research.google.com/github/bedooralmareni/saudi-Digital-Concierge/blob/main/M4%20-%20Baseline%20running/notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_local_Qwen_single_model_baseline.ipynb).
2. Select **Runtime → Change runtime type → GPU**, such as T4. Start with a fresh runtime.
3. Run cells **1–6** in order. They install packages, check GPU availability, clone
   the repository, load the stored KB and CPU embeddings, and load Qwen3-8B in 4-bit.
   Internet is needed for packages, the repository, and first-time model downloads.
   If installation requests a restart, restart and rerun from the top.
4. Run cells **7–10** to define the search tools and single-agent loop.
5. Run cell **11** to define the five example scenarios, then cell **12** to run them.
   The output shows each request and its Qwen answer; internal tool logs are hidden.

No Ollama installation or OpenAI API key is required. Colab GPU availability and
runtime limits depend on your account. First setup can take several minutes.

To run one custom request after cell 10, add a code cell:

```python
request = "Suggest three hotels in Riyadh for two people, at most 400 SAR per night, with guest ratings of at least 8/10."
result = run_agent(request, max_steps=10, max_retries=2)
print(result["answer"])
print("Status:", result["status"])
```

The agent chooses the tool arguments from your request. The current notebook keeps
the five scenario results in `ALL_RESULTS` in memory; it does not export them automatically.

## Run the OpenAI API notebook

1. [Open the API notebook in Colab](https://colab.research.google.com/github/bedooralmareni/saudi-Digital-Concierge/blob/main/M4%20-%20Baseline%20running/notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_OpenAI_API_single_agent_baseline.ipynb).
2. Select a **CPU runtime**. A GPU is unnecessary for this notebook.
3. Run cells **2–6** in order to install packages, clone the repository, load the KB,
   and load the multilingual embedding model on CPU.
4. Before running cell **7**, add `OPENAI_API_KEY` in Colab's **Secrets** panel and
   enable notebook access, or enter your key at the hidden prompt. Your API project
   needs credits and access to `gpt-6-luna`. Do not paste a key into notebook source.
5. Run cells **8–11** to define the tools and agent. The configured model is
   `gpt-6-luna`, with `reasoning_effort="none"`, temperature 0, and mandatory tool use
   on the first model call.
6. Run cell **12** to define the five scenarios, then cell **13** to run all five.
   Each scenario may make several paid API calls. The output shows requests and answers.
7. In Colab's **Files** panel, download `openai_baseline_results.json` from `/content/`
   before closing the runtime. It contains requests, answers, status, tool traces,
   elapsed time, and the model name.

To run one custom request, use the same `run_agent` example above after cell 11,
and skip cell 13. Requests and retrieved evidence are sent to OpenAI. The API key
is not written to the result JSON.

## Inspect and save evidence

For either notebook, inspect the five-scenario results after the final cell:

```python
print("Status:", ALL_RESULTS["S1"]["status"])
print(json.dumps(ALL_RESULTS["S1"]["trace"], ensure_ascii=False, indent=2))
```

To export Qwen results, add and run this cell after cell 12:

```python
from google.colab import files

output_path = "/content/qwen_baseline_results.json"
with open(output_path, "w", encoding="utf-8") as file:
    json.dump(
        {"model": MODEL_ID, "results": ALL_RESULTS},
        file, ensure_ascii=False, indent=2, default=str,
    )
files.download(output_path)
```

For a custom request, inspect `result["trace"]` and save `result` with its request
and model name instead of exporting `ALL_RESULTS`.

## Knowledge-base files and dependencies

Both notebooks expect these files in the cloned repository:

- `data/final/knowledge_base.sqlite`
- `data/final/vector_store/vectors.npy`
- `data/final/vector_store/vector_meta.csv`
- `data/final/vector_store/index_info.json`

The repository currently tracks a KB snapshot. These notebooks check for the files
and load them; they do **not** automatically rebuild missing artifacts. The real
index must use `intfloat/multilingual-e5-base`, normalized 768-dimensional vectors.

If a file is missing, after the clone cell add and run this cell, then rerun the
artifact-check cell and continue:

```python
import os
import sys
import subprocess

environment = dict(os.environ, EMBED_MODEL="intfloat/multilingual-e5-base")
environment.pop("HF_HUB_OFFLINE", None)
environment.pop("TRANSFORMERS_OFFLINE", None)
for module in (
    "src.entity_resolution.resolve",
    "src.database.build_sqlite",
    "src.vector_store.build_index",
):
    subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_DIR, env=environment, check=True,
    )
```

Rebuilding uses the processed CSVs and can take time to embed all records. The
offline stub is for tests, not the submitted model demonstrations.

The project has one [requirements.txt](../requirements.txt). The submitted notebooks
currently install their own package lists in their first installation cells; they
do not read that file. For a local project environment, install it with
`python -m pip install -r requirements.txt` from the repository root.

## M4 acceptance and current verification

The required workflow is **travel request → KB retrieval → model answer → display**.
Both uploaded notebooks contain saved answers for five scenarios and no saved error
outputs. Review the trace to confirm that retrieval succeeded for the demonstrated
request. A nonempty answer or `completed` status alone does not prove grounding or
constraint satisfaction. Five examples are demonstrations, not the final evaluation set.

During the latest review, `python -m pytest -q` reported **27 passed, 12 failed,
3 errors**. Baseline tests reference the replaced notebook filenames and previous
cell layouts, so they need updating. The older **42 passed** record in
[VERIFICATION.md](VERIFICATION.md) applies to the earlier notebook versions.

For submission, save the executed notebooks and exported results, identify each
model, and verify that the recipient can open the repository. These Colab links
point to `main`; the new notebook files must be committed and pushed before the
links can open them from GitHub.

## Known limitations and troubleshooting

Hotel prices are historical snapshots, not current quotes. Event date overlap does
not confirm live availability. Missing activity or meal prices are unknown, and
city coverage varies. Review generated names, ratings, costs, and itinerary claims
against the actual evidence.

The latest review found Qwen recommendations absent from the indexed KB and unrated
restaurants despite a requested minimum rating. Qwen can also finish without a
successful tool call. Luna's S4 answer incorrectly calls the budget impossible
when unknown costs mean it cannot be verified. These are recorded baseline failures;
this documentation update does not change the notebook code or saved answers.

| Problem | Action |
| --- | --- |
| Missing package after installation | Restart if requested, then rerun cells in order. |
| Qwen GPU error or out of memory | Select a GPU and start a fresh runtime. |
| API authentication, credit, or access error | Check your own secret, API project, and model access. |
| Missing KB files | Use the rebuild cell above and rerun the file checks. |
| No retrieved matches | Check the tool arguments and dataset coverage. |
| Answer violates a requirement | Record the failure and compare the answer with its trace. |

The [evaluation notes](evaluation_notes.md) describe planned research. The separate
[submission guide](SUBMISSION.md) and verification record still describe aspects of
the previous notebook versions; use this README for the current notebook filenames,
model names, and run steps. The [main project README](../README.md) is maintained separately.
