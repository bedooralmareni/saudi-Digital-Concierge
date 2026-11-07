# Shared JSON contract for Qwen and OpenAI

Version **1.0**. `request.schema.json` describes the normalized user request. `response.schema.json` describes the final answer for either a recommendation list, a day-by-day itinerary, information, or clarification. `examples.json` shows one valid hotel-only case. The baseline currently returns free text and tool traces; adopting this contract requires changing its final-answer step in **both** notebooks. Do not claim existing baseline results already follow it.

## Contract

1. Keep the original scenario ID and `raw_request` outside model reinterpretation. Parse the user request once into the request object; check it before retrieval. For ambiguous/missing city/date or contradictory hard bounds, set `interpretation_status` and ask a question.
2. Use identical normalized request JSON, retrieval tools, source database snapshot and response schema in both systems. Qwen and OpenAI can use different generation mechanisms, but the same fields and external validator.
3. Use `intent=recommendations` for hotel-only/list requests; leave `days=[]`. Use `intent=itinerary` only when the user asks for a day-by-day trip. For history or field questions, use `information`.
4. Each recommended item needs an exact `record_id` from retrieved tool results. Do not infer a price, opening hour, available room, current event operation, or proximity. A missing field is `null` or `unknown`, not `false`.
5. `hotel_budget.operator=lt` means strictly less than; `lte` is inclusive. `trip_budget_sar` is separate and cannot be confirmed from the recorded hotel price alone. `dates.date_meaning` distinguishes inclusive visits, hotel checkout, and event-start-month questions.
6. The response status describes the whole request. `constraint_results` records the individual hard constraints. For a partial answer, show supported options and mark unresolved or unsatisfied constraints. If asking for clarification, recommendations and days can be empty.
7. For an itinerary, populate `days` with numbered days and evidence-backed items; `recommendations=[]`. Day dates are `null` if not established. No itinerary is forced by the schema for hotel-only cases.

All objects have `additionalProperties: false`, every property is required, and potentially unavailable scalar values use `null`. This keeps the schema within the common strict-output shape. Structural JSON validation still does **not** establish factual correctness or completeness: verify IDs, values, count, dates, language and constraint logic against the KB and scenario gold separately.

## Integrating

For OpenAI Chat Completions, use the response schema only in the **final answer** call:

```python
import json
from pathlib import Path

schema = json.loads(Path('response.schema.json').read_text(encoding='utf-8'))
response_format = {
    'type': 'json_schema',
    'json_schema': {'name': 'sdc_response_v1', 'strict': True, 'schema': schema},
}
# Pass response_format=response_format on the final completion request.
# Keep the intermediate tool-calling requests and their tool schemas separate.
```

For local Qwen, send the same field descriptions and an empty object template with the system prompt. Parse the generated final JSON and validate it locally. If the Qwen serving stack supports constrained JSON generation, pass `response.schema.json` there as well; the current notebook uses ordinary text generation, so prompting alone does not guarantee validity. Record parse/validation failures rather than silently changing the answer. Use the same response validation in both conditions.

The current notebooks' `search_hotels`, `search_places` (including entertainment), and `search_events` retrieve the supporting records. The output schema does not change their tool contracts. Avoid attaching the JSON schema to the **tool call** itself; it describes the model's final answer.

Run `python build_schema.py` after deliberate contract edits and `python validate_contract.py` to check example structure and schema shape. Keep version and keys fixed during an experimental run; any schema revision requires rebuilding both systems and rerunning comparisons.
