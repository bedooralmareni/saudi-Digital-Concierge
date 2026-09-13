# Entity resolution

Links the same real-world place across datasets and assigns a **canonical id**
(region-prefixed, e.g. `RYD_000123`) so reviews, coordinates and ratings can all refer to
the same entity — while **retaining every source-specific identifier**.

```bash
python -m src.entity_resolution.resolve
```

Inputs: the cleaned point entities — `places`, `entertainment`, `hotels`
(10,382 records). Reviews are linked separately (best-effort).

## Matching method — never name alone

A pair is considered only when it is in the **same city** and of a **compatible type**:

- `place ↔ place / entertainment` (POIs & attractions can be the same venue)
- `entertainment ↔ entertainment`
- `hotel ↔ hotel` only (accommodation is a separate domain)

**Hard merges require coordinate corroboration** (combines name similarity + coordinates
+ city + type):

| Rule (same city, compatible type) | Merge? |
| --------------------------------- | ------ |
| both have coords, distance ≤ 20 m and name_sim ≥ 0.60 | ✅ |
| both have coords, distance ≤ 50 m and name_sim ≥ 0.85 | ✅ |
| no coordinates on either side | ❌ never hard-merge |
| same name, far apart | ❌ (different branch of a chain) |

- **Name similarity is bilingual**: names are split into English and Arabic parts
  (entertainment stores `"عربي | English"`), each scored, and the max taken.
- **Same-name chain branches are NOT merged.** Two "Starbucks" 5 km apart, or several
  same-named entertainment records with no coordinates, are kept distinct — a strong
  cross-source name match is instead written to `candidate_links.csv` for review, not
  merged automatically.
- Blocking (city + name-prefix + coordinate cell) keeps it fast; union-find forms clusters.

## Outputs (`data/processed/standardized/`)

| File | Rows | What it is |
| ---- | ---- | ---------- |
| `entity_crosswalk.csv` | 10,382 | one row per **source** record: `canonical_id` ↔ its `source` + `source_entity_id` (retains all source ids) |
| `canonical_entities.csv` | 10,027 | one row per canonical entity: primary name, types, city, region, best lat/lon, `n_members`, `sources`, `member_ids` |
| `candidate_links.csv` | 75 | strong cross-source name matches **not** merged (need coordinate/manual confirmation) |
| `review_place_links.csv` | 3,538 | reviews → canonical place by name+city (nullable `canonical_id`; 120 linked) |

## Result summary (current run)

- **457** coordinate-corroborated hard merges.
- **10,027** canonical entities (225 multi-record clusters; max size 13 — same-name
  records within 50 m, i.e. genuine scrape duplicates; 9,802 singletons).
- **75** candidate cross-source links held for review.
- **120 / 3,538** reviews linked to a canonical place (most reviews are Arabic names for
  non-Riyadh places with no English/coordinate counterpart, so remain unlinked — expected).

## Design notes

- Every source record keeps its own id in the crosswalk; canonical ids are **additive**,
  never destructive.
- Conservative by design: we prefer to leave two records separate (a candidate link) over
  wrongly merging distinct places — matching the "don't merge on name alone" requirement.
- Reviews and entertainment lack coordinates, which limits automatic cross-source merging;
  coordinate-bearing sources (places, hotels) resolve most reliably. Adding coordinates to
  events/entertainment later would convert many `candidate_links` into confirmed merges.
