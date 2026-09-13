"""Embedding models for the vector store.

Bilingual corpus (Arabic + English) -> a MULTILINGUAL embedder is required.

Backends (choose via the EMBED_MODEL env var or `get_embedder(name)`):
  - "intfloat/multilingual-e5-base"  (default; local, open, strong multilingual, needs
    the "query:"/"passage:" prefixes — handled here). Requires `sentence-transformers`.
  - any other sentence-transformers multilingual model id (e.g. "BAAI/bge-m3").
  - "stub"  -> a deterministic hashing embedder with NO dependencies or downloads. Not
    semantic; only for wiring/tests and offline smoke checks.

All embedders return L2-normalized float32 vectors, so cosine similarity == dot product.
"""
from __future__ import annotations

import hashlib
import os
import re

import numpy as np

DEFAULT_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-base")
STUB_DIM = 256


class StubEmbedder:
    """Dependency-free hashing embedder (bag-of-words hashed into STUB_DIM).

    Deterministic and offline — used to validate the build/search pipeline without
    downloading a model. Do NOT use for real semantic quality.
    """

    name = "stub"
    dim = STUB_DIM

    def encode(self, texts, kind="passage", batch_size=256):
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", str(t).lower()):
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                vecs[i, h % self.dim] += 1.0
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


class SentenceTransformerEmbedder:
    """Wraps a sentence-transformers multilingual model."""

    def __init__(self, model_name=DEFAULT_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "sentence-transformers is required for real embeddings.\n"
                "  pip install sentence-transformers\n"
                "Or use the offline stub: EMBED_MODEL=stub") from e
        self.name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()
        self._e5 = "e5" in model_name.lower()   # e5 needs query:/passage: prefixes

    def encode(self, texts, kind="passage", batch_size=64):
        texts = [str(t) for t in texts]
        if self._e5:
            prefix = "query: " if kind == "query" else "passage: "
            texts = [prefix + t for t in texts]
        return self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True,
                                 normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


def get_embedder(model_name=None):
    name = model_name or DEFAULT_MODEL
    if name == "stub":
        return StubEmbedder()
    return SentenceTransformerEmbedder(name)
