# M5 — Evaluation Harness

This folder is the single entry point for Milestone 5. It maps the deliverable to the
four marking criteria (C5.1–C5.4), shows where every artifact lives, and gives the exact
commands a third party runs to reproduce the reported baseline scores.

**M5 deliverable (course brief):** golden set of ≥ 20 cases; scoring code; baseline score
with variance across three seeds; ≥ 1 trajectory-level metric.

> Scope: M5 is the *measurement instrument* plus one or more single-agent **baselines**.
> The multi-agent treatment and the controlled comparison are M6, not M5.

---

## Criteria map (C5.1 – C5.4)

| Criterion | Where it is satisfied |
|---|---|
| **C5.1** Golden set: enough cases, defensible ground truth | `evaluation/scenario_package/` — 100 frozen cases (Development 60 / Validation 20 / Final Test 20; 50 AR / 50 EN; 70 Typical / 30 Edge). Ground truth is parameterized SQL + admissible IDs + supporting evidence in each `*/gold.json`. Re-verified by `evaluation/scenario_package/verify_ground_truth.py` → **PASS** over 100 cases / 4,904 evidence rows (`validation_report.json`). |
| **C5.2** Scoring is automated and reproducible | Scorer: `evaluation/score_runs.py` (+ `evaluation/cost_from_runs.py`). The database is pinned by SHA-256 against `evaluation/scenario_package/manifest.json`; every answer and tool call is validated against the JSON schemas in `schemas/`. See **Reproduce** below. |
| **C5.3** End-to-end **and** component-level evaluation | The scorer reports all three levels: end-to-end (`e2e_structured`), component-level (`cc_structured` / component gates, `hcs`), and **trajectory-level** (`tool_syntax_validity`, `tool_error_rate`, retrieval-in-trace). |
| **C5.4** Baseline score reported with variance across three seeds | Two single-agent baselines, each on the frozen **Development-20** benchmark, seeds **17 / 29 / 43**. Reported mean **and** sample variance / SD in `baseline_scores/` (tables below). |

**≥ 1 trajectory-level metric:** `tool_syntax_validity`, `tool_error_rate`, `redundant_call_rate`,
`retrieval_evidence_coverage` (recorded search-trajectory metrics).

---

## Reported baselines (Development-20, seeds 17 / 29 / 43)

Both baselines run the same 20 frozen cases three times. Full per-metric tables are in
`baseline_scores/<system>/summary.csv` (mean, sample variance, sample SD) and
`run_scores.csv` (per-seed scores).

### OpenAI single-agent — `gpt-6-luna`

| Metric | Level | Mean | Sample SD |
|---|---|---:|---:|
| `e2e_structured` | end-to-end | 0.767 | 0.029 |
| `cc_structured` | component | 0.767 | 0.029 |
| `hcs` (hard-constraint satisfaction) | component | 0.771 | 0.036 |
| `tool_syntax_validity` | trajectory | 1.000 | 0.000 |
| `tool_error_rate` | trajectory | 0.000 | 0.000 |
| `schema_validity` | output | 1.000 | 0.000 |
| `entity_grounding` | output | 1.000 | 0.000 |
| Latency (s) | process | 13.35 | 1.52 |
| Cost (USD/scenario) | process | 0.005 | 0.001 |

Per-seed `e2e_structured`: 0.75 / 0.80 / 0.75 (sample variance 0.000833).

### Qwen single-agent v8 — `Qwen/Qwen3-8B`

| Metric | Level | Mean | Sample SD |
|---|---|---:|---:|
| `e2e_structured` | end-to-end | 0.900 | 0.050 |
| `component_completion` | component | 0.917 | 0.058 |
| `retrieval_evidence_coverage` | trajectory | 1.000 | 0.000 |
| `tool_syntax_validity` | trajectory | 0.786 | 0.098 |
| `tool_error_rate` | trajectory | 0.018 | 0.016 |
| `schema_validity` | output | 0.983 | 0.029 |
| `structured_unsupported_rate` | output | 0.000 | 0.000 |
| Latency (s) | process | 168.94 | 8.14 |
| Tokens / attempt | process | 19,584 | 907 |

