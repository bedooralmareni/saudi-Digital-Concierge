# Standardized layer

Where the cleaned datasets become **compatible with each other**. Built by
`src/standardization/standardize.py` from the per-entity `data/processed/*_clean.csv`
tables.

```bash
python -m src.standardization.standardize
```

## Outputs

### `entities_core.csv` — unified core schema (point entities)
One row per recommendable entity (places, hotels, events, entertainment) in a **shared
schema**, so they can be compared and combined directly:

`entity_id · entity_type · name · category · city · region · latitude · longitude ·
rating_norm · price_sar · <provenance>`

- **`rating_norm`** puts every source on the same **0–1 scale** (places `rating/5`,
  hotels `guest_rating/10`, entertainment `rating/5`) so ratings are comparable across
  datasets. Null stays null (unrated).
- **`city` / `region`** are the canonical join key (from `src/cleaning/geo.py`).

### `kb_documents.csv` — unified retrieval documents (all entities)
One row per retrievable item across **every** entity (adds reviews, tourism statistics and
indicators), following `docs/data_dictionary.md` §12:

`document_id · chunk_id · entity_type · entity_id · text · language · city · region ·
category · latitude · longitude · rating_norm · price_sar · <provenance>`

- **`text`** is a natural-language rendering per entity, ready to embed.
- **`language`** is detected per document (`ar` / `en` / `mixed`) — the corpus is bilingual.
- Metadata columns (`city`, `region`, `category`, `price_sar`, `rating_norm`, coords) are
  retrieval filters; provenance (`source`, `source_url`, `snapshot_date`, `is_live`, …)
  carries the evidence trace back to each source.

## Row counts (current run)

| entity_type | rows |
| ----------- | ---: |
| place | 8,836 |
| review | 3,538 |
| hotel | 1,025 |
| entertainment | 521 |
| tourism_indicator | 403 |
| tourism_statistics | 259 |
| **kb_documents total** | **14,582** |
| entities_core total | 10,382 |

> `events` is included automatically once `data/processed/events/events_clean.csv` exists
> (run `python -m src.cleaning.clean_events` where enjoy.sa is reachable, then re-run
> standardization).

**Next:** the KB-construction step embeds `kb_documents.csv` into the vector store
(`data/final/`) using a multilingual embedding model; the structured layer (DuckDB/SQLite
over the processed tables + `entities_core.csv`) serves exact constraint checks.
