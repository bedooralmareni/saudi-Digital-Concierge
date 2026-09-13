"""Clean Source 7 — Entertainment -> data/processed/entertainment/entertainment_clean.csv

Decisions (see data_dictionary.md §7):
  - ~24 column-misaligned rows (rating holds text like 'No reviews · …' / 'Saudi Arabia')
    are DROPPED as unrecoverable (rating not numeric). Logged, not silently kept.
  - ~14 non-Saudi venues (Bahrain/Kuwait) are DROPPED (country confirms membership; the
    bbox is not used as proof of Saudi).
  - review_count '(1.1T)' -> 1100 (T/K = thousand, M = million); rating -> float 0-5.
  - genre trimmed; contaminated genres (price symbols ₹, 'In <place>' leaks) -> null.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.cleaning.common import make_id, norm_text, RAW, report, save_processed, validate
from src.cleaning.geo import map_city

ENTITY = "entertainment"


def _parse_reviews(x):
    if pd.isna(x):
        return np.nan
    m = re.match(r"([\d.]+)\s*([KkMmTt]?)", str(x).strip().strip("()").strip())
    if not m:
        return np.nan
    return float(m.group(1)) * {"": 1, "K": 1e3, "T": 1e3, "M": 1e6}[m.group(2).upper()]


def _country(loc: str) -> str:
    s = str(loc) if loc is not None else ""
    if "Saudi Arabia" in s:
        return "Saudi Arabia"
    if "Bahrain" in s:
        return "Bahrain"
    if "Kuwait" in s:
        return "Kuwait"
    return "Unknown"


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "entertainment" / "Entertainment_KSA.csv").rename(columns={"Unnamed: 0": "idx"})
    n = len(raw)

    rating = pd.to_numeric(raw["rating"], errors="coerce")
    misaligned = rating.isna()          # DECISION: drop column-misaligned rows
    country = raw["location"].map(_country)
    non_saudi = country != "Saudi Arabia"  # DECISION: keep only confirmed-Saudi rows

    nameless = raw["name"].isna()  # DECISION: a venue with no name is unusable -> drop
    keep = ~misaligned & ~non_saudi & ~nameless
    kept = raw[keep].reset_index(drop=True)

    df = pd.DataFrame()
    df["entertainment_id"] = [make_id("entertainment", i) for i in range(len(kept))]
    df["name"] = kept["name"].map(norm_text)

    genre = kept["genre"].fillna("").str.strip()
    contam = genre.str.match(r"^[₹$]+$") | genre.str.startswith("In ")
    df["genre"] = genre.where(~contam & (genre != ""), other=None)

    r = pd.to_numeric(kept["rating"], errors="coerce")
    df["rating"] = r.where(r.between(0, 5))
    df["review_count"] = kept["review_count"].map(_parse_reviews).astype("Int64")

    city_region = kept["location"].map(map_city)
    df["city"] = [c for c, _ in city_region]
    df["region"] = [rg for _, rg in city_region]
    df["country"] = "Saudi Arabia"
    df["best_comment"] = kept["best_comment"].map(norm_text)

    df["source"] = "entertainment_kaggle"
    df["source_id"] = ""
    df["source_url"] = ""  # Kaggle dataset URL: TBD
    df["data_period"] = "static"
    df["snapshot_date"] = pd.NaT
    df["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    df["is_live"] = False

    issues = validate(df, entity=ENTITY, pk="entertainment_id",
                      required=["entertainment_id", "name", "city", "country"])
    report(ENTITY, n, df, issues)
    print(f"  dropped misaligned rows : {int(misaligned.sum())}")
    print(f"  dropped non-Saudi rows  : {int((non_saudi & ~misaligned).sum())}")
    print(f"  dropped nameless rows   : {int((nameless & ~misaligned & ~non_saudi).sum())}")
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
