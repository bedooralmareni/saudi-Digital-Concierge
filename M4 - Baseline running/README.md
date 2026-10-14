# M4 — Single-agent baseline

**Travel request → retrieve KB evidence → generate an answer → display it.**

[Repository](https://github.com/bedooralmareni/saudi-Digital-Concierge)

## Choose a notebook

| Notebook | Model | Requirements |
| --- | --- | --- |
| [OpenAI API](notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_OpenAI_API_single_agent_baseline.ipynb) | `gpt-6-luna` | CPU, internet, API key and credits |
| [Local Qwen](notebooks/M4_%E2%80%94_Saudi_Digital_Concierge_local_Qwen_single_model_baseline.ipynb) | `Qwen/Qwen3-8B`, 4-bit | Compatible NVIDIA GPU and CUDA-enabled PyTorch |

Use the API version if your computer has no compatible GPU.

## Setup on your computer

Install **Git** and **Python 3.11**, then run in Windows PowerShell:

```powershell
git clone https://github.com/bedooralmareni/saudi-Digital-Concierge.git
cd saudi-Digital-Concierge
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m jupyter lab
```

On Linux/macOS, use `python3.11` to create the environment and `.venv/bin/python`
for the remaining commands. Qwen's current notebook requires CUDA.

In Jupyter, open **M4 - Baseline running → notebooks** and select the Python kernel
from `.venv`. Skip the notebook's `%pip install` cell; dependencies are already installed.

Replace `PROJECT_DIR` in **Qwen cell 3** or **API cell 4** with your cloned repository path:

```python
PROJECT_DIR = r"C:\Users\YOUR_NAME\saudi-Digital-Concierge"
```

For Qwen, `torch.cuda.is_available()` must return `True`. If needed, install the
appropriate CUDA build using the [PyTorch setup guide](https://docs.pytorch.org/get-started/locally/).
First-time model downloads may take several minutes.

## Run

- **API:** Run cells **3–13** in order. Enter your key at the hidden prompt in cell 7.
  The final cell runs five scenarios and saves `openai_baseline_results.json` in the
  kernel's working folder. Each scenario may make several paid API calls.
- **Qwen:** Run cells **2–12** in order. The final cell runs five scenarios and displays
  their answers. Results remain in `ALL_RESULTS` until you save them.

To try one request, run through **API cell 11** or **Qwen cell 10**, skip the scenario
batch, and add this cell:

```python
request = "Suggest three hotels in Riyadh for two people, at most 400 SAR per night, rated at least 8/10."
result = run_agent(request, max_steps=10, max_retries=2)
print(result["answer"])
print(json.dumps(result["trace"], ensure_ascii=False, indent=2))
```

## Save results

Save the executed notebook with **File → Save Notebook**. The API batch already
writes its JSON file; use `import os; print(os.getcwd())` to locate it.

After the Qwen batch, add this cell to save its model, answers, and evidence:

```python
from pathlib import Path

folder = Path(PROJECT_DIR) / "baseline_results"
folder.mkdir(exist_ok=True)
(folder / "qwen_results.json").write_text(
    json.dumps({"model": MODEL_ID, "results": ALL_RESULTS},
               ensure_ascii=False, indent=2, default=str),
    encoding="utf-8",
)
```

Rename result files to preserve separate runs. For a custom request, save `request`
and `result` with the model name instead of `ALL_RESULTS`.

## If KB files are missing

From the repository root, run these commands, then restart and rerun the notebook:

```powershell
.\.venv\Scripts\python.exe -m src.entity_resolution.resolve
.\.venv\Scripts\python.exe -m src.database.build_sqlite
.\.venv\Scripts\python.exe -m src.vector_store.build_index
```

Leave `EMBED_MODEL` unset to use the real multilingual embedding model.

Hotel prices are historical snapshots; live availability and missing costs are
unknown. Check generated claims against the evidence. The saved demos were run
in Colab; fresh local execution remains unverified. Existing baseline tests still
target earlier notebooks and need updating.
