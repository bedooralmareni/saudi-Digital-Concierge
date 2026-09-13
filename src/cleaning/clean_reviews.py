"""Clean Source 1 — Tourism Reviews -> data/processed/reviews/reviews_clean.csv

Decisions (see data_dictionary.md §3):
  - Six aspect columns are sentiment in {-1, 0, 1}. Missing = aspect NOT mentioned ->
    kept as null (NOT 0). One value in البيئة_golden is non-numeric -> coerced to null.
  - Arabic text is NFKC-normalized (diacritics/tatweel removed).
  - place_id (link to places) is NOT set here — it is a nullable FK resolved later by
    entity matching (Phase 6). We keep place_name_raw for that step.
  - 5 exact duplicate rows are dropped.
"""
from __future__ import annotations

import pandas as pd

# Allow running this file directly (IDE 'Run') as well as `python -m src.cleaning.<x>`.
import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

from src.cleaning.common import make_id, norm_text, RAW, report, save_processed, validate
from src.cleaning.geo import map_city

ENTITY = "reviews"

ASPECTS = {
    "السعر_golden": "sent_price",
    "النظافة_golden": "sent_cleanliness",
    "المرافق_golden": "sent_facilities",
    "الخدمة و الموظفين_golden": "sent_service",
    "البيئة_golden": "sent_environment",
    "التجربة بشكل عام_golden": "sent_overall",
}


def _sentiment(series):
    s = pd.to_numeric(series, errors="coerce")   # non-numeric -> NaN
    return s.where(s.isin([-1, 0, 1]))            # anything else -> null


def clean() -> pd.DataFrame:
    raw = pd.read_excel(RAW / "tourism_reviews" / "golden_data_set_processed_google_reviews.xlsx")
    n = len(raw)
    raw = raw.drop_duplicates().reset_index(drop=True)  # DECISION: drop 5 exact dups

    df = pd.DataFrame()
    df["review_id"] = [make_id("reviews", i) for i in range(len(raw))]
    df["place_name_raw"] = raw["اسم المكان"].map(norm_text)
    df["place_id"] = None  # resolved by entity matching later (nullable FK)
    df["review_text"] = raw["processed_reviews"].map(norm_text)

    city_region = raw["المدينة"].map(map_city)
    df["city"] = [c for c, _ in city_region]
    df["category"] = raw["الفئة"].map(norm_text)

    for ar_col, out_col in ASPECTS.items():
        df[out_col] = _sentiment(raw[ar_col]).astype("Int64")

    df["source"] = "reviews_zenodo"
    df["source_id"] = ""
    df["source_url"] = "https://zenodo.org/records/16924532"
    df["data_period"] = "static"
    df["snapshot_date"] = pd.NaT
    df["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    df["is_live"] = False

    issues = validate(df, entity=ENTITY, pk="review_id",
                      required=["review_id", "place_name_raw", "review_text"],
                      region_col=None)
    report(ENTITY, n, df, issues)
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
