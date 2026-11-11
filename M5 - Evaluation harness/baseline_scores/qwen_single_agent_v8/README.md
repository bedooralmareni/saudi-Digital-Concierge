# M5 Evaluation Harness — Qwen3-8B Single-Agent (v8)

**Experiment:** `qwen3_8b_single_m5_v8_development20` (merged from two 30-attempt batches).
**Scope:** Development-20 benchmark only — **not** a held-out final-test estimate, and not an
independent result (Development20 was used during iterative tuning).
**Dataset:** pinned SQLite KB, SHA-256 `cdbd4c20…08c986`.
**Model:** `Qwen/Qwen3-8B`, revision `b968826d…`, 4-bit NF4 on a Tesla T4.
**Seeds:** 17 / 29 / 43 (model RNG resets per case).

> **All published E2E scores are Structured E2E (automatic), not Human-reviewed E2E.**
> Structured E2E checks the explicit structured-output contract (shape, status, grounded
> options/required facts, constraint-aligned components). It does **not** verify free-text
> `message`/`reason` prose or semantic intent. Human-reviewed E2E (`e2e_reviewed`) is **0/60**
> completed — `human_review.json` is a blank template — so those columns are intentionally
> empty, never 0. Golden-set structured scoring is a contract/grounding check, **not** an
> answer-quality judgement.

## Files

| Path | Contents |
|---|---|
| `summary.csv` | Per-metric mean, sample variance and SD across the three seeds (the reported baseline). |
| `run_scores.csv` | Per-seed metric scores, with `scored_cases` per metric. |
| `scores.csv` | Per-attempt structured scores (60 rows). |
| `runs.jsonl` | The merged 60-attempt raw run log (model outputs + tool trajectories). |
| `harness/` | The Qwen v8 scorer source (`m5_evaluate.py`, `m5_contract.py`, `m5_runner.py`), offline tests and the v8 response schema — kept here for inspection. |
| `M5_Evaluation_Report_Qwen_v8.md` | Full write-up mapping C5.1–C5.4 with error analysis. |

## Baseline results (Development-20, seeds 17 / 29 / 43)

| Metric | Level | Mean | Sample SD | Cases scored / seed |
|---|---|---:|---:|:--:|
| `e2e_structured` | end-to-end | 0.900 | 0.0500 | 20 / 20 |
| `component_completion` | component | 0.917 | 0.0577 | 20 / 20 |
| `retrieval_evidence_coverage` | trajectory | 1.000 | 0.0000 | 20 / 20 |
| `schema_validity` | output | 0.983 | 0.0289 | 20 / 20 |
| `tool_syntax_validity` | trajectory | 0.786 | 0.0983 | **18 / 20** |
| `tool_error_rate` | trajectory | 0.018 | 0.0156 | **18 / 20** |
| `redundant_call_rate` | trajectory | 0.000 | 0.0000 | **18 / 20** |
| `structured_unsupported_rate` | output | 0.000 | 0.0000 | **15 / 20** |
| `e2e_reviewed` | end-to-end (human) | — | — | **0 / 20** |
| Latency (s/attempt) | process | 168.94 | 8.14 | 20 / 20 |
| Tokens / attempt | process | 19,584 | 907 | 20 / 20 |

**Why some denominators are below 20 (per seed):** a metric is reported only where it is
defined, never padded with zeros.
- `tool_syntax_validity` / `tool_error_rate` / `redundant_call_rate` → **18**: two attempts made
  no tool calls, so a per-call ratio is undefined and excluded (shown N/A with its denominator).
- `structured_unsupported_rate` → **15**: only attempts that emitted structured claims to check.
- `e2e_reviewed` → **0**: requires the (unfinished) human prose/intent review.

Seed-level `e2e_structured`: 18/20 / 17/20 / 19/20 = 0.90 / 0.85 / 0.95; sample variance 0.0025.

## Reproducing the score (C5.2)

The scorer reads each experiment's `attempts/*.json` against the pinned project snapshot, so an
**exact** rescore needs the complete original bundle. It was removed from the working tree for
tidiness but is recoverable from git history — this command restores it and re-runs the offline
scorer (no GPU, model weights or API calls needed):

```bash
git checkout dc55bf4 -- "Qwen3_8B_M5_v8_Merged_Submission/"
cd "Qwen3_8B_M5_v8_Merged_Submission/Qwen_M5_v8_Submission"
# the pinned DB + vectors are .gitignored out of the bundle — copy them from the repo root (same SHA-256):
cp ../../data/final/knowledge_base.sqlite runtime_snapshot/data/final/
cp ../../data/final/vector_store/vectors.npy runtime_snapshot/data/final/vector_store/
python test_m5.py runtime_snapshot Qwen3_8B_M5_v8_Development20/frozen20.json   # 47 offline checks
python test_v8_guards.py                                                       # 5 v8 guard checks
python -c "from m5_evaluate import evaluate_experiment; \
  print(evaluate_experiment('runtime_snapshot', \
  'Qwen3_8B_M5_v8_Development20', \
  'Qwen3_8B_M5_v8_Development20/human_review.json')[0])"
```

**Verified** in this repo: tests pass (0 failures) and the rescore reports `recorded_attempts: 60`
and reproduces `summary.csv` exactly (`e2e_structured` 0.900 ± 0.050). The two `cp` lines are
needed because the DB/vector artifacts match `.gitignore` and were not stored inside the bundle,
but the repo root carries them at the pinned SHA-256 `cdbd4c20…08c986`. The `harness/` copy in this
folder is the same scorer source, kept for direct inspection of the instrument.
