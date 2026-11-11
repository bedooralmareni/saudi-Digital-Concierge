"""Read-only retrieval over Hadeer's SQLite snapshot.

Hard constraints are applied before semantic ranking, deduplication and limits.
This module neither reads evaluation gold nor calls a language model.
"""
from __future__ import annotations
import inspect
import json
import math
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

ALIASES = {
    "الرياض": "Riyadh", "جدة": "Jeddah", "جده": "Jeddah", "أبها": "Abha", "ابها": "Abha",
    "الدمام": "Dammam", "الخبر": "Al Khobar", "خبر": "Al Khobar", "الطائف": "Taif",
    "مكة": "Makkah", "مكه": "Makkah", "مكة المكرمة": "Makkah", "المدينة": "Madinah",
    "المدينة المنورة": "Madinah", "العلا": "Al Ula", "تبوك": "Tabuk", "حائل": "Hail",
    "بريدة": "Buraydah", "بريده": "Buraydah", "الأحساء": "Al Ahsa", "الاحساء": "Al Ahsa",
}
GROUPS = {"hotel": ("hotels", "hotel_id"), "place": ("places", "place_id"),
          "entertainment": ("entertainment", "entertainment_id"), "event": ("events", "event_id")}


def normalize_city(city):
    if city is None:
        return None
    if not isinstance(city, str) or not city.strip():
        raise ValueError("city must be a nonempty string")
    return ALIASES.get(city.strip(), city.strip())


def text(value, name):
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{name} must be a nonempty string or null")


def number(value, name, minimum=0, maximum=float("inf"), integer=False):
    if value is None:
        return
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if integer and type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside its allowed range")


def boolean(value, name):
    if value is not None and type(value) is not bool:
        raise ValueError(f"{name} must be true, false or null")


def iso_date(value, name):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return value


def exclusions(exclude_ids):
    if exclude_ids is None:
        return []
    if not isinstance(exclude_ids, list) or not all(isinstance(x, str) and x for x in exclude_ids):
        raise ValueError("exclude_ids must be a list of record IDs")
    return exclude_ids


def identity_filters(city, record_id, name, id_column):
    city = normalize_city(city)
    text(record_id, "record_id"); text(name, "name")
    if city is None and record_id is None and name is None:
        raise ValueError("Provide city for a search, or record_id/name for a direct lookup")
    where, params = [], []
    if city is not None:
        where.append("LOWER(TRIM(city))=LOWER(TRIM(?))"); params.append(city)
    if record_id is not None:
        where.append(id_column + "=?"); params.append(record_id)
    if name is not None:
        where.append("LOWER(TRIM(name))=LOWER(TRIM(?))"); params.append(name.strip())
    return where, params


def add_lower(where, params, column, value):
    if value is not None:
        where.append(column + ">=?"); params.append(value)


def add_flag(where, params, column, value):
    if value is not None:
        where.append(column + "=?"); params.append(int(value))


def distinct_key(row):
    key = (row["name"].strip().casefold(), row.get("city"))
    if row["entity_type"] == "event":
        key += (row.get("start_date"), row.get("end_date"))
    return key


class ExistingVectorRanker:
    """Reuse the notebook's E5 vectors. Missing ID coverage is an explicit error.

    No fresh model/vector download is performed here. Candidate records are already
    SQL-filtered. Semantic scores affect ordering only, never constraint compliance.
    """
    def __init__(self, vectors, metadata, embedder):
        import numpy as np
        if len(vectors) != len(metadata):
            raise ValueError("Vector/metadata row count mismatch")
        if "entity_id" not in metadata.columns or "entity_type" not in metadata.columns:
            raise ValueError("Vector metadata must retain source entity_id and entity_type")
        self.vectors, self.embedder = vectors, embedder
        self.positions = {}
        for i, row in enumerate(metadata.to_dict("records")):
            key = (str(row["entity_type"]), str(row["entity_id"]))
            self.positions.setdefault(key, []).append(i)
        if not np.isfinite(vectors).all():
            raise ValueError("Non-finite vector values")

    def __call__(self, query, rows):
        import numpy as np
        groups = []
        for row in rows:
            ids = self.positions.get((row["source_entity_type"], row["record_id"]))
            if not ids:
                raise ValueError("Vector metadata missing a filtered record ID; rebuild the matching index")
            groups.append(ids)
        q = self.embedder.encode(["query: " + query], normalize_embeddings=True)[0]
        if q.shape[0] != self.vectors.shape[1]:
            raise ValueError("Query/index embedding dimension mismatch")
        scored = []
        for row, ids in zip(rows, groups):
            score = float(np.max(self.vectors[ids] @ q))
            scored.append(dict(row, score=round(score, 6), retrieval_method="sql_then_semantic"))
        return sorted(scored, key=lambda r: (-r["score"], r["record_id"]))


