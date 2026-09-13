"""Clean Source 6 — Booking.com hotels -> data/processed/hotels/hotels_clean.csv

Decisions (see data_dictionary.md §5):
  - 2020 snapshot: data_period=2020, snapshot_date=2020-04-24, is_live=False.
  - Star_Rating == 0 -> UNRATED (null), NOT zero-star (52% of rows are apartments etc.).
  - breakfast_included / free_cancellation are THREE-STATE: missing -> null (unknown),
    never coerced to False.
  - Price 'SAR 179' -> numeric price_sar; Max persons text -> int; column-name typos fixed.
  - Coordinates validated against Saudi bbox; city extracted from 'Neighbourhood, City'.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Allow running this file directly (IDE 'Run') as well as `python -m src.cleaning.<x>`.
import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

from src.cleaning.common import make_id, norm_text, RAW, report, save_processed, valid_coord, validate
from src.cleaning.geo import map_city

ENTITY = "hotels"


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def clean() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "Booking.com" / "project3_df1.csv").rename(columns={"Unnamed: 0": "idx"})
    n = len(raw)
    df = pd.DataFrame()

    df["hotel_id"] = [make_id("hotels", i) for i in range(n)]
    df["source_id"] = raw["Property_id"].astype(str)
    df["name"] = raw["Name"].map(norm_text)

    city_region = raw["City"].map(map_city)
    df["city"] = [c for c, _ in city_region]
    df["region"] = [r for _, r in city_region]

    df["price_sar"] = _num(raw["Price"].astype(str).str.replace("SAR", "", regex=False)
                           .str.replace(",", "").str.strip())

    star = _num(raw["Star_Rating"])
    df["star_rating"] = star.where(star.between(1, 5)).astype("Int64")  # 0 -> null (unrated)

    df["guest_rating"] = _num(raw["Customers_Rating"])
    df["guest_rating_count"] = (raw["Customers_Review"].astype(str)
                                .str.extract(r"(\d+)")[0].pipe(_num).astype("Int64"))
    df["room_type"] = raw["Type_of_room"].map(norm_text)
    df["bed_type"] = raw["Bed_type"].map(norm_text)
    df["max_persons"] = (raw["Max_persons"].astype(str).str.extract(r"(\d+)")[0]
                         .pipe(_num).astype("Int64"))

    # THREE-STATE booleans: only set True when explicitly present; missing stays null.
    df["breakfast_included"] = raw["Breakfst_included"].apply(
        lambda x: True if isinstance(x, str) and "breakfast" in x.lower() else pd.NA).astype("boolean")
    df["free_cancellation"] = raw["Canelation"].apply(
        lambda x: True if isinstance(x, str) and "free" in x.lower() else pd.NA).astype("boolean")

    coords = [valid_coord(la, lo) for la, lo in zip(raw["Latitude_y"], raw["Longitude_x"])]
    df["latitude"] = [c[0] for c in coords]
    df["longitude"] = [c[1] for c in coords]
    df["source_url"] = raw["Link"].astype(str)

    df["source"] = "booking_kaggle"
    df["data_period"] = "2020"
    df["snapshot_date"] = "2020-04-24"
    df["retrieved_at"] = pd.Timestamp.utcnow().isoformat()
    df["is_live"] = False

    # DECISION: `region` is best-effort. Saudi towns beyond the canonical mapping keep
    # city + coordinates but a null region (rather than a wrong guess); not a hard fail.
    issues = validate(df, entity=ENTITY, pk="hotel_id",
                      required=["hotel_id", "name", "city", "price_sar",
                                "latitude", "longitude"])
    report(ENTITY, n, df, issues)
    print(f"  star_rating unrated (0->null): {int(df['star_rating'].isna().sum())}")
    print(f"  breakfast null (unknown): {int(df['breakfast_included'].isna().sum())}")
    print(f"  region unmapped (best-effort, null): {int(df['region'].isna().sum())}")
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
