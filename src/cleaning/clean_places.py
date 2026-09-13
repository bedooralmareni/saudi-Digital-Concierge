"""Clean Source 2 — Riyadh Places  ->  data/processed/places/places_clean.csv

Decisions (see data_dictionary.md §2):
  - average_rating == 0 is treated as UNRATED (null), NOT a genuine 0/5 rating.
    Google-style exports use 0 when there are no ratings; keeping it as 0 would wrongly
    drag down "best rated" queries. rate_count == 0 corroborates this.
  - categories is pipe-delimited multi-value -> kept as a '|'-joined string in the CSV.
  - Coordinates validated against the Saudi bbox; all rows are Riyadh (city/region fixed).
"""
from __future__ import annotations

import pandas as pd

# Allow running this file directly (IDE 'Run') as well as `python -m src.cleaning.<x>`.
import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

from src.cleaning.common import (RAW, make_id, norm_text, report, save_processed,
                                 valid_coord, validate)

ENTITY = "places"


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "riyadh_places" / "riyadh_places_8836x9.csv")
    n = len(raw)
    df = pd.DataFrame()

    df["place_id"] = [make_id("places", i) for i in range(n)]
    df["source_id"] = raw["id"].astype(str)
    df["name"] = raw["place_name"].map(norm_text)
    df["is_restaurant"] = raw["is_restaurant"].astype(str).str.upper().eq("RESTAURANT")

    df["categories"] = (raw["categories"].fillna("")
                        .str.split("|").map(lambda xs: "|".join(x.strip() for x in xs if x.strip()) or None))
    df["granular_category"] = raw["granular_category"].map(norm_text)

    rating = pd.to_numeric(raw["average_rating"], errors="coerce")
    rc = pd.to_numeric(raw["rate_count"], errors="coerce")
    # DECISION: rating 0 (and/or 0 ratings) -> unrated (null), not a real 0/5.
    df["average_rating"] = rating.where((rating > 0) & (rc.fillna(0) > 0))
    df["rate_count"] = rc.clip(lower=0)

    df["city"] = "Riyadh"
    df["region"] = "Riyadh"

    coords = [valid_coord(la, lo) for la, lo in zip(raw["latitude"], raw["longitude"])]
    df["latitude"] = [c[0] for c in coords]
    df["longitude"] = [c[1] for c in coords]

    df["source"] = "riyadh_places_kaggle"
    df["source_url"] = ""  # Kaggle dataset URL: TBD
    df["data_period"] = "static"
    df["snapshot_date"] = pd.NaT
    df["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    df["is_live"] = False

    issues = validate(df, entity=ENTITY, pk="place_id",
                      required=["place_id", "name", "is_restaurant", "city", "region",
                                "latitude", "longitude"])
    report(ENTITY, n, df, issues)
    print(f"  unrated (rating->null): {int(df['average_rating'].isna().sum())}")
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
