"""Semantic + hybrid search over the vector index.

    from src.vector_store.search import semantic_search, hybrid_search
    semantic_search("مكان مناسب لعشاق الثقافة السعودية", top_k=5)
    hybrid_search("family-friendly cafe", city="Riyadh", entity_type="place", min_rating=0.8)

`hybrid_search` applies exact metadata filters (the structured half) BEFORE semantic
ranking, so "cafes in Riyadh suitable for families" respects city/type/price/rating and
still ranks by meaning. Results carry canonical_id + source_url for evidence grounding.
"""
from __future__ import annotations

import functools
import json

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from src.cleaning.common import ROOT
from src.vector_store.embedder import get_embedder

STORE = ROOT / "data" / "final" / "vector_store"


@functools.lru_cache(maxsize=1)
def _load():
    info = json.loads((STORE / "index_info.json").read_text())
    vectors = np.load(STORE / "vectors.npy")
    meta = pd.read_csv(STORE / "vector_meta.csv")
    embedder = get_embedder(info["model"])
    return info, vectors, meta, embedder


def _mask(meta, *, entity_type=None, city=None, region=None,
          max_price=None, min_rating=None):
    m = np.ones(len(meta), dtype=bool)
    if entity_type is not None:
        types = {entity_type} if isinstance(entity_type, str) else set(entity_type)
        m &= meta["entity_type"].isin(types).to_numpy()
    if city is not None:
        m &= (meta["city"] == city).to_numpy()
    if region is not None:
        m &= (meta["region"] == region).to_numpy()
    if max_price is not None:
        m &= (meta["price_sar"].fillna(np.inf) <= max_price).to_numpy()
    if min_rating is not None:
        m &= (meta["rating_norm"].fillna(-1) >= min_rating).to_numpy()
    return m


def _rank(query, mask, top_k):
    info, vectors, meta, embedder = _load()
    qv = embedder.encode([query], kind="query")[0]
    scores = vectors @ qv                      # cosine (all normalized)
    scores = np.where(mask, scores, -np.inf)
    k = min(top_k, int(mask.sum()))
    if k <= 0:
        return meta.head(0).assign(score=[])
    idx = np.argpartition(-scores, k - 1)[:k]
    idx = idx[np.argsort(-scores[idx])]
    out = meta.iloc[idx].copy()
    out.insert(0, "score", scores[idx].round(4))
    return out


COLS = ["score", "entity_type", "entity_id", "city", "region", "category",
        "rating_norm", "price_sar", "source_url", "text"]


def semantic_search(query, top_k=10):
    """Pure semantic search across all embedded documents."""
    _, _, meta, _ = _load()
    return _rank(query, np.ones(len(meta), dtype=bool), top_k)[COLS]


def hybrid_search(query, *, entity_type=None, city=None, region=None,
                  max_price=None, min_rating=None, top_k=10):
    """Metadata pre-filter (structured) + semantic ranking."""
    _, _, meta, _ = _load()
    mask = _mask(meta, entity_type=entity_type, city=city, region=region,
                 max_price=max_price, min_rating=min_rating)
    return _rank(query, mask, top_k)[COLS]


if __name__ == "__main__":
    info = _load()[0]
    print("index:", info)
    print("\n[semantic] 'traditional Saudi culture and heritage':")
    print(semantic_search("traditional Saudi culture and heritage", top_k=5).to_string(index=False))
    print("\n[hybrid] places in Riyadh, semantic 'family friendly outing':")
    print(hybrid_search("family friendly outing", entity_type="place", city="Riyadh",
                        top_k=5).to_string(index=False))
