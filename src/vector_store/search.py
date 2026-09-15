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
        "rating_norm", "price_sar", "source", "source_url", "text"]

# machine source id -> human-readable name (for display)
SOURCE_NAMES = {
    "reviews_zenodo": "Tourism Reviews",
    "riyadh_places_kaggle": "Riyadh Places",
    "booking_kaggle": "Booking.com Hotels",
    "entertainment_kaggle": "Entertainment KSA",
    "enjoy_sa": "Enjoy.sa Events",
}


def format_results(query, df, text_chars=90):
    """Render a results DataFrame in the RETRIEVED DOCUMENTS format.

    Distance = 1 - cosine similarity (vectors are L2-normalized, so smaller = closer).
    """
    lines = [f"QUERY:\n{query}\n", "RETRIEVED DOCUMENTS:\n"]
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows(), 1):
        dist = 1.0 - float(r["score"])
        text = " ".join(str(r["text"]).split())
        if len(text) > text_chars:
            text = text[:text_chars].rstrip() + "..."
        lines += [
            f"--- Result {i} ---",
            f"Distance: {dist:.4f}",
            f"Type: {r['entity_type']}",
            f"City: {r['city'] if pd.notna(r['city']) else 'N/A'}",
            f"Source: {SOURCE_NAMES.get(r['source'], r['source'])}",
            f"Text: {text}",
            "",
        ]
    return "\n".join(lines)


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
    import argparse

    ap = argparse.ArgumentParser(description="Semantic / hybrid search over the vector index.")
    ap.add_argument("query", nargs="*", help="free-text query (Arabic or English)")
    ap.add_argument("-k", "--top-k", type=int, default=3)
    ap.add_argument("--city", default=None)
    ap.add_argument("--type", dest="entity_type", default=None,
                    help="place | review | hotel | entertainment")
    args = ap.parse_args()

    info = _load()[0]
    if info["model"] == "stub":
        print("WARNING: index built with the STUB embedder (token-hash, not semantic).")
        print("         Rebuild with a real model for cross-lingual results:")
        print("         python -m src.vector_store.build_index\n")

    if args.query:
        q = " ".join(args.query)
        df = (hybrid_search(q, city=args.city, entity_type=args.entity_type, top_k=args.top_k)
              if (args.city or args.entity_type)
              else semantic_search(q, top_k=args.top_k))
        print(format_results(q, df))
    else:
        for q in ["family-friendly activities in Riyadh",
                  "traditional Saudi culture and heritage"]:
            print(format_results(q, semantic_search(q, top_k=3)))
            print("=" * 60)
