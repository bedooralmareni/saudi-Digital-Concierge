# Structured knowledge base (SQLite)

The **exact-filter half** of the hybrid KB. Serves deterministic constraint queries for
the Planning/Verifier agents; semantic queries are served by the separate vector store,
joined on `canonical_id`.

```bash
python -m src.database.build_sqlite     # build data/final/knowledge_base.sqlite
python -m src.database.kb               # demo query
```

> The `.sqlite` file is a **regenerable build artifact** (git-ignored). Rebuild it any time
> from the processed + standardized CSVs with the command above.

## Contents

Loads the cleaned, standardized and entity-resolved tables as typed SQLite tables:

`places · hotels · entertainment · reviews · tourism_statistics · tourism_indicators ·
entities_core · canonical_entities · entity_crosswalk · candidate_links ·
review_place_links` (+ `events` if generated locally).

- **Indexes** on all filter/join keys (city, region, price_sar, guest_rating, star_rating,
  max_persons, dates, canonical_id, …).
- **Views** the agents use:
  - `v_hotels`, `v_places` — the entity table + its `canonical_id`.
  - `v_entity_canonical` — every source record joined to its canonical entity (join hub).
  - `v_reviews_resolved` — reviews with their resolved canonical place (nullable).

## Structured retrieval API (`src/database/kb.py`)

Parameterized, injection-safe helpers:

```python
from src.database.kb import find_hotels, find_places, find_events, reviews_for

find_hotels(city="Riyadh", max_price=500, min_guest_rating=8)   # thesis example
find_places(city="Riyadh", is_restaurant=True, min_rating=4.5)
find_events(city="Jeddah", active_only=True, family=True)        # needs events table
reviews_for("RYD_002531")                                        # evidence by canonical_id
```

## Verified example queries

| Query | Result |
| ----- | ------ |
| Hotels in Riyadh, `price_sar < 500`, `guest_rating >= 8` | 34 |
| Riyadh restaurants `average_rating >= 4.5` | 2,186 |
| Canonical entities with >1 member (deduped) | 225 |

## Role in the hybrid KB

```
structured filter (this DB)  ─┐
                              ├─►  hybrid retrieval  (join on canonical_id)
semantic rank (vector store) ─┘
```

- **This layer** answers "hotels in Riyadh under 500 SAR, rating ≥ 8" — exact predicates
  the Verifier can check deterministically (budget, capacity, dates, city).
- The **vector store** (next step) answers "suitable for a traditional-culture lover" over
  the `embed=True` documents; results resolve back here via `canonical_id`.
- `embed=False` statistics/indicators live **only** here (structured-only).