class KnowledgeBaseTools:
    def __init__(self, db_path, ranker=None):
        self.db_path = Path(db_path).resolve()
        if not self.db_path.is_file():
            raise FileNotFoundError("Knowledge base missing; supply the fixed SQLite snapshot")
        self.ranker = ranker
        self.functions = {name: getattr(self, name) for name in ["search_hotels", "search_places", "search_events"]}

    def _query(self, kind, where, params):
        table, id_column = GROUPS[kind]
        sql = f"SELECT * FROM {table} WHERE " + (" AND ".join(where) or "1=1") + f" ORDER BY {id_column}"
        with closing(sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            rows = [dict(row) for row in conn.execute(sql, params)]
        for row in rows:
            for key, val in list(row.items()):
                if isinstance(val, float) and not math.isfinite(val):
                    row[key] = None
            row["record_id"] = row[id_column]
            row["source_entity_type"] = kind
            row["entity_type"] = ("restaurant" if kind == "place" and row.get("granular_category") == "restaurants"
                                  else "activity" if kind == "entertainment" else kind)
            row["availability_verified"] = False
            row["retrieval_method"] = "structured_sql"
            if kind == "hotel":
                row["price_basis"] = "historical_recorded_option; nightly_unit_not_verified"
            # Preserve the original source flags; none establishes live verification.
        return rows

    def _finish(self, rows, limit, exclude_ids, query=None, semantic=False, deduplicate=True):
        number(limit, "limit", 1, 100, integer=True)
        if limit is None:
            raise ValueError("limit must not be null")
        excluded = set(exclusions(exclude_ids))
        rows = [r for r in rows if r["record_id"] not in excluded]
        if semantic and rows:
            if self.ranker is None:
                raise ValueError("Semantic ranking requested but the notebook ranker is not configured")
            rows = self.ranker(query, rows)
        result, seen = [], set()
        for row in rows:
            key = distinct_key(row)
            if deduplicate and key in seen:
                continue
            seen.add(key); result.append(row)
            if len(result) == limit:
                break
        return result

    def search_hotels(self, city=None, max_price_per_night=None, min_guest_rating=None,
                      guests=None, limit=5, *, max_price_sar=None, price_operator="lte",
                      min_stars=None, breakfast_included=None, free_cancellation=None,
                      record_id=None, name=None, exclude_ids=None):
        """max_price_per_night is a legacy alias, not verification of a nightly unit."""
        for key, val, high in [("max_price_sar", max_price_sar, float("inf")),
                              ("max_price_per_night", max_price_per_night, float("inf")),
                              ("min_guest_rating", min_guest_rating, 10), ("min_stars", min_stars, 5)]:
            number(val, key, maximum=high)
        number(guests, "guests", 1, integer=True)
        for key, val in [("breakfast_included", breakfast_included), ("free_cancellation", free_cancellation)]:
            boolean(val, key)
        if price_operator not in ("lt", "lte"):
            raise ValueError("price_operator must be lt or lte")
        if max_price_sar is not None and max_price_per_night is not None and max_price_sar != max_price_per_night:
            raise ValueError("Conflicting price aliases")
        cap = max_price_sar if max_price_sar is not None else max_price_per_night
        where, params = identity_filters(city, record_id, name, "hotel_id")
        if cap is not None:
            where.append("price_sar" + ("<?" if price_operator == "lt" else "<=?")); params.append(cap)
        for col, val in [("guest_rating", min_guest_rating), ("star_rating", min_stars), ("max_persons", guests)]:
            add_lower(where, params, col, val)
        add_flag(where, params, "breakfast_included", breakfast_included)
        add_flag(where, params, "free_cancellation", free_cancellation)
        return self._finish(self._query("hotel", where, params), limit, exclude_ids,
                            deduplicate=record_id is None)

    def search_places(self, query="", city=None, entity_type=None, top_k=5, *,
                      category=None, genre=None, min_rating=None, min_review_count=None,
                      record_id=None, name=None, exclude_ids=None, semantic=True):
        """Exact restaurant tag/genre/rating filters before E5 ranking.

        For a record lookup, pass record_id (query and city may be omitted).
        category matches one complete pipe-delimited food tag, not a substring.
        """
        if not isinstance(query, str):
            raise ValueError("query must be a string")
        if type(semantic) is not bool:
            raise ValueError("semantic must be true or false")
        text(category, "category"); text(genre, "genre"); text(record_id, "record_id")
        number(min_rating, "min_rating", 0, 5)
        number(min_review_count, "min_review_count", integer=True)
        number(top_k, "top_k", 1, 100, integer=True)
        aliases = {"attraction": "entertainment", "attractions": "entertainment", "activity": "entertainment",
                   "activities": "entertainment", "restaurant": "restaurant", "restaurants": "restaurant",
                   "place": "place", "entertainment": "entertainment"}
        if entity_type is None:
            types = ["place", "entertainment"]
        elif not isinstance(entity_type, str):
            raise ValueError("entity_type must be a string")
        else:
            supplied = [part.strip().casefold() for part in entity_type.split(",")]
            if not supplied or any(t not in aliases for t in supplied):
                raise ValueError("Use restaurant, place or entertainment; unsupported types are not broadened")
            types = list(dict.fromkeys(aliases[t] for t in supplied))
        if category is not None and types != ["restaurant"]:
            raise ValueError("category is an exact restaurant tag; use entity_type=restaurant")
        if genre is not None and types != ["entertainment"]:
            raise ValueError("genre requires entity_type=entertainment")
        result = []
        for chosen in types:
            kind = "place" if chosen == "restaurant" else chosen
            _, id_column = GROUPS[kind]
            where, params = identity_filters(city, record_id, name, id_column)
            if chosen == "restaurant":
                where.append("granular_category='restaurants'")
            if category is not None:
                # Escape LIKE metacharacters so user text cannot relax the exact-tag filter.
                tag = category.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                where.append("('|' || categories || '|') LIKE ? ESCAPE '\\'"); params.append("%|" + tag + "|%")
            if genre is not None:
                where.append("genre=?"); params.append(genre)
            add_lower(where, params, "average_rating" if kind == "place" else "rating", min_rating)
            add_lower(where, params, "rate_count" if kind == "place" else "review_count", min_review_count)
            result.extend(self._query(kind, where, params))
        # Deduplicate source IDs when callers request overlapping types, e.g. place,restaurant.
        result = list({r["record_id"]: r for r in result}.values())
        return self._finish(result, top_k, exclude_ids, query=query,
                            semantic=semantic and bool(query.strip()) and record_id is None,
                            deduplicate=record_id is None)

    def search_events(self, city=None, start_date=None, end_date=None, limit=10, *,
                      date_mode="overlap", family=None, record_id=None, name=None,
                      reference_date=None, exclude_ids=None):
        """date_mode=starts_in tests event START in the window; overlap tests intersection.

        reference_date reports recorded_ongoing_on_reference, independent of is_active.
        This is a date comparison, never verification of live operation.
        """
        boolean(family, "family")
        if date_mode not in ("overlap", "starts_in"):
            raise ValueError("date_mode must be overlap or starts_in")
        where, params = identity_filters(city, record_id, name, "event_id")
        has_dates = start_date is not None or end_date is not None
        if has_dates:
            start_date = iso_date(start_date, "start_date"); end_date = iso_date(end_date, "end_date")
            if start_date > end_date:
                raise ValueError("Invalid date range: start is after end")
            if date_mode == "starts_in":
                where += ["date(start_date)>=date(?)", "date(start_date)<=date(?)"]
                params += [start_date, end_date]
            else:
                where += ["date(start_date)<=date(?)", "date(COALESCE(NULLIF(end_date,''),start_date))>=date(?)"]
                params += [end_date, start_date]
        elif record_id is None and name is None:
            raise ValueError("Provide travel dates, or record_id/name for an event lookup")
        add_flag(where, params, "is_family_allowed", family)
        rows = self._query("event", where, params)
        if reference_date is not None:
            iso_date(reference_date, "reference_date")
            for row in rows:
                try:
                    first = iso_date(row["start_date"], "stored start")
                    last = iso_date(row["end_date"] or row["start_date"], "stored end")
                    row["recorded_ongoing_on_reference"] = first <= reference_date <= last if first <= last else None
                except ValueError:
                    row["recorded_ongoing_on_reference"] = None
                row["reference_date"] = reference_date
        return self._finish(rows, limit, exclude_ids, deduplicate=record_id is None)

    def execute_tool(self, name, arguments):
        """Keep Hadeer's list/error return convention for the existing agent loop."""
        if not isinstance(name, str) or name not in self.functions:
            return {"error": "Unknown tool", "error_type": "UnknownTool"}
        if not isinstance(arguments, dict):
            return {"error": "Arguments must be an object", "error_type": "InvalidArguments"}
        try:
            inspect.signature(self.functions[name]).bind(**arguments)
            result = self.functions[name](**arguments)
            return json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as exc:
            return {"error": str(exc), "error_type": "InvalidArgumentsOrIndex"}
        except sqlite3.Error:
            return {"error": "Database query failed", "error_type": "DatabaseError"}


def field(kind, description, **kwargs):
    return {"type": kind, "description": description, **kwargs}


ID = field("string", "Exact source record ID for direct lookup; missing fields remain null.")
CITY = field("string", "City in English or a supported Arabic alias. Required for ordinary search.")
NAME = field("string", "Exact recorded name for lookup; do not use fuzzy guessing.")
LIMIT = field("integer", "Maximum number of distinct options to return.", minimum=1, maximum=100)
EXCLUDE = {"type": "array", "items": {"type": "string"}, "description": "Exact source record IDs to exclude."}


def tool(name, description, properties):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": [], "additionalProperties": False}}}


TOOLS = [
    tool("search_hotels", "Search historical hotel records by city, recorded price, capacity, stars, guest rating and explicit flags. Or look up a record_id/name. Missing values are unknown. Price is not a verified nightly quote.", {
        "city": CITY, "record_id": ID, "name": NAME,
        "max_price_sar": field("number", "Bound on historical recorded price, SAR.", minimum=0),
        "price_operator": field("string", "lt means strictly below; lte means at most.", enum=["lt", "lte"]),
        "min_guest_rating": field("number", "Minimum guest rating out of 10.", minimum=0, maximum=10),
        "min_stars": field("number", "Minimum star classification, separate from guest rating.", minimum=0, maximum=5),
        "guests": field("integer", "Required recorded capacity of each option.", minimum=1),
        "breakfast_included": field("boolean", "Require recorded true or recorded false; omit if unspecified."),
        "free_cancellation": field("boolean", "Require recorded true or false; null in DB never satisfies either."),
        "limit": LIMIT, "exclude_ids": EXCLUDE}),
    tool("search_places", "Search places/entertainment with SQL hard filters before semantic ranking. Use restaurant for verified food venues, entertainment for activities. Return exact IDs and native rating/count fields. Or look up record_id/name with no query.", {
        "query": field("string", "Soft semantic preference, e.g. cultural activities; omit for a lookup."),
        "city": CITY, "record_id": ID, "name": NAME,
        "entity_type": field("string", "restaurant, entertainment or place; comma-separated combinations only if no type-specific filter."),
        "category": field("string", "Exact complete restaurant tag, e.g. Italian. Requires entity_type=restaurant."),
        "genre": field("string", "Exact entertainment genre, e.g. Science museum. Requires entity_type=entertainment."),
        "min_rating": field("number", "Minimum rating out of 5.", minimum=0, maximum=5),
        "min_review_count": field("integer", "Minimum recorded review/rating count.", minimum=0),
        "top_k": LIMIT, "exclude_ids": EXCLUDE,
        "semantic": field("boolean", "Default true for nonempty query. False uses deterministic SQL order after filters.")}),
    tool("search_events", "Search saved event records or look up record_id/name. starts_in means the event begins inside the window; overlap means its dates intersect the window. Flags and date ranges do not verify live operation.", {
        "city": CITY, "record_id": ID, "name": NAME,
        "start_date": field("string", "Inclusive window start YYYY-MM-DD; required together with end_date for searches."),
        "end_date": field("string", "Inclusive window end YYYY-MM-DD."),
        "date_mode": field("string", "Use starts_in for 'events starting in a month'; overlap for visit date intersection.", enum=["overlap", "starts_in"]),
        "family": field("boolean", "Require explicit family permission or prohibition; omit if unspecified."),
        "reference_date": field("string", "Fixed YYYY-MM-DD for comparing recorded dates independently of is_active."),
        "limit": LIMIT, "exclude_ids": EXCLUDE}),
]