Per-seed `e2e_structured`: 18/20 / 17/20 / 19/20 = 0.90 / 0.85 / 0.95 (sample variance 0.0025).
Full write-up: `baseline_scores/qwen_single_agent_v8/M5_Evaluation_Report_Qwen_v8.md`.

> The two baselines use different harness generations (OpenAI: `frozen20-runner`; Qwen: v8)
> and are **not** compared to each other. Each is a standalone baseline; the controlled
> comparison in M6 is within a model family (single vs. multi-agent on the same model).

---

## Reproduce

Everything is offline — no model call or API key is needed to **score**; the raw run logs
are already recorded.

### 1. Golden-set ground truth (C5.1)

```bash
python evaluation/scenario_package/verify_ground_truth.py data/final/knowledge_base.sqlite
```

### 2. OpenAI baseline score with variance (C5.2 / C5.4)

```bash
pip install -r requirements.txt
cd evaluation
python score_runs.py --project .. --frozen reviews/frozen20.json \
    --runs runs.jsonl --out m5_baseline_scores
```

Reads the recorded `evaluation/runs.jsonl` (60 attempts = 20 cases × 3 seeds) and writes
`summary.csv` / `run_scores.csv` / `scores.csv`. The committed copies are in
`baseline_scores/openai_single_agent/`. The runner notebook that produced the runs —
committed **with its execution outputs** as run evidence — is
`notebooks/OpenAI_Single_Agent_Frozen20.ipynb`.

### 3. Qwen baseline score with variance (C5.2 / C5.4)

The Qwen v8 submission (its scorer `m5_evaluate.py`, runner, offline tests, and raw
attempts) is the self-contained bundle on `main` at
`Qwen3_8B_M5_v8_Merged_Submission/Qwen_M5_v8_Submission/`. From that directory:

```bash
python test_m5.py runtime_snapshot Qwen3_8B_M5_v8_Development20/frozen20.json
python test_v8_guards.py
python -c "from m5_evaluate import evaluate_experiment; \
  print(evaluate_experiment('runtime_snapshot', \
  'Qwen3_8B_M5_v8_Development20', \
  'Qwen3_8B_M5_v8_Development20/human_review.json')[0])"
```

The committed result tables are mirrored here in `baseline_scores/qwen_single_agent_v8/`.

---

## Folder contents

```
M5 - Evaluation harness/
├── README.md                              # this file — the M5 hand-in index
├── notebooks/
│   └── OpenAI_Single_Agent_Frozen20.ipynb # runner that produced the OpenAI runs (with outputs/results)
└── baseline_scores/
    ├── openai_single_agent/
    │   ├── summary.csv                     # mean / variance / SD across 3 seeds
    │   └── run_scores.csv                  # per-seed scores
    └── qwen_single_agent_v8/
        ├── summary.csv
        ├── run_scores.csv
        └── M5_Evaluation_Report_Qwen_v8.md # full Qwen v8 write-up (C5.1–C5.4 + error analysis)
```

> The Qwen v8 runner notebook can be added next to the OpenAI one under `notebooks/` when
> available; the Qwen baseline's scorer, tests and raw attempts are the bundle on `main`
> under `Qwen3_8B_M5_v8_Merged_Submission/`.

Canonical code and data referenced above live in the repository root
(`evaluation/`, `schemas/`, `data/final/`), not duplicated here.

## Note on the two baselines

Each model family has its own harness and scorer — OpenAI under `evaluation/`, Qwen v8 as its
own bundle — and that is by design. The two baselines are independent and are never compared
to each other; the only controlled comparison (M6) is **within** a model family, where the
single-agent baseline and its multi-agent treatment share the same model, scorer, split and
seeds. So the metric-name differences between families (e.g. `cc_structured` vs
`component_completion`) are expected and do not affect M5.
