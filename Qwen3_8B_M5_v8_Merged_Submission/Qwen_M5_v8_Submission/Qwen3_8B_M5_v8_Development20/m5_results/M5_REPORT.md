# M5 — Qwen3-8B single-agent

Experiment: Qwen3_8B_M5_v8_Development20
Recorded attempts: 60/60. Split: Development; mode: development20; unique cases: 20. Seeds: [17, 29, 43].
Primary endpoint: structured task success; full narrative claims are not included without the review.

| Metric | Mean | Sample SD across seed means | Sample variance |
|---|---:|---:|---:|
| e2e_structured | 0.900000 | 0.050000 | 0.002500 |
| component_completion | 0.916667 | 0.057735 | 0.003333 |
| retrieval_evidence_coverage | 1.000000 | 0.000000 | 0.000000 |
| schema_validity | 0.983333 | 0.028868 | 0.000833 |
| tool_syntax_validity | 0.786486 | 0.098306 | 0.009664 |
| tool_error_rate | 0.018018 | 0.015604 | 0.000243 |
| redundant_call_rate | 0.000000 | 0.000000 | 0.000000 |
| structured_unsupported_rate | 0.000000 | 0.000000 | 0.000000 |
| e2e_reviewed | Pending / not applicable | Pending / not applicable | Pending / not applicable |
| seconds | 168.940350 | 8.142546 | 66.301055 |
| generation_seconds | 168.723827 | 8.152051 | 66.455942 |
| tool_calls | 1.733333 | 0.202073 | 0.040833 |
| model_calls | 4.150000 | 0.229129 | 0.052500 |
| total_tokens | 19584.500000 | 907.211038 | 823031.867500 |

## Failure analysis
- structured_inconsistency: 6 attempts
- component_failure: 5 attempts
- grounding_inconsistent: 4 attempts
- wrong_status: 4 attempts
- invalid_output_contract: 1 attempts
- response_shape: 1 attempts
- schema_invalid: 1 attempts

## Reporting limits
- Development results do not establish untouched-test generalization.
- 60 attempts on 20 cases are not independent tasks; SD is across three seed-level scores.
- Quantized GPU sampling is seeded but bitwise identity across different hardware/software is not guaranteed.
- Historical database records do not establish current availability or live prices.
- v5 vs v4 updates the system/final prompts only, with unchanged scoring logic, generation settings, one-pass JSON repair and tools. The earlier v3-v4 comparison was not a prompt-only ablation. Old OpenAI v1 results are not a controlled architecture comparison.
- smoke5 is diagnostic only and does not meet the 20-case M5 requirement. Validation and Final Test need separately validated requirements and are not supported by this evaluator.
- Local GPU monetary cost is unpriced. Latency includes model/tools/checkpoint overhead; generation_seconds excludes model loading.
- No failed attempt is silently retried or omitted; infrastructure errors are separately identified.

## Human review
Completed: 0/60. Fill human_review.json with evidence notes and rerun the offline evaluation cell.
Do not describe structured_unsupported_rate as the hallucination rate of the complete prose answer.