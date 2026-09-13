"""Standardization — make the cleaned datasets compatible with each other.

Cleaning produced one tidy table per entity. Standardization unifies them so they can be
combined, compared and retrieved together:

  1. A shared **core schema** across the recommendable point-entities (places, hotels,
     events, entertainment): same column names, a comparable `rating_norm` (0-1), city/
     region as the join key, coordinates, price, and provenance.
     ->  data/processed/standardized/entities_core.csv

  2. A unified **knowledge-base documents** table across ALL entities (incl. reviews and
     statistics) following data_dictionary.md §12: one row per retrievable item with a
     natural-language `text`, `language`, metadata filters and provenance — ready to embed.
     ->  data/processed/standardized/kb_documents.csv

Run:
    python -m src.standardization.standardize
"""
from __future__ import annotations

import re

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from src.cleaning.common import PROCESSED

OUT = PROCESSED / "standardized"

# Shared core schema for point entities (things the concierge can recommend/place).
CORE_COLS = ["entity_id", "entity_type", "name", "category", "city", "region",
             "latitude", "longitude", "rating_norm", "price_sar",
             "source", "source_url", "data_period", "snapshot_date", "retrieved_at", "is_live"]

# KB document schema (data_dictionary.md §12).
DOC_COLS = ["document_id", "chunk_id", "entity_type", "entity_id", "text", "language",
            "city", "region", "category", "latitude", "longitude", "rating_norm", "price_sar",
            "source", "source_id", "source_url", "data_period", "snapshot_date",
            "retrieved_at", "is_live"]

PROV = ["source", "source_id", "source_url", "data_period", "snapshot_date",
        "retrieved_at", "is_live"]

_ARABIC = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[A-Za-z]")


def _read(entity, filename=None):
    path = PROCESSED / entity / (filename or f"{entity}_clean.csv")
    return pd.read_csv(path) if path.exists() else None


def detect_language(text) -> str:
    if not isinstance(text, str) or not text.strip():
        return "en"
    ar, la = bool(_ARABIC.search(text)), bool(_LATIN.search(text))
    return "mixed" if ar and la else ("ar" if ar else "en")


def _prov(df):
    return {c: df[c] if c in df.columns else None for c in PROV}


# ── Per-entity adapters to the core schema (+ a text renderer) ──────────────────
def _places(df):
    core = pd.DataFrame({
        "entity_id": df["place_id"], "entity_type": "place", "name": df["name"],
        "category": df["granular_category"], "city": df["city"], "region": df["region"],
        "latitude": df["latitude"], "longitude": df["longitude"],
        "rating_norm": pd.to_numeric(df["average_rating"], errors="coerce") / 5.0,
        "price_sar": np.nan, **_prov(df)})
    text = df.apply(lambda r: _join([
        r["name"],
        f"— {r['granular_category']}" if pd.notna(r.get("granular_category")) else "",
        f"in {r['city']}." if pd.notna(r.get("city")) else "",
        f"Rated {r['average_rating']}/5" if pd.notna(r.get("average_rating")) else "",
        f"({int(r['rate_count'])} reviews)." if pd.notna(r.get("rate_count")) else "",
    ]), axis=1)
    return core, text


def _hotels(df):
    core = pd.DataFrame({
        "entity_id": df["hotel_id"], "entity_type": "hotel", "name": df["name"],
        "category": "hotel", "city": df["city"], "region": df["region"],
        "latitude": df["latitude"], "longitude": df["longitude"],
        "rating_norm": pd.to_numeric(df["guest_rating"], errors="coerce") / 10.0,
        "price_sar": pd.to_numeric(df["price_sar"], errors="coerce"), **_prov(df)})
    text = df.apply(lambda r: _join([
        r["name"], "—",
        f"{int(r['star_rating'])}-star" if pd.notna(r.get("star_rating")) else "",
        f"hotel in {r['city']}, {r['region']}." if pd.notna(r.get("region")) else f"hotel in {r['city']}.",
        f"Guest rating {r['guest_rating']}/10." if pd.notna(r.get("guest_rating")) else "",
        f"From {int(r['price_sar'])} SAR/night (2020)." if pd.notna(r.get("price_sar")) else "",
    ]), axis=1)
    return core, text


def _events(df):
    core = pd.DataFrame({
        "entity_id": df["event_id"], "entity_type": "event", "name": df["name"],
        "category": "event", "city": df["city"], "region": df["region"],
        "latitude": np.nan, "longitude": np.nan, "rating_norm": np.nan,
        "price_sar": np.nan, **_prov(df)})

    def who(r):
        aud = []
        if r.get("is_family_allowed") is True or str(r.get("is_family_allowed")).lower() == "true":
            aud.append("families")
        if r.get("is_male_allowed") is True or str(r.get("is_male_allowed")).lower() == "true":
            aud.append("men")
        if r.get("is_female_allowed") is True or str(r.get("is_female_allowed")).lower() == "true":
            aud.append("women")
        return ", ".join(aud)
    text = df.apply(lambda r: _join([
        r["name"], f"— event in {r['city']}" if pd.notna(r.get("city")) else "— event",
        f"from {r['start_date']} to {r['end_date']}." if pd.notna(r.get("start_date")) else "",
        f"Open to: {who(r)}." if who(r) else "",
    ]), axis=1)
    return core, text


