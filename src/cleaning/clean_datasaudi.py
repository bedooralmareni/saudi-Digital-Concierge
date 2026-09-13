"""Clean Source 4 — DataSaudi indicators (curated)
    -> data/processed/tourism_indicators/tourism_indicators_clean.csv

Decisions (see data_dictionary.md §9):
  - CURATE: keep only the tables that add distinct value (purpose of visit, spending by
    purpose, NPS, satisfaction, complementary indicators). Drop the ones that duplicate
    Source 3 (length of stay, spend/night, spend/trip, overnight stays) and the heavy
    monthly/annual occupancy series.
  - Reshape everything to one LONG table: indicator, period, dimension, dimension_value,
    value, unit.
  - Drop constant `Economic Sectors`/`*_ID` columns and any `Grand Total` rollup rows.
"""
from __future__ import annotations

import pandas as pd

# Allow running this file directly (IDE 'Run') as well as `python -m src.cleaning.<x>`.
import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

from src.cleaning.common import RAW, report, save_processed

ENTITY = "tourism_indicators"
DIR = RAW / "tourism_statistics" / "tourism_statistics_datasaudi"


def _rows(indicator, period, value, unit, dimension=None, dim_value=None):
    return pd.DataFrame({
        "indicator": indicator, "period": period.astype(str),
        "dimension": dimension, "dimension_value": dim_value,
        "value": pd.to_numeric(value, errors="coerce"), "unit": unit,
    })


def clean() -> pd.DataFrame:
    parts = []

    # 1. Tourists by trip purpose (count).
    d = pd.read_csv(DIR / "mot_tourism_by_trip_main_purpose_and_tourists_type.csv")
    parts.append(_rows("tourists_by_purpose", d["Year"], d["Tourists"], "count",
                       "trip_purpose|nationality",
                       d["Trip Purpose Name"].astype(str) + " | " + d["Nationality"].astype(str)))

    # 2. Spending by trip purpose (million SAR).
    d = pd.read_csv(DIR / "sama_tourism_expenditure_by_trip_purpose_and_tourists_type.csv")
    parts.append(_rows("spending_by_purpose", d["Year"], d["Million SAR"], "sar_million",
                       "trip_purpose|tourist_type",
                       d["Trip Purpose Name"].astype(str) + " | " + d["Tourist Type Name"].astype(str)))

    # 3. Net Promoter Score (quarterly index).
    d = pd.read_csv(DIR / "net_promoter_score.csv")
    parts.append(_rows("net_promoter_score", d["Quarter"], d["Net Promoter Score"], "index"))

    # 4. Tourism Satisfaction Index (quarterly ratio).
    d = pd.read_csv(DIR / "tourism_satisfaction_index.csv")
    parts.append(_rows("tourism_satisfaction_index", d["Quarter"], d["Tourism Satisfaction Index"], "ratio"))

    # 5. Complementary indicators (wide -> long; one indicator per column).
    d = pd.read_csv(DIR / "tourism_complementary_indicators.csv")
    for col in [c for c in d.columns if c != "Year"]:
        key = col.strip().lower().replace(" ", "_")
        parts.append(_rows(f"complementary:{key}", d["Year"], d[col], "ratio"))

    out = pd.concat(parts, ignore_index=True)
    # Drop Grand Total rollups if they leaked into any dimension_value.
    out = out[~out["dimension_value"].fillna("").str.contains("Grand Total")].reset_index(drop=True)

    out["source"] = "datasaudi"
    out["source_id"] = ""
    out["source_url"] = "https://datasaudi.mep.gov.sa"
    out["data_period"] = "2014-2025"
    out["snapshot_date"] = pd.NaT
    out["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    out["is_live"] = False

    issues = []
    if out["value"].isna().any():
        issues.append(f"value: {int(out['value'].isna().sum())} nulls")
    report(ENTITY, sum(1 for _ in DIR.glob("*.csv")), out, issues)
    print("  indicators:", out["indicator"].nunique(), "| files kept: 5 of 11")
    return out


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
