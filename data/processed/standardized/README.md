# Standardized layer

Where the cleaned datasets become **compatible with each other**. Built by
`src/standardization/standardize.py` from the per-entity `data/processed/*_clean.csv`
tables.

```bash
python -m src.standardization.standardize
```

## Outputs

### `entities_core.csv` — shared core schema (point entities)
One row per recommendable entity (places, hotels, events, entertainment) sharing **common
core fields where applicable** (not identical schemas — each entity keeps its own detail
in its processed table), so they can be compared and combined directly:

`entity_id · entity_type · name · category · city · region · latitude · longitude ·
rating · rating_scale · rating_norm · price_sar · <provenance>`

- **Ratings are kept in three forms** — the native **`rating`** (as reported), its
  **`rating_scale`** (5 for places/entertainment, 10 for hotels' guest score), AND a
  cross-source comparable **`rating_norm`** (0–1). The normalized value never replaces the
  original. Null stays null (unrated).
- **`city` / `region`** are the canonical join key (from `src/cleaning/geo.py`).

### `kb_documents.csv` — unified retrieval documents (all entities)
One row per item across **every** entity (adds reviews, tourism statistics and indicators),
following `docs/data_dictionary.md` §12:

`document_id · chunk_id · entity_type · entity_id · text · language · embed · city · region ·
category · latitude · longitude · rating · rating_scale · rating_norm · price_sar ·
<provenance>`

- **`text`** is a natural-language rendering per entity, ready to embed.
- **`language`** uses a **controlled vocabulary: `ar` / `en` / `mixed`** (detected per doc;
  validated on build). Current: en 10,681 · mixed 3,901.
- **`embed`** marks whether a document belongs in the **vector store** (`True`) or should
  **stay structured-only** (`False`). Not every document must be embedded — tourism
  statistics and indicators are numeric and are better served from the structured layer,
  so they carry `embed=False` (662 rows). Everything narrative (places, reviews, hotels,
  events, entertainment) is `embed=True` (13,920 rows).
- **Linkage & provenance** (validated on build): every document has a non-null
  `document_id` (unique) and `entity_id` that resolves back to its processed record, plus
  `source` / `source_url` / `snapshot_date` / `is_live` — the trace that powers
  evidence-grounded generation.

## Row counts (current run)

| entity_type | rows | embed |
| ----------- | ---: | :---: |
| place | 8,836 | ✅ |
| review | 3,538 | ✅ |
| hotel | 1,025 | ✅ |
| entertainment | 521 | ✅ |
| tourism_indicator | 403 | ❌ structured-only |
| tourism_statistics | 259 | ❌ structured-only |
| **kb_documents total** | **14,582** | 13,920 embed / 662 structured |
| entities_core total | 10,382 | — |

## Raw → standardized row-count reconciliation

Standardization does not change counts by itself; the differences come from the **cleaning**
stage (documented in `data/processed/README.md` and each `src/cleaning/clean_*.py`):

| Entity | Raw | Clean | Why the change |
| ------ | --: | ----: | -------------- |
| places | 8,836 | 8,836 | no rows dropped |
| hotels | 1,025 | 1,025 | no rows dropped |
| reviews | 3,543 | 3,538 | −5 exact duplicate rows |
| entertainment | 564 | 521 | −24 column-misaligned, −15 non-Saudi, −4 nameless |
| tourism_statistics | 1,058 | 259 | −28 exact dups, then **aggregated** to one row per (year, region, tourism_type): 1,030 sub-rows → 259 groups |
| tourism_indicators | 11 files | 403 | curated to 5 files, **reshaped** wide→long (one row per indicator × period × dimension) |

- **entities_core (10,382)** = places 8,836 + hotels 1,025 + entertainment 521 (+ events when present).
- **kb_documents (14,582)** = entities_core point entities + reviews 3,538 + statistics 259 + indicators 403.

> `events` is included automatically once `data/processed/events/events_clean.csv` exists
> (run `python -m src.cleaning.clean_events` where enjoy.sa is reachable, then re-run
> standardization).

**Next:** the KB-construction step embeds only the `embed=True` documents into the vector
store (`data/final/`) using a multilingual embedding model; the structured layer
(DuckDB/SQLite over the processed tables + `entities_core.csv`, incl. the `embed=False`
statistics/indicators) serves exact constraint checks.
