#!/usr/bin/env python3
"""Calculate documented-model estimated token spend from existing `runs.jsonl`.

Reads saved `api_calls[].usage` only; NEVER calls an LLM or modifies original logs.
Per API call, prompt_tokens = ordinary + cached + cache_write tokens.
Reject inconsistent/missing usage rather than guessing costs.
"""
import argparse
import csv
import json
from pathlib import Path

PRICING_DEFAULT = Path(__file__).with_name("pricing_gpt6_luna.json")


def price_attempt(run, price_table):
    models = price_table["models"]
    calls = run.get("api_calls")
    if not isinstance(calls, list) or not calls:
        return {"estimated_cost_usd": None, "cost_status": "missing_api_calls", "price_tier": None,
                "price_source": price_table.get("source_url"), "costed_calls": 0}
    amount = 0.0
    tiers = set()
    for call in calls:
        model = call.get("model") or run.get("model")
        definition = models.get(model)
        if definition is None:
            return {"estimated_cost_usd": None, "cost_status": f"unpriced_model:{model}",
                    "price_tier": None, "price_source": price_table.get("source_url"), "costed_calls": 0}
        u = call.get("usage")
        if not isinstance(u, dict) or not all(isinstance(u.get(k), int) and u[k] >= 0
                                              for k in ("prompt_tokens", "completion_tokens")):
            return {"estimated_cost_usd": None, "cost_status": "missing_or_invalid_usage",
                    "price_tier": None, "price_source": price_table.get("source_url"), "costed_calls": 0}
        prompt = u["prompt_tokens"]
        out = u["completion_tokens"]
        detail = u.get("prompt_tokens_details") or {}
        if not isinstance(detail, dict):
            return {"estimated_cost_usd": None, "cost_status": "invalid_prompt_details",
                    "price_tier": None, "price_source": price_table.get("source_url"), "costed_calls": 0}
        # Without a breakdown, treating cached/write as zero would overstate some costs.
        if not all(isinstance(detail.get(k), int) and detail[k] >= 0
                   for k in ("cached_tokens", "cache_write_tokens")):
            return {"estimated_cost_usd": None, "cost_status": "missing_cache_breakdown",
                    "price_tier": None, "price_source": price_table.get("source_url"), "costed_calls": 0}
        cached = detail["cached_tokens"]
        written = detail["cache_write_tokens"]
        ordinary = prompt - cached - written
        if ordinary < 0:
            return {"estimated_cost_usd": None, "cost_status": "inconsistent_cache_breakdown",
                    "price_tier": None, "price_source": price_table.get("source_url"), "costed_calls": 0}
        tier = "long" if prompt > definition["long_context_threshold_prompt_tokens"] else "short"
        rates = definition[tier]
        tiers.add(tier)
        amount += (ordinary * rates["input_per_million"] + cached * rates["cached_input_per_million"]
                   + written * rates["cache_write_per_million"] + out * rates["output_per_million"]) / 1_000_000
    return {"estimated_cost_usd": round(amount, 10), "cost_status": "estimated_from_logged_usage",
            "price_tier": "+".join(sorted(tiers)), "price_source": price_table.get("source_url"),
            "costed_calls": len(calls)}


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    p=argparse.ArgumentParser(description="Compute per-attempt costs offline; no API access needed.")
    p.add_argument("--runs", required=True, nargs="+")
    p.add_argument("--pricing", default=str(PRICING_DEFAULT))
    p.add_argument("--out", required=True, help="Folder to write estimated_costs.csv/json and summary.json")
    args=p.parse_args()
    pricing=json.loads(Path(args.pricing).read_text(encoding="utf-8"))
    out=Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows=[]
    for run_path in args.runs:
        for line in Path(run_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            run=json.loads(line)
            result=price_attempt(run, pricing)
            rows.append({"attempt_id":run.get("attempt_id"),"scenario_id":run.get("scenario_id"),
                         "run_id":run.get("run_id"), "system":run.get("system"),
                         "model":run.get("model"), "seconds":run.get("elapsed_seconds"),
                         "prompt_tokens":(run.get("usage_totals") or {}).get("prompt_tokens"),
                         "completion_tokens":(run.get("usage_totals") or {}).get("completion_tokens"),
                         "total_tokens":(run.get("usage_totals") or {}).get("total_tokens"), **result})
    write_csv(out/"estimated_costs.csv",rows)
    (out/"estimated_costs.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    complete=[r for r in rows if r["estimated_cost_usd"] is not None]
    summary={"attempts":len(rows),"priced_attempts":len(complete),
             "unpriced_attempts":len(rows)-len(complete),
             "total_estimated_usd":round(sum(r["estimated_cost_usd"] for r in complete),8),
             "pricing_reference":pricing["source_url"],"pricing_checked":pricing["source_checked_date"],
             "assumed_service_tier":pricing["service_tier"],"cache_write_ttl":pricing["cache_write_ttl"],
             "caveat":"Estimates from token usage, not billable-invoice verification; extra fees and uplifts not included."}
    (out/"cost_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
