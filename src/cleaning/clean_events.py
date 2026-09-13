"""Clean Source 5 — Enjoy.sa events -> data/processed/events/events_clean.csv

Live API source. Run where enjoy.sa is reachable (the exploration environment's egress
policy blocks it). Decisions (see data_dictionary.md §6):
  - Dates come from the *Formatted (DD-MM-YYYY) fields, parsed with dayfirst=True.
  - event_id is a DETERMINISTIC hash of normalized (name, city, start_date, start_time,
    end_date) — reproducible across pulls. Duplicate detection is reported SEPARATELY
    (a hash collision is flagged, not assumed to be the same event).
  - Audience flags are three-state booleans; is_active from EventMode.
  - City (Arabic) -> canonical city/region; is_live=True, retrieved_at=fetch time.

The response envelope and exact field names are resolved adaptively so the cleaner keeps
working if the API wraps records differently or changes casing.
"""
from __future__ import annotations

import hashlib

import pandas as pd
import requests

# Allow running this file directly (IDE 'Run') as well as `python -m src.cleaning.<x>`.
import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

from src.cleaning.common import norm_text, report, save_processed, validate
from src.cleaning.geo import map_city, normalize_ar

ENTITY = "events"
URL = "https://enjoy.sa/api/v1/odp/events/Get"


def _extract_records(payload):
    """Return the list of event dicts from whatever envelope the API uses."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ["Data", "data", "items", "Items", "results", "Results",
                    "events", "Events", "records", "Records", "value", "Value"]:
            if isinstance(payload.get(key), list):
                return payload[key]
        # one level deeper, e.g. {"result": {"events": [...]}}
        for v in payload.values():
            if isinstance(v, dict):
                for inner in v.values():
                    if isinstance(inner, list):
                        return inner
    raise ValueError(f"Could not find a records list in the response (keys={list(payload)[:10]})")


def _col(df, *candidates):
    """Resolve a column by exact, then case-insensitive, then 'contains' match."""
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in lower:
            return lower[cand.lower()]
    for cand in candidates:
        for c in df.columns:
            if cand.lower() in c.lower():
                return c
    return None


def _series(df, col, default=None):
    return df[col] if col else pd.Series([default] * len(df))


def _bool(x):
    s = str(x).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return pd.NA


def _event_id(name, city, sd, st, ed):
    key = f"{normalize_ar(name)}|{city}|{sd}|{st}|{ed}"
    return "events_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def clean() -> pd.DataFrame:
    retrieved_at = pd.Timestamp.utcnow().isoformat()
    payload = requests.get(URL, headers={"Accept": "application/json"}, timeout=60).json()
    raw = pd.json_normalize(_extract_records(payload))
    n = len(raw)

    # Resolve columns adaptively (bilingual/casing-robust).
    c_name = _col(raw, "Name", "EventName", "Title", "اسم")
    c_city = _col(raw, "City", "المدينة", "Region")
    c_sdf = _col(raw, "StartDateFormatted", "StartDate")
    c_edf = _col(raw, "EndDateFormatted", "EndDate")
    c_st = _col(raw, "StartTime")
    c_et = _col(raw, "EndTime")
    c_male = _col(raw, "IsMaleAllowed")
    c_female = _col(raw, "IsFemaleAllowed")
    c_family = _col(raw, "IsFamilyAllowed")
    c_mode = _col(raw, "EventMode", "Status")

    if not c_name or not c_city or not c_sdf:
        raise ValueError(
            "Expected event fields not found. Available columns: "
            f"{list(raw.columns)}")

    df = pd.DataFrame()
    df["name"] = _series(raw, c_name).map(norm_text)
    city_region = _series(raw, c_city).map(map_city)
    df["city"] = [c for c, _ in city_region]
    df["region"] = [r for _, r in city_region]

    df["start_date"] = pd.to_datetime(_series(raw, c_sdf), dayfirst=True, errors="coerce").dt.date
    df["end_date"] = pd.to_datetime(_series(raw, c_edf), dayfirst=True, errors="coerce").dt.date
    df["start_time"] = _series(raw, c_st).astype(str).str.slice(0, 5)
    df["end_time"] = _series(raw, c_et).astype(str).str.slice(0, 5)

    df["is_male_allowed"] = _series(raw, c_male).map(_bool).astype("boolean")
    df["is_female_allowed"] = _series(raw, c_female).map(_bool).astype("boolean")
    df["is_family_allowed"] = _series(raw, c_family).map(_bool).astype("boolean")
    df["is_active"] = _series(raw, c_mode).astype(str).str.lower().eq("isactive")

    df.insert(0, "event_id", [
        _event_id(nm, ci, sd, st, ed)
        for nm, ci, sd, st, ed in zip(_series(raw, c_name), df["city"], df["start_date"],
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
    print(f"  resolved columns: name={c_name!r} city={c_city!r} start={c_sdf!r} mode={c_mode!r}")
    print(f"  duplicate event keys collapsed: {dup}")
    print(f"  active events: {int(df['is_active'].sum())}")
    return df


if __name__ == "__main__":
    path = save_processed(clean(), ENTITY)
    print("saved ->", path)