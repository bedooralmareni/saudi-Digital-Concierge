# Qwen v8 — M5 single-agent hand-in (merged)

This is a **single offline-reproducible submission snapshot** assembled from the two original Qwen v8 10-case batches. No Qwen model was run during merging. Original attempt records were not altered.

## Files

- `M5_Evaluation_Report_Qwen_v8.md`: maps submission evidence to C5.1–C5.4, explains variance and limits.
- `frozen20.json`: 20 frozen Development prompts and three seed IDs.
- `M5_PROTOCOL.txt`, `requirements_recorded.txt`: evaluation protocol and Python package versions.
- `m5_runner.py`, `m5_contract.py`: Qwen v8 single-agent runner and public schema/tool contract.
- `m5_evaluate.py`: offline evaluator (requires `m5_contract.py` adjacent).
- `test_m5.py`, `test_v8_guards.py`: offline reproducibility / regression tests.
- `runtime_snapshot/evaluation/scenario_package/development/gold.json`: original gold with evidence (60 Development records including frozen 20); never expose it to model prompts.
- `runtime_snapshot/data/final/knowledge_base.sqlite`: pinned source database.
- `runtime_snapshot/data/final/vector_store/*`: pinned retrieval index and metadata.
- `runtime_snapshot/src/shared_tools/kb_tools.py`: original search implementations.
- `runtime_snapshot/schemas/response.schema.json`, `response_v8.schema.json`: output schema and final v8 contract.
- `Qwen3_8B_M5_v8_Development20/experiment_manifest.json`: model version, seeds, settings, hashes and environment.
- `Qwen3_8B_M5_v8_Development20/attempts/*.json`: all 60 original attempt records, one per seed/case, including traces.
- `Qwen3_8B_M5_v8_Development20/runs.jsonl`: merged 60-attempt log.
- `Qwen3_8B_M5_v8_Development20/m5_results/`: all freshly rescored tables, diagnostics, readiness, narrative review queue.
- `Qwen3_8B_M5_v8_Development20/human_review.json`: empty review template for 60 records, not evidence of completed prose review.

## Offline instructions (run from this directory)

Install Python 3 and `jsonschema`, then:

```bash
python test_m5.py runtime_snapshot Qwen3_8B_M5_v8_Development20/frozen20.json
python test_v8_guards.py
python -c "from m5_evaluate import evaluate_experiment; print(evaluate_experiment('runtime_snapshot','Qwen3_8B_M5_v8_Development20','Qwen3_8B_M5_v8_Development20/human_review.json')[0])"
```

The result should contain `automatic_report_ready: True` and `recorded_attempts: 60`. For final numbers read `Qwen3_8B_M5_v8_Development20/m5_results/summary.csv`. **Do not use the separate per-batch summary.csv files** for a 60-attempt M5 claim. No API or Qwen generation is needed for scoring.

## Ethical/evaluation limits

This is a Development baseline, not an untouched independent test. Structured success is not prose factuality. No full human review has been completed. Local GPU cost not priced. Historical database values are not real-time room availability.
