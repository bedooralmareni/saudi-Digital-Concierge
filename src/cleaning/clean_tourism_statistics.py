"""Clean Source 3 — Saudi Tourism 2015-2024
    -> data/processed/tourism_statistics/tourism_statistics_clean.csv

Decisions (see data_dictionary.md §8):
  - Resolve the non-unique granularity: exact duplicates dropped, then aggregate to ONE
    row per (year, region, tourism_type). Volume columns are SUMMED; the Avg_* columns are
    RECOMPUTED from the summed totals (never averaging pre-computed averages).
  - Zeros are RETAINED as valid values (not forced to null). Where a group's total is 0,
    the derived averages are null (division by zero), which correctly encodes "no basis".
  - Province -> canonical region.
Units (per source): tourists & overnight stays in THOUSANDS; spending in MILLION SAR.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.cleaning.common import RAW, report, save_processed, validate
from src.cleaning.geo import map_region

ENTITY = "tourism_statistics"


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "tourism_statistics" / "tourism_data.csv")
    n = len(raw)
    raw = raw.drop_duplicates()  # DECISION: drop ~28 exact duplicate rows

    raw = raw.assign(region=raw["Province"].map(map_region),
                     tourism_type=raw["Tourism_Type"].str.strip())

    g = (raw.groupby(["YEARS", "region", "tourism_type"], as_index=False)
             .agg(tourists_thousands=("Tourists_Number", "sum"),
                  overnight_stays_thousands=("Overnight_Stay", "sum"),
                  spending_million_sar=("Tourists_Spending", "sum")))
    g = g.rename(columns={"YEARS": "year"})

    # Recompute averages from summed totals (guard divide-by-zero -> null).
    with np.errstate(divide="ignore", invalid="ignore"):
        g["avg_stay_nights"] = (g["overnight_stays_thousands"] / g["tourists_thousands"]).replace([np.inf, -np.inf], np.nan)
        # spending is million SAR, volumes are thousands -> *1000 to get SAR per unit.
        g["avg_spend_per_trip_sar"] = (g["spending_million_sar"] / g["tourists_thousands"] * 1000).replace([np.inf, -np.inf], np.nan)
        g["avg_spend_per_night_sar"] = (g["spending_million_sar"] / g["overnight_stays_thousands"] * 1000).replace([np.inf, -np.inf], np.nan)

    g = g.round({"avg_stay_nights": 2, "avg_spend_per_trip_sar": 1, "avg_spend_per_night_sar": 1})

    g["source"] = "tourism_kaggle"
    g["source_id"] = ""
    g["source_url"] = ""  # Kaggle dataset URL: TBD
    g["data_period"] = "2015-2024"
    g["snapshot_date"] = pd.NaT
    g["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    g["is_live"] = False

    issues = validate_pk(g)
    report(ENTITY, n, g, issues)
    print(f"  rows collapsed from {len(raw)} sub-rows to {len(g)} (year x region x type)")
    return g


def validate_pk(g):
    """Composite-key validation for tourism_statistics."""
    from src.cleaning.geo import REGIONS
    issues = []
    for col in ["year", "region", "tourism_type"]:
        if g[col].isna().any():
            issues.append(f"{col}: nulls in required column")
    if g.duplicated(subset=["year", "region", "tourism_type"]).any():
        issues.append("(year, region, tourism_type): duplicate key")
    if not g["year"].between(2015, 2024).all():
        issues.append("year: out of 2015-2024")
    bad = set(g["region"].dropna().unique()) - REGIONS
    if bad:
        issues.append(f"region: unmapped {sorted(bad)}")
    return issues


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
