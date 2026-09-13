"""Structured-retrieval API over the SQLite knowledge base.

Thin, parameterized helpers the Planning/Verifier agents use for exact constraint
queries (the structured half of the hybrid KB). Semantic search lives in the vector
store; the two join on `canonical_id`.

    from src.database.kb import connect, find_hotels, find_places
    find_hotels(city="Riyadh", max_price=500, min_guest_rating=8)
"""
from __future__ import annotations

import sqlite3

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd

from src.cleaning.common import ROOT

DB_PATH = ROOT / "data" / "final" / "knowledge_base.sqlite"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a read-only SQL query and return a DataFrame."""
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


def find_hotels(city=None, region=None, max_price=None, min_guest_rating=None,
                min_star=None, min_persons=None, limit=20) -> pd.DataFrame:
    """Exact-filter hotels (the 'hotels in Riyadh under 500 SAR, rating >= 8' case)."""
    where, params = ["1=1"], []
    if city:
        where.append("city = ?"); params.append(city)
    if region:
        where.append("region = ?"); params.append(region)
    if max_price is not None:
        where.append("price_sar <= ?"); params.append(max_price)
    if min_guest_rating is not None:
        where.append("guest_rating >= ?"); params.append(min_guest_rating)
    if min_star is not None:
        where.append("star_rating >= ?"); params.append(min_star)
    if min_persons is not None:
        where.append("max_persons >= ?"); params.append(min_persons)
    sql = (f"SELECT hotel_id, canonical_id, name, city, region, price_sar, star_rating, "
           f"guest_rating, max_persons, latitude, longitude, source_url "
           f"FROM v_hotels WHERE {' AND '.join(where)} "
           f"ORDER BY guest_rating DESC NULLS LAST LIMIT ?")
    params.append(limit)
    return query(sql, tuple(params))


def find_places(city="Riyadh", is_restaurant=None, min_rating=None, category=None,
                limit=20) -> pd.DataFrame:
    """Exact-filter POIs / restaurants."""
    where, params = ["1=1"], []
    if city:
        where.append("city = ?"); params.append(city)
    if is_restaurant is not None:
        where.append("is_restaurant = ?"); params.append(1 if is_restaurant else 0)
    if min_rating is not None:
        where.append("average_rating >= ?"); params.append(min_rating)
    if category:
        where.append("(granular_category = ? OR categories LIKE ?)")
        params += [category, f"%{category}%"]
    sql = (f"SELECT place_id, canonical_id, name, granular_category, average_rating, "
           f"rate_count, latitude, longitude "
           f"FROM v_places WHERE {' AND '.join(where)} "
           f"ORDER BY average_rating DESC NULLS LAST, rate_count DESC LIMIT ?")
    params.append(limit)
    return query(sql, tuple(params))


def find_entertainment(city=None, genre=None, min_rating=None, limit=20) -> pd.DataFrame:
    where, params = ["country = 'Saudi Arabia'"], []
    if city:
        where.append("city = ?"); params.append(city)
    if genre:
        where.append("genre LIKE ?"); params.append(f"%{genre}%")
    if min_rating is not None:
        where.append("rating >= ?"); params.append(min_rating)
    sql = (f"SELECT entertainment_id, name, genre, rating, city, region "
           f"FROM entertainment WHERE {' AND '.join(where)} "
           f"ORDER BY rating DESC NULLS LAST LIMIT ?")
    params.append(limit)
    return query(sql, tuple(params))


def find_events(city=None, active_only=True, family=None, on_or_after=None, limit=20) -> pd.DataFrame:
    """Exact-filter events (requires events table — run clean_events locally first)."""
    where, params = ["1=1"], []
    if active_only:
        where.append("is_active = 1")
    if city:
        where.append("city = ?"); params.append(city)
    if family is not None:
        where.append("is_family_allowed = ?"); params.append(1 if family else 0)
    if on_or_after:
        where.append("end_date >= ?"); params.append(on_or_after)
    sql = (f"SELECT event_id, name, city, region, start_date, end_date, "
           f"is_family_allowed, is_active FROM events WHERE {' AND '.join(where)} "
           f"ORDER BY start_date LIMIT ?")
    params.append(limit)
    return query(sql, tuple(params))


def reviews_for(canonical_id: str, limit=20) -> pd.DataFrame:
    """Reviews resolved to a canonical place (evidence for the Verifier)."""
    return query(
        "SELECT review_id, place_name_raw, city, review_text, sent_overall "
        "FROM v_reviews_resolved WHERE canonical_id = ? LIMIT ?",
        (canonical_id, limit))


if __name__ == "__main__":
    print("Example: hotels in Riyadh under 500 SAR with guest rating >= 8")
    print(find_hotels(city="Riyadh", max_price=500, min_guest_rating=8, limit=5).to_string(index=False))
