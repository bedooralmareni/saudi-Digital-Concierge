"""Shared cleaning utilities: paths, text normalization, geo validity, IO, validation.

Cleaning principle (see docs/data_dictionary.md):
  raw  ->  clean  ->  validate  ->  save processed
Raw data under data/raw/ is READ-ONLY and never modified. Cleaned tables are written to
data/processed/<entity>/<entity>_clean.csv.

We prefer to PRESERVE information over deleting it: ambiguous/unknown values become
`null` (unknown) rather than being coerced to a misleading concrete value, and rows are
only dropped for documented reasons (non-Saudi, unrecoverable corruption).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root: walk up until we find data/raw.
_p = Path(__file__).resolve()
while _p != _p.parent and not (_p / "data" / "raw").exists():
    _p = _p.parent
ROOT = _p
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# Saudi bounding box — a coordinate-VALIDITY check only, NOT proof of Saudi membership
# (the box overlaps neighbouring countries). See data_dictionary.md §1.4.
SA_LAT = (16.0, 32.5)
SA_LON = (34.5, 56.0)

# Arabic diacritics/tatweel ONLY (harakat, superscript alef, Quranic marks, tatweel).
# Must NOT touch the Arabic letter block (U+0621-U+064A).
_AR_DIACRITICS = re.compile(r"[ـً-ٰٟۖ-ۭ]")
_WS = re.compile(r"\s+")


def norm_text(text) -> str | None:
    """NFKC-normalize, strip Arabic diacritics/tatweel, collapse whitespace."""
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return None
    t = unicodedata.normalize("NFKC", str(text))
    t = _AR_DIACRITICS.sub("", t)
    t = _WS.sub(" ", t).strip()
    return t or None


def valid_coord(lat, lon):
    """Return (lat, lon) if inside the Saudi bbox, else (None, None)."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
    if SA_LAT[0] <= lat <= SA_LAT[1] and SA_LON[0] <= lon <= SA_LON[1]:
        return lat, lon
    return None, None


def make_id(prefix: str, n: int, width: int = 5) -> str:
    return f"{prefix}_{n:0{width}d}"


def save_processed(df: pd.DataFrame, entity: str, filename: str | None = None) -> Path:
    """Write a cleaned table to data/processed/<entity>/<filename>."""
    out_dir = PROCESSED / entity
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (filename or f"{entity}_clean.csv")
    df.to_csv(path, index=False)
    return path


def validate(df: pd.DataFrame, *, entity: str, pk: str, required: list[str],
             region_col: str | None = "region") -> list[str]:
    """Assert the data contract; return a list of human-readable issues (empty = OK)."""
    from src.cleaning.geo import REGIONS
    issues = []
    if df[pk].isna().any():
        issues.append(f"{pk}: has nulls")
    if df[pk].duplicated().any():
        issues.append(f"{pk}: {int(df[pk].duplicated().sum())} duplicate ids")
    for col in required:
        if col not in df.columns:
            issues.append(f"missing required column: {col}")
        elif df[col].isna().any():
            issues.append(f"{col}: {int(df[col].isna().sum())} nulls in required column")
    if region_col and region_col in df.columns:
        bad = set(df[region_col].dropna().unique()) - REGIONS
        if bad:
            issues.append(f"{region_col}: unmapped regions {sorted(bad)}")
    return issues


def report(entity: str, raw_rows: int, df: pd.DataFrame, issues: list[str]) -> None:
    print(f"\n=== {entity} ===")
    print(f"  raw rows      : {raw_rows}")
    print(f"  cleaned rows  : {len(df)}")
    print(f"  columns       : {len(df.columns)}")
    print(f"  contract check: {'OK' if not issues else 'ISSUES'}")
    for i in issues:
        print(f"    - {i}")
