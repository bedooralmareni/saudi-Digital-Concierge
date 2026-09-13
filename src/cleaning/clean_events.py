"""Clean Source 5 — Enjoy.sa events -> data/processed/events/events_clean.csv

Live API source. Run where enjoy.sa is reachable (the exploration environment's egress
policy blocks it). Decisions (see data_dictionary.md §6):
  - Dates come from the *Formatted (DD-MM-YYYY) fields, parsed with dayfirst=True.
  - event_id is a DETERMINISTIC hash of normalized (name, city, start_date, start_time,
    end_date) — reproducible across pulls. Duplicate detection is reported SEPARATELY
    (a hash collision is flagged, not assumed to be the same event).
  - Audience flags are three-state booleans; is_active from EventMode.
  - City (Arabic) -> canonical city/region; is_live=True, retrieved_at=fetch time.
"""
from __future__ import annotations

import hashlib

import pandas as pd
import requests

from src.cleaning.common import norm_text, report, save_processed, validate
from src.cleaning.geo import map_city, normalize_ar

ENTITY = "events"
URL = "https://enjoy.sa/api/v1/odp/events/Get"


def _bool(x):
    if x is True or str(x).lower() == "true":
        return True
    if x is False or str(x).lower() == "false":
        return False
    return pd.NA


def _event_id(name, city, sd, st, ed):
    key = f"{normalize_ar(name)}|{city}|{sd}|{st}|{ed}"
    return "events_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def clean() -> pd.DataFrame:
    retrieved_at = pd.Timestamp.utcnow().isoformat()
    payload = requests.get(URL, headers={"Accept": "application/json"}, timeout=60).json()
    records = payload["Data"] if isinstance(payload, dict) else payload
    raw = pd.json_normalize(records)
    n = len(raw)

    df = pd.DataFrame()
    df["name"] = raw["Name"].map(norm_text)
    city_region = raw["City"].map(map_city)
    df["city"] = [c for c, _ in city_region]
    df["region"] = [r for _, r in city_region]

    df["start_date"] = pd.to_datetime(raw["StartDateFormatted"], dayfirst=True, errors="coerce").dt.date
    df["end_date"] = pd.to_datetime(raw["EndDateFormatted"], dayfirst=True, errors="coerce").dt.date
    df["start_time"] = raw["StartTime"].astype(str).str.slice(0, 5)
    df["end_time"] = raw["EndTime"].astype(str).str.slice(0, 5)

    df["is_male_allowed"] = raw["IsMaleAllowed"].map(_bool).astype("boolean")
    df["is_female_allowed"] = raw["IsFemaleAllowed"].map(_bool).astype("boolean")
    df["is_family_allowed"] = raw["IsFamilyAllowed"].map(_bool).astype("boolean")
    df["is_active"] = raw["EventMode"].astype(str).str.lower().eq("isactive")

    df.insert(0, "event_id", [
        _event_id(nm, ci, sd, st, ed)
        for nm, ci, sd, st, ed in zip(raw["Name"], df["city"], df["start_date"],
                                      df["start_time"], df["end_date"])])

    df["source"] = "enjoy_sa"
    df["source_id"] = ""
    df["source_url"] = URL
    df["data_period"] = str(pd.Timestamp.utcnow().date())
    df["snapshot_date"] = str(pd.Timestamp.utcnow().date())
    df["retrieved_at"] = retrieved_at
    df["is_live"] = True

    # Duplicate detection is SEPARATE from id generation.
    dup = int(df["event_id"].duplicated().sum())
    df = df.drop_duplicates(subset="event_id").reset_index(drop=True)

    issues = validate(df, entity=ENTITY, pk="event_id",
                      required=["event_id", "name", "city", "start_date", "end_date", "is_active"])
    bad_range = int((pd.to_datetime(df["end_date"]) < pd.to_datetime(df["start_date"])).sum())
    if bad_range:
        issues.append(f"end_date < start_date: {bad_range} rows")
    report(ENTITY, n, df, issues)
    print(f"  duplicate event keys collapsed: {dup}")
    print(f"  active events: {int(df['is_active'].sum())}")
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)
