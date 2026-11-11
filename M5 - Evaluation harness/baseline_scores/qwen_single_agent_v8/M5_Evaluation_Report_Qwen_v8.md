# M5 Evaluation Harness — Qwen3-8B Single-Agent (v8)

**Experiment:** `qwen3_8b_single_m5_v8_development20` (merged from two batches, without rerunning the model)  
**Scope:** Development20 benchmark only; not a held-out final-test estimate.  
**Dataset:** pinned SQLite knowledge base, SHA-256 `cdbd4c20632e57c87d2ffb3ef97f603bfd1150cbb0ee38a297e2ce736f08c986`.  
**Model:** `Qwen/Qwen3-8B`, revision `b968826d9c46dd6066d109eabc6255188de91218`, 4-bit NF4 quantization on Tesla T4.  
**Settings:** tools temperature 0.7, final temperature 0.2, top_p 0.8, top_k 20, tool max_new_tokens 512, final max_new_tokens 3072, max 8 tool calls, max 2 model-powered final repairs.  
**Replication:** seeds 17, 29, 43 are actual model RNG resets per case; GPU/library differences may prevent bit-for-bit repetition.

## C5.1 — Golden benchmark and ground truth

20 fixed, distinct Development questions (14 Typical, 6 Edge; 10 Arabic, 10 English). The exact question text and checksums are in `frozen20.json`; admissible IDs, required counts, distinct-option groups, SQL-grounded evidence and expected behavior are in `runtime_snapshot/evaluation/scenario_package/development/gold.json`. The 60-case Development gold file contains the 20 frozen cases as a subset. Database and code are pinned and hashed. Gold is read by the offline evaluator, **not passed to the inference model**.

## C5.2 — Automated, reproducible scoring

`m5_evaluate.py` evaluates recorded outputs and tool trajectories against the pinned database, JSON schema, and gold reference. Both input batch archives were checked for matching configuration and module hashes; 30+30 disjoint attempt records were merged. A fresh **offline** evaluator run succeeded with 60/60 records and all 3 seeds complete. `m5_results/scores.csv`, `run_scores.csv`, and `summary.csv` were regenerated from the merged runs (not averaged from partial-batch reports). Offline regression tests passed: 47 checks in `test_m5.py` and 5 v8 guard checks in `test_v8_guards.py`.

## C5.3 — End-to-end, component, and trajectory evaluation

- **Structured E2E Success:** correct structured output, expected status, grounded options/required facts and constraint-aligned components; 1/0 per attempt. It does *not* attest to all free-text claims.
- **Component Completion:** fraction of scenario components meeting the evaluator's ground-truth gates; macro-averaged over cases per seed.
- **Trajectory metrics:** Tool Syntax Validity (valid attempted tool actions / attempted tool actions), Tool Error Rate (error actions / attempted actions), and Retrieval Evidence Coverage. These measure the recorded search trajectory; they are not identical to a manually audited full semantic trajectory-validity score.
- **Additional diagnostics:** Schema Validity, Structured Unsupported Rate, Redundant Call Rate, tool/model calls, wall time, generation time and tokens.

## C5.4 — Baseline results across three seeds

| Metric | Mean | Sample SD | Sample variance |
|---|---:|---:|---:|
| Structured E2E | 90.00% | 5.00 pp | 0.002500 |
| Component completion | 91.67% | 5.77 pp | 0.003333 |
| Retrieval evidence coverage | 100.00% | 0.00 pp | 0.000000 |
| JSON schema validity | 98.33% | 2.89 pp | 0.000833 |
| Tool syntax validity | 78.65% | 9.83 pp | 0.009664 |
| Tool error rate | 1.80% | 1.56 pp | 0.000243 |
| Redundant call rate | 0.00% | 0.00 pp | 0.000000 |
| Structured unsupported-claim rate | 0.00% | 0.00 pp | 0.000000 |
| Mean wall time per attempt (s) | 168.94 | 8.14 | 66.30 |
| Mean tokens per attempt | 19,584.50 | 907.21 | 823,031.87 |

**Seed-level structured E2E:** 17 → 18/20 (90%); 29 → 17/20 (85%); 43 → 19/20 (95%). Total: **54/60 (90%)**. Standard deviation is computed over the three **seed-level case means**, not by treating attempts as 60 independent questions. Sample variance for E2E proportions is **0.0025**.

## Error analysis

Six unsuccessful structured attempts across four scenarios:

- `SDC-035`, seed 29: schema-invalid response; incorrect status and missing component fulfillment.
- `SDC-043`, seeds 17, 29, 43: grounding and response-status inconsistency.
- `SDC-045`, seed 17: structured inconsistency.
- `SDC-058`, seed 29: grounding and component inconsistency.

These categories can overlap within a failed attempt. The run-level audit and exact causes are in `m5_results/diagnostics.csv` and `failure_analysis.csv`.

## Limitations and unfinished review

- **Full reviewed E2E, prose factuality and semantic intent:** 0/60 human review records completed (`human_review.json` remains a blank review template). Do not claim these scores are available or substitute 0 for pending review.
- **Development-set caveat:** Development20 was used during iterative tuning; these are not unbiased Validation/Final Test results. Report them as *Development baseline results*.
- **Cost:** local Colab GPU monetary cost is not quantified; tokens and time are recorded instead. Do not invent a USD API cost.
- **Tool Syntax Validity is 78.65%**, despite a 1.80% tool error rate: syntactic/contract issues and tool execution errors are different measures. The trajectory merits additional analysis rather than being described as completely valid.
- Some generated system reports inside earlier *individual batch* archives say 30/60 and show pending averages. They are correct **for each incomplete batch** but not for the combined experiment. Use only the freshly merged `m5_results/summary.csv` and this consolidated report for the 60-attempt results.
- **Repository layout (updated):** the reported tables, per-attempt `scores.csv`, raw `runs.jsonl`
  and the scorer source (`harness/`) are kept in this folder. The complete original submission
  bundle — which also carried the pinned `runtime_snapshot` (database, vector index, gold) and the
  per-attempt records the scorer reads — was removed from the working tree to keep the repository
  tidy; it is recoverable from git history at commit `dc55bf4` (see this folder's `README.md` for
  the exact `git checkout` + rescore commands). No model weights are included; regenerating Qwen
  outputs needs the model revision, a GPU and the recorded packages, but **rescoring** needs no GPU
  or model calls.
