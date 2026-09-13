"""Build the vector index — embed the embed=True KB documents.

Reads data/processed/standardized/kb_documents.csv, keeps rows with embed=True, embeds
their `text` with a multilingual model, and writes to data/final/vector_store/:
  - vectors.npy         float32 [N x dim], L2-normalized
  - vector_meta.csv     aligned metadata (filters + provenance + text)
  - index_info.json     model name, dim, count

Metadata mirrors the SQL filter columns (city, region, entity_type, price_sar,
rating_norm, canonical_id) so hybrid pre-filtering works, and carries provenance
(source_url) for evidence grounding.

Run:
    python -m src.vector_store.build_index                 # default multilingual model
    EMBED_MODEL=stub python -m src.vector_store.build_index   # offline wiring test
"""
from __future__ import annotations

import json

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from src.cleaning.common import PROCESSED, ROOT
from src.vector_store.embedder import get_embedder

DOCS = PROCESSED / "standardized" / "kb_documents.csv"
OUT = ROOT / "data" / "final" / "vector_store"

META_COLS = ["document_id", "chunk_id", "entity_type", "entity_id", "language",
             "city", "region", "category", "latitude", "longitude",
             "rating_norm", "price_sar", "source", "source_id", "source_url",
             "snapshot_date", "is_live", "text"]


def build(model_name=None):
    OUT.mkdir(parents=True, exist_ok=True)
    docs = pd.read_csv(DOCS)
    docs = docs[docs["embed"] == True].reset_index(drop=True)  # noqa: E712
    print(f"documents to embed (embed=True): {len(docs)}")

    embedder = get_embedder(model_name)
    print(f"embedding model: {embedder.name} (dim={embedder.dim})")

    vectors = embedder.encode(docs["text"].tolist(), kind="passage")
    assert vectors.shape == (len(docs), embedder.dim)

    np.save(OUT / "vectors.npy", vectors)
    docs.reindex(columns=META_COLS).to_csv(OUT / "vector_meta.csv", index=False)
    (OUT / "index_info.json").write_text(json.dumps({
        "model": embedder.name, "dim": int(embedder.dim), "count": int(len(docs)),
        "normalized": True, "metric": "cosine",
    }, indent=2))

    print(f"saved -> {OUT}/ (vectors.npy [{vectors.shape}], vector_meta.csv, index_info.json)")
    print("by entity_type:")
    print(docs["entity_type"].value_counts().to_string())


if __name__ == "__main__":
    build()
