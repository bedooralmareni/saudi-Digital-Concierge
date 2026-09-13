"""Build the structured SQLite knowledge base — the exact-filter half of the hybrid KB.

Loads the cleaned + standardized + entity-resolved tables into a typed SQLite database
(`data/final/knowledge_base.sqlite`) with indexes and convenience views, so the
Planning/Verifier agents can answer hard-constraint queries deterministically, e.g.:

    SELECT * FROM hotels
    WHERE city = 'Riyadh' AND price_sar < 500 AND guest_rating >= 8
    ORDER BY guest_rating DESC;

Semantic ("suitable for a culture lover") queries are served by the separate vector store
built from the embed=True kb_documents; the two join on `canonical_id` / `entity_id`.

Run:  python -m src.database.build_sqlite
"""
from __future__ import annotations

import sqlite3

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import pandas as pd

from src.cleaning.common import PROCESSED, ROOT

DB_PATH = ROOT / "data" / "final" / "knowledge_base.sqlite"
STD = PROCESSED / "standardized"

# entity table -> (csv path, primary key). Loaded as-is (already typed & clean).
TABLES = {
    "places": (PROCESSED / "places" / "places_clean.csv", "place_id"),
    "hotels": (PROCESSED / "hotels" / "hotels_clean.csv", "hotel_id"),
    "entertainment": (PROCESSED / "entertainment" / "entertainment_clean.csv", "entertainment_id"),
    "reviews": (PROCESSED / "reviews" / "reviews_clean.csv", "review_id"),
    "tourism_statistics": (PROCESSED / "tourism_statistics" / "tourism_statistics_clean.csv", None),
    "tourism_indicators": (PROCESSED / "tourism_indicators" / "tourism_indicators_clean.csv", None),
    # standardized / entity-resolution layer
    "entities_core": (STD / "entities_core.csv", "entity_id"),
    "canonical_entities": (STD / "canonical_entities.csv", "canonical_id"),
    "entity_crosswalk": (STD / "entity_crosswalk.csv", None),
    "candidate_links": (STD / "candidate_links.csv", None),
    "review_place_links": (STD / "review_place_links.csv", "review_id"),
}
# events is included automatically if it has been generated locally.
_EVENTS = PROCESSED / "events" / "events_clean.csv"
if _EVENTS.exists():
    TABLES["events"] = (_EVENTS, "event_id")

# Columns to index per table (filter/join keys) — only created if the column exists.
INDEXES = {
    "places": ["city", "region", "is_restaurant", "average_rating", "granular_category"],
    "hotels": ["city", "region", "price_sar", "star_rating", "guest_rating", "max_persons"],
    "entertainment": ["city", "region", "rating", "genre"],
    "reviews": ["place_id", "city", "category"],
    "events": ["city", "region", "start_date", "end_date", "is_active"],
    "tourism_statistics": ["year", "region", "tourism_type"],
    "tourism_indicators": ["indicator", "period"],
    "entities_core": ["entity_type", "city", "region", "rating_norm", "price_sar"],
    "canonical_entities": ["city", "region", "entity_types"],
    "entity_crosswalk": ["canonical_id", "source", "source_entity_id"],
    "review_place_links": ["canonical_id"],
}

# Convenience views used by the agents.
VIEWS = {
    # every entity crosswalked to its canonical id (join hub)
    "v_entity_canonical": """
        CREATE VIEW v_entity_canonical AS
        SELECT x.canonical_id, x.entity_type, x.source, x.source_entity_id,
               c.name AS canonical_name, c.city, c.region, c.latitude, c.longitude
        FROM entity_crosswalk x
        LEFT JOIN canonical_entities c ON c.canonical_id = x.canonical_id
    """,
    # hotels enriched with their canonical id
    "v_hotels": """
        CREATE VIEW v_hotels AS
        SELECT h.*, x.canonical_id
        FROM hotels h
        LEFT JOIN entity_crosswalk x
          ON x.source_entity_id = h.hotel_id AND x.source = 'booking_kaggle'
    """,
    # places enriched with their canonical id
    "v_places": """
        CREATE VIEW v_places AS
        SELECT p.*, x.canonical_id
        FROM places p
        LEFT JOIN entity_crosswalk x
          ON x.source_entity_id = p.place_id AND x.source = 'riyadh_places_kaggle'
    """,
    # reviews attached to their resolved canonical place (nullable)
    "v_reviews_resolved": """
        CREATE VIEW v_reviews_resolved AS
        SELECT r.review_id, r.place_name_raw, r.city, r.review_text,
               r.sent_overall, r.sent_cleanliness, r.sent_service,
               l.canonical_id, l.name_sim
        FROM reviews r
        LEFT JOIN review_place_links l ON l.review_id = r.review_id
    """,
}


def build():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # rebuild from scratch for reproducibility
    con = sqlite3.connect(DB_PATH)

    loaded = {}
    for table, (path, pk) in TABLES.items():
        if not path.exists():
            print(f"  - {table}: (missing, skipped)")
            continue
        df = pd.read_csv(path)
        df.to_sql(table, con, if_exists="replace", index=False)
        loaded[table] = (len(df), pk, list(df.columns))
        # unique index on the primary key where defined and actually unique
        if pk and pk in df.columns and not df[pk].duplicated().any():
            con.execute(f'CREATE UNIQUE INDEX "ux_{table}_{pk}" ON "{table}"("{pk}")')
        print(f"  - {table}: {len(df)} rows")

    # secondary indexes
    n_idx = 0
    for table, cols in INDEXES.items():
        if table not in loaded:
            continue
        existing = loaded[table][2]
        for col in cols:
            if col in existing:
                con.execute(f'CREATE INDEX IF NOT EXISTS "ix_{table}_{col}" ON "{table}"("{col}")')
                n_idx += 1

    # views
    n_view = 0
    for name, ddl in VIEWS.items():
        need = _view_deps(name)
        if all(t in loaded for t in need):
            con.executescript(ddl)
            n_view += 1
        else:
            print(f"  - view {name}: skipped (needs {need})")

    con.commit()
    _report(con, loaded, n_idx, n_view)
    con.close()
    print(f"\nsaved -> {DB_PATH}")


def _view_deps(view):
    return {
        "v_entity_canonical": {"entity_crosswalk", "canonical_entities"},
        "v_hotels": {"hotels", "entity_crosswalk"},
        "v_places": {"places", "entity_crosswalk"},
        "v_reviews_resolved": {"reviews", "review_place_links"},
    }[view]


def _report(con, loaded, n_idx, n_view):
    print(f"\ntables: {len(loaded)} | indexes: {n_idx} | views: {n_view}")
    # smoke-test the two thesis example queries
    print("\nsmoke test — structured filter:")
    q1 = ("SELECT COUNT(*) FROM hotels "
          "WHERE city='Riyadh' AND price_sar < 500 AND guest_rating >= 8")
    try:
        print(f"  hotels in Riyadh < 500 SAR & guest_rating>=8: {con.execute(q1).fetchone()[0]}")
    except sqlite3.Error as e:
        print("  q1 error:", e)
    q2 = ("SELECT COUNT(*) FROM places "
          "WHERE city='Riyadh' AND is_restaurant=1 AND average_rating >= 4.5")
    print(f"  Riyadh restaurants rated>=4.5: {con.execute(q2).fetchone()[0]}")
    q3 = "SELECT COUNT(*) FROM canonical_entities WHERE n_members > 1"
    print(f"  canonical entities with >1 member: {con.execute(q3).fetchone()[0]}")


if __name__ == "__main__":
    build()
