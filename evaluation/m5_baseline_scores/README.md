# Baseline results — frozen Development-20

Automated M5 scoring of the single-agent OpenAI baseline, produced by:

```bash
cd evaluation
python score_runs.py --project .. --frozen reviews/frozen20.json \
    --runs runs.jsonl --out m5_baseline_scores
```

- **System / model:** `openai_single_agent` / `gpt-6-luna`
- **Benchmark:** frozen Development-20 (`reviews/frozen20.json`), seeds 17 / 29 / 43
- **Project commit:** `c87473d`
- **Database SHA-256:** `cdbd4c20632e57c87d2ffb3ef97f603bfd1150cbb0ee38a297e2ce736f08c986`

## Files

| File | Contents |
|---|---|
| `summary.csv` | Per-metric mean, sample variance and SD across the three seeds (the reported baseline). |
| `run_scores.csv` | Per-seed metric scores. |
| `scores.csv` | Per-attempt structured scores (flat columns). |
| `scores.json` | Per-attempt scores with full nested component/action detail. |

The per-reviewer artifacts (`review_queue.json`, `review_template.json`) are regenerated on demand and are not committed. The `e2e` / `cc` / `tv` / `ucr` columns stay null until the optional human prose/intent review is completed; the `*_structured` columns are the automated baseline.