def _entertainment(df):
    core = pd.DataFrame({
        "entity_id": df["entertainment_id"], "entity_type": "entertainment", "name": df["name"],
        "category": df["genre"], "city": df["city"], "region": df["region"],
        "latitude": np.nan, "longitude": np.nan,
        "rating_norm": pd.to_numeric(df["rating"], errors="coerce") / 5.0,
        "price_sar": np.nan, **_prov(df)})
    text = df.apply(lambda r: _join([
        r["name"],
        f"— {r['genre']}" if pd.notna(r.get("genre")) else "— entertainment venue",
        f"in {r['city']}." if pd.notna(r.get("city")) else "",
        f"Rated {r['rating']}/5." if pd.notna(r.get("rating")) else "",
    ]), axis=1)
    return core, text


def _join(parts):
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def _to_docs(core, text):
    docs = core.reindex(columns=[c for c in DOC_COLS if c in core.columns]).copy()
    docs["document_id"] = core["entity_id"]
    docs["chunk_id"] = pd.NA
    docs["text"] = text.values
    docs["language"] = docs["text"].map(detect_language)
    return docs.reindex(columns=DOC_COLS)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    adapters = {"places": _places, "hotels": _hotels, "events": _events,
                "entertainment": _entertainment}

    core_frames, doc_frames = [], []
    for entity, fn in adapters.items():
        df = _read(entity)
        if df is None:
            print(f"  - {entity}: (no processed file, skipped)")
            continue
        core, text = fn(df)
        core_frames.append(core)
        doc_frames.append(_to_docs(core, text))
        print(f"  - {entity}: {len(core)} rows")

    core_all = pd.concat(core_frames, ignore_index=True).reindex(columns=CORE_COLS)
    core_all.to_csv(OUT / "entities_core.csv", index=False)

    # Non-point entities become KB documents too (text only, no geo/rating).
    rv = _read("reviews")
    if rv is not None:
        d = pd.DataFrame({
            "document_id": rv["review_id"], "chunk_id": pd.NA, "entity_type": "review",
            "entity_id": rv["review_id"],
            "text": rv.apply(lambda r: _join([
                f"Review of {r['place_name_raw']}" if pd.notna(r.get("place_name_raw")) else "Review",
                f"({r['city']}):" if pd.notna(r.get("city")) else ":",
                str(r["review_text"]) if pd.notna(r.get("review_text")) else ""]), axis=1),
            "city": rv.get("city"), "region": np.nan, "category": rv.get("category"),
            "latitude": np.nan, "longitude": np.nan, "rating_norm": np.nan, "price_sar": np.nan,
            **_prov(rv)})
        d["language"] = d["text"].map(detect_language)
        doc_frames.append(d.reindex(columns=DOC_COLS))
        print(f"  - reviews: {len(d)} rows")

    ts = _read("tourism_statistics")
    if ts is not None:
        d = pd.DataFrame({
            "document_id": [f"stats_{i:05d}" for i in range(len(ts))], "chunk_id": pd.NA,
            "entity_type": "tourism_statistics",
            "entity_id": [f"stats_{i:05d}" for i in range(len(ts))],
            "text": ts.apply(lambda r: _join([
                f"{r['region']} {int(r['year'])} {r['tourism_type']}:",
                f"{r['tourists_thousands']:.0f}k tourists," if pd.notna(r.get("tourists_thousands")) else "",
                f"{r['spending_million_sar']:.0f}M SAR spending," if pd.notna(r.get("spending_million_sar")) else "",
                f"avg stay {r['avg_stay_nights']:.1f} nights." if pd.notna(r.get("avg_stay_nights")) else "",
            ]), axis=1),
            "city": np.nan, "region": ts.get("region"), "category": "tourism_statistics",
            "latitude": np.nan, "longitude": np.nan, "rating_norm": np.nan, "price_sar": np.nan,
            **_prov(ts)})
        d["language"] = "en"
        doc_frames.append(d.reindex(columns=DOC_COLS))
        print(f"  - tourism_statistics: {len(d)} rows")

    ind = _read("tourism_indicators")
    if ind is not None:
        d = pd.DataFrame({
            "document_id": [f"ind_{i:05d}" for i in range(len(ind))], "chunk_id": pd.NA,
            "entity_type": "tourism_indicator",
            "entity_id": [f"ind_{i:05d}" for i in range(len(ind))],
            "text": ind.apply(lambda r: _join([
                f"{r['indicator']} ({r['period']}",
                f"| {r['dimension_value']}" if pd.notna(r.get("dimension_value")) else "",
                f"): {round(float(r['value']), 2)} {r['unit']}." if pd.notna(r.get("value")) else "):",
            ]), axis=1),
            "city": np.nan, "region": np.nan, "category": "tourism_indicator",
            "latitude": np.nan, "longitude": np.nan, "rating_norm": np.nan, "price_sar": np.nan,
            **_prov(ind)})
        d["language"] = "en"
        doc_frames.append(d.reindex(columns=DOC_COLS))
        print(f"  - tourism_indicators: {len(d)} rows")

    docs = pd.concat(doc_frames, ignore_index=True).reindex(columns=DOC_COLS)
    docs.to_csv(OUT / "kb_documents.csv", index=False)

    print(f"\nentities_core.csv : {len(core_all)} rows x {len(CORE_COLS)} cols")
    print(f"kb_documents.csv  : {len(docs)} rows x {len(DOC_COLS)} cols")
    print("by entity_type:")
    print(docs["entity_type"].value_counts().to_string())
    print("by language:")
    print(docs["language"].value_counts().to_string())
    return core_all, docs


if __name__ == "__main__":
    build()
    print("\nsaved -> data/processed/standardized/{entities_core.csv, kb_documents.csv}")
