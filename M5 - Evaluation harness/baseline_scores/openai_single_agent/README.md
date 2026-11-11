# M5 Evaluation Harness — OpenAI Single-Agent

**Experiment:** `openai_single_frozen20_v1`
**Scope:** Development-20 benchmark only; not a held-out final-test estimate.
**Dataset:** pinned SQLite knowledge base, SHA-256 `cdbd4c20632e57c87d2ffb3ef97f603bfd1150cbb0ee38a297e2ce736f08c986`.
**Model:** `gpt-6-luna`, Chat Completions endpoint, `temperature=0`, `reasoning_effort=none`, max 8 tool rounds.
**Project commit:** `c87473d`.
**Replication:** seeds 17, 29, 43 are three independent repetitions (the API `seed` is left unset, so run-to-run spread is observable rather than forced to zero).

## C5.1 — Golden benchmark and ground truth

20 fixed, distinct Development questions (14 Typical, 6 Edge; 10 Arabic, 10 English), the same
frozen set used by every system. Exact question text and checksums are in
`evaluation/reviews/frozen20.json`; admissible IDs, required counts, SQL-grounded evidence and
expected behavior are in `evaluation/scenario_package/development/gold.json`. Gold is read by the
offline scorer **only after inference**, never placed in the model's messages.

## C5.2 — Automated, reproducible scoring

`evaluation/score_runs.py` scores the recorded outputs and tool trajectories against the pinned
database, the JSON schemas in `schemas/`, and the gold reference. The database is verified by
SHA-256 against `manifest.json` before scoring. The tables in this folder were regenerated from
the merged 60-attempt `evaluation/runs.jsonl` (20 cases × 3 seeds). Reproduce with:

```bash
pip install -r requirements.txt
cd evaluation
python score_runs.py --project .. --frozen reviews/frozen20.json \
    --runs runs.jsonl --out m5_baseline_scores
```

Runner notebook (with its execution outputs):
`M5 - Evaluation harness/notebooks/OpenAI_Single_Agent_Frozen20.ipynb`.

## C5.3 — End-to-end, component, and trajectory evaluation

- **Structured E2E (`e2e_structured`):** correct structured output, expected status, grounded
  options/required facts and constraint-aligned components; 1/0 per attempt. It does *not* attest
  to every free-text claim (prose/intent review is the separate `e2e` metric, left unscored here).
- **Component (`cc_structured`, `hcs`):** per-component pass gates and hard-constraint satisfaction.
- **Trajectory (`tool_syntax_validity`, `tool_error_rate`):** validity of the recorded tool-call
  sequence; whether every recommended ID actually appeared in the retrieval trace.
- **Additional diagnostics:** `schema_validity`, `entity_grounding`, `structured_ucr`
  (unsupported-claim rate), `structured_consistency_pass`, latency and cost per attempt.

## C5.4 — Baseline results across three seeds

> **All E2E scores here are Structured E2E (automatic), not Human-reviewed E2E.** Structured E2E
> checks the structured-output contract and grounding; it does not verify free-text prose or
> intent. The reviewed metrics (`e2e`, `cc`, `tv`, `ucr`) need an optional human review that is
> not completed, so they are left empty — never scored as 0.

| Metric | Level | Mean | Sample SD | Sample variance | Cases scored / seed |
|---|---|---:|---:|---:|:--:|
| `e2e_structured` | end-to-end | 0.767 | 0.0289 | 0.000833 | 20 / 20 |
| `cc_structured` | component | 0.767 | 0.0289 | 0.000833 | 20 / 20 |
| `hcs` (hard-constraint satisfaction) | component | 0.771 | 0.0361 | 0.001302 | **16 / 20** |
| `tool_syntax_validity` | trajectory | 1.000 | 0.0000 | 0.000000 | 20 / 20 |
| `tool_error_rate` | trajectory | 0.000 | 0.0000 | 0.000000 | 20 / 20 |
| `schema_validity` | output | 1.000 | 0.0000 | 0.000000 | 20 / 20 |
| `entity_grounding` | output | 1.000 | 0.0000 | 0.000000 | **13 / 20** |
| `structured_ucr` (unsupported-claim rate) | output | 0.000 | 0.0000 | 0.000000 | **13 / 20** |
| `structured_consistency_pass` | output | 1.000 | 0.0000 | 0.000000 | 20 / 20 |
| Latency (s/attempt) | process | 13.35 | 1.52 | 2.324 | 20 / 20 |
| Cost (USD/attempt) | process | 0.00478 | 0.00111 | 1.24e-06 | 20 / 20 |

**Seed-level `e2e_structured`:** 17 → 0.75; 29 → 0.80; 43 → 0.75. Mean **0.767**, sample variance
**0.000833** (ddof=1 over the three seed-level case means, not over 60 independent attempts).

**Why some denominators are below 20 (per seed):** a metric is reported only where it is defined,
never padded with zeros.
- `hcs` → **16**: only the scenarios that carry a hard constraint to satisfy (e.g. hotel
  price/rating/capacity requests) are in scope.
- `entity_grounding` / `structured_ucr` → **13**: only attempts that actually selected items —
  there is nothing to ground or to check for unsupported claims when no option was returned.
- The reviewed `e2e` / `cc` (5/20) and `tv` / `ucr` (0/20) depend on the unfinished human review
  and are excluded from the reported means.

## Files

| File | Contents |
|---|---|
| `summary.csv` | Per-metric mean, sample variance and SD across the three seeds (the reported baseline). |
| `run_scores.csv` | Per-seed metric scores. |

Per-attempt detail and the raw run log live in `evaluation/m5_baseline_scores/` and
`evaluation/runs.jsonl`.

## Limits

This is a Development baseline, not an untouched independent test. Structured success is not prose
factuality: `e2e`, `cc`, `tv` and `ucr` stay unscored because they need an optional human
prose/intent review. Hotel prices are historical recorded values, not real-time availability.
