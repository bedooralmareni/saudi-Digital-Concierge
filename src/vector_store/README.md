# Vector store (semantic half of the hybrid KB)

Embeds the `embed=True` KB documents and serves semantic + hybrid retrieval. Joins the
structured SQLite layer on `canonical_id` / `entity_id`.

```bash
pip install sentence-transformers            # for the real multilingual model
python -m src.vector_store.build_index       # build data/final/vector_store/
python -m src.vector_store.search            # demo queries

# offline wiring test (no download, not semantic):
EMBED_MODEL=stub python -m src.vector_store.build_index
EMBED_MODEL=stub python -m src.vector_store.search
```

> The index (`vectors.npy`, `vector_meta.csv`) is a **regenerable build artifact**
> (git-ignored). Rebuild any time from `kb_documents.csv`.

## Embedding model — must be multilingual (Arabic + English)

Set with the `EMBED_MODEL` env var (default `intfloat/multilingual-e5-base`):

| Value | Notes |
| ----- | ----- |
| `intfloat/multilingual-e5-base` | default; local/open, strong multilingual, 768-dim (e5 query/passage prefixes handled automatically) |
| `BAAI/bge-m3` | heavier, excellent multilingual, 1024-dim |
| any sentence-transformers multilingual id | pluggable |
| `stub` | dependency-free hashing embedder for offline wiring tests only (not semantic) |

> An English-only embedder must **not** be used — half the corpus (reviews, many names)
> is Arabic. If you prefer an API model (e.g. a hosted multilingual embeddings endpoint),
> add a backend in `embedder.py`; the rest of the pipeline is unchanged.

## What gets embedded

The `embed=True` rows of `kb_documents.csv` (13,920): places, reviews, hotels,
entertainment. `embed=False` statistics/indicators are **not** embedded — they live in the
structured layer only.

`data/final/vector_store/`:
- `vectors.npy` — float32 `[N x dim]`, L2-normalized (cosine == dot product)
- `vector_meta.csv` — aligned metadata: filter columns (`city`, `region`, `entity_type`,
  `price_sar`, `rating_norm`) + provenance (`source_url`, …) + `text`
- `index_info.json` — model, dim, count

## Retrieval API (`src/vector_store/search.py`)

```python
from src.vector_store.search import semantic_search, hybrid_search

# pure semantic (the "suitable for a traditional-culture lover" case)
semantic_search("مكان مناسب لعشاق الثقافة السعودية", top_k=5)

# hybrid: exact metadata pre-filter THEN semantic ranking
hybrid_search("family-friendly outing", entity_type="place", city="Riyadh",
              max_price=None, min_rating=0.8, top_k=10)
```

Every result carries `entity_id`, `source_url`, and the metadata needed to resolve back to
the structured record (`canonical_id` via `entity_crosswalk`) — the evidence trace.

## Role in the hybrid KB

```
structured filter (SQLite)  ─┐
                             ├─►  hybrid retrieval  (pre-filter → semantic rank; join on canonical_id/entity_id)
semantic rank (this store)  ─┘
```

- **This store** answers meaning-based queries ("good for a culture lover").
- The **SQLite layer** answers exact constraints ("under 500 SAR, rating ≥ 8").
- `hybrid_search` combines them: structured filter first, semantic ranking second.
