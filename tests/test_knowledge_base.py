import contextlib
import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.vector_store import build_index, search
from src.vector_store.embedder import StubEmbedder
from src.entity_resolution import resolve
from src.database import build_sqlite


@pytest.fixture
def documents():
    rows = [
        ("hotel", "h1", "booking", "Riyadh", 200, .9, "heritage hotel"),
        ("place", "p1", "places", "Riyadh", 50, .8, "heritage museum"),
        ("entertainment", "e1", "ent", "Jeddah", 80, .7, "heritage attraction"),
        ("review", "r1", "reviews", "Riyadh", None, None, "heritage review"),
        ("review", "r2", "reviews", "Riyadh", None, None, "unresolved review"),
        ("place", "p2", "places", "Riyadh", 900, .95, "heritage expensive"),
        ("place", "p3", "places", "Riyadh", 20, .2, "heritage low rating"),
        ("event", "ev1", "events", "Riyadh", None, None, "heritage event"),
        ("place", "p4", "places", "Riyadh", None, None, "heritage unknown"),
    ]
    df = pd.DataFrame(rows, columns=[
        "entity_type", "entity_id", "source", "city", "price_sar", "rating_norm", "text"])
    df["document_id"] = df.entity_id
    df["embed"] = True
    df["region"] = df.city
    df["category"] = "culture"
    df["source_url"] = "https://example.com"
    return df


@pytest.fixture
def mappings():
    cross = pd.DataFrame([
        ("booking", "h1", "C_H"), ("places", "p1", "C_P"),
        ("ent", "e1", "C_E"), ("places", "p2", "C_P2"),
        ("places", "p3", "C_P3"),
    ], columns=["source", "source_entity_id", "canonical_id"])
    links = pd.DataFrame([("r1", "C_P"), ("r2", None)],
                         columns=["review_id", "canonical_id"])
    return cross, links


def test_enrichment_order_count_and_sources(documents, mappings):
    cross, links = mappings
    # The same source-specific ID in another source must not override this hotel.
    cross = pd.concat([cross, pd.DataFrame([{
        "source": "other", "source_entity_id": "h1", "canonical_id": "WRONG"}])])
    out = build_index.enrich_documents(documents.iloc[::-1], cross, links)
    assert out.entity_id.tolist() == documents.entity_id.tolist()[::-1]
    assert len(out) == len(documents)
    ids = out.set_index("entity_id").canonical_id
    assert ids[["h1", "p1", "e1", "r1"]].tolist() == ["C_H", "C_P", "C_E", "C_P"]
    assert ids[["r2", "p4", "ev1"]].isna().all()


@pytest.mark.parametrize("duplicate", ["crosswalk", "reviews"])
def test_duplicate_mapping_keys_rejected(documents, mappings, duplicate):
    cross, links = mappings
    if duplicate == "crosswalk":
        cross = pd.concat([cross, cross.iloc[:1]])
    else:
        links = pd.concat([links, links.iloc[:1]])
    with pytest.raises(pd.errors.MergeError):
        build_index.enrich_documents(documents, cross, links)


@pytest.fixture
def built_index(tmp_path, monkeypatch, documents, mappings):
    docs_path = tmp_path / "kb_documents.csv"
    documents.to_csv(docs_path, index=False)
    cross, links = mappings
    cross.to_csv(tmp_path / "entity_crosswalk.csv", index=False)
    links.to_csv(tmp_path / "review_place_links.csv", index=False)
    monkeypatch.setattr(build_index, "DOCS", docs_path)
    monkeypatch.setattr(build_index, "STD", tmp_path)
    monkeypatch.setattr(build_index, "OUT", tmp_path / "index")
    build_index.build("stub")
    monkeypatch.setattr(search, "STORE", build_index.OUT)
    search._load.cache_clear()
    yield build_index.OUT
    search._load.cache_clear()


def test_canonical_ids_survive_build_and_search(built_index):
    meta = pd.read_csv(built_index / "vector_meta.csv")
    vectors = np.load(built_index / "vectors.npy")
    assert len(meta) == len(vectors) == 9
    assert meta.entity_id.tolist() == ["h1", "p1", "e1", "r1", "r2", "p2", "p3", "ev1", "p4"]
    for result in [
        search.semantic_search("heritage", top_k=20),
        search.hybrid_search("heritage", city="Riyadh", entity_type="review", top_k=20),
    ]:
        ids = result.set_index("entity_id").canonical_id
        assert ids["r1"] == "C_P"
        assert pd.isna(ids["r2"])
    assert search.semantic_search("heritage").set_index("entity_id").canonical_id["h1"] == "C_H"


def test_filters_and_empty_results(built_index):
    result = search.hybrid_search(
        "heritage", city="Riyadh", region="Riyadh",
        entity_type=["place", "hotel"], max_price=250, min_rating=.8, top_k=20)
    assert set(result.entity_id) == {"h1", "p1"}
    assert search.hybrid_search("heritage", city="Nowhere").empty
    assert search.semantic_search("heritage", top_k=0).empty


def test_legacy_index_requests_rebuild(built_index, monkeypatch):
    meta = pd.read_csv(built_index / "vector_meta.csv").drop(columns="canonical_id")
    meta.to_csv(built_index / "vector_meta.csv", index=False)
    search._load.cache_clear()
    def no_model(*args):
        pytest.fail("Legacy validation must precede model loading")
    monkeypatch.setattr(search, "get_embedder", no_model)
    with pytest.raises(ValueError, match="python -m src.vector_store.build_index"):
        search.semantic_search("heritage")


def test_search_with_monkeypatched_loader(documents, mappings, monkeypatch):
    meta = build_index.enrich_documents(documents, *mappings)
    embedder = StubEmbedder()
    vectors = embedder.encode(meta.text.tolist())
    monkeypatch.setattr(search, "_load", lambda: ({}, vectors, meta, embedder))
    result = search.hybrid_search("museum", entity_type="place", max_price=60, min_rating=.8)
    assert result.entity_id.tolist() == ["p1"]
    assert result.canonical_id.tolist() == ["C_P"]


@pytest.mark.parametrize("scores,expected", [
    ([("A", 1.0), ("B", 1.0)], None),
    ([("A", 1.0), ("A", 1.0)], "A"),
    ([("A", .849)], None),
    ([("A", .85)], "A"),
    ([("A", .9), ("B", .85)], "A"),
    ([("A", .9), ("B", .850001)], None),
    ([], None),
])
def test_review_thresholds_and_canonical_grouping(monkeypatch, scores, expected):
    monkeypatch.setattr(resolve, "name_sim", lambda target, score: score)
    cid, _ = resolve.select_review_match("venue", "Riyadh", scores)
    assert cid == expected


@pytest.mark.parametrize("city", [None, np.nan, pd.NA, "", "  "])
def test_missing_city_review_stays_unresolved(city):
    assert resolve.select_review_match("venue", city, [("A", ("venue", ""))]) == (None, None)


def test_same_name_branches_remain_unresolved():
    norm = resolve.split_name("Starbucks")
    assert resolve.select_review_match("Starbucks", "Riyadh", [("A", norm), ("B", norm)]) == (None, 1.0)


@pytest.fixture
def database_inputs(tmp_path, monkeypatch):
    frames = {
        "hotels": pd.DataFrame([dict(hotel_id="h1", city="Riyadh", price_sar=200, guest_rating=9)]),
        "places": pd.DataFrame([dict(place_id="p1", city="Riyadh", is_restaurant=1, average_rating=4.8)]),
        "reviews": pd.DataFrame([dict(review_id="r1", place_name_raw="Museum", city="Riyadh",
                                     review_text="Good", sent_overall=1, sent_cleanliness=1, sent_service=1)]),
        "canonical_entities": pd.DataFrame([dict(canonical_id="C_P", name="Museum", city="Riyadh",
                                                region="Riyadh", latitude=24.7, longitude=46.7, n_members=1)]),
        "entity_crosswalk": pd.DataFrame([
            dict(canonical_id="C_P", entity_type="place", source="riyadh_places_kaggle", source_entity_id="p1"),
            dict(canonical_id="C_H", entity_type="hotel", source="booking_kaggle", source_entity_id="h1")]),
        "review_place_links": pd.DataFrame([dict(review_id="r1", canonical_id="C_P", name_sim=1)]),
    }
    tables = {}
    keys = {"hotels": "hotel_id", "places": "place_id", "reviews": "review_id",
            "canonical_entities": "canonical_id", "review_place_links": "review_id"}
    for table, frame in frames.items():
        path = tmp_path / f"{table}.csv"
        frame.to_csv(path, index=False)
        tables[table] = (path, keys.get(table))
    tables["events"] = (tmp_path / "absent_events.csv", "event_id")
    destination = tmp_path / "knowledge_base.sqlite"
    with contextlib.closing(sqlite3.connect(destination)) as con:
        con.execute("CREATE TABLE previous (value TEXT)")
        con.execute("INSERT INTO previous VALUES ('working')")
        con.commit()
    monkeypatch.setattr(build_sqlite, "TABLES", tables)
    monkeypatch.setattr(build_sqlite, "DB_PATH", destination)
    return destination, tables


def test_database_success_replaces_after_close(database_inputs):
    destination, _ = database_inputs
    build_sqlite.build()
    with contextlib.closing(sqlite3.connect(destination)) as con:
        assert con.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view'")} == set(build_sqlite.VIEWS)
        assert con.execute("SELECT canonical_id FROM v_reviews_resolved").fetchone()[0] == "C_P"
        assert con.execute("SELECT canonical_id FROM v_hotels").fetchone()[0] == "C_H"
        assert not con.execute("SELECT name FROM sqlite_master WHERE name='previous'").fetchall()
    assert not list(destination.parent.glob("kb-*.sqlite"))


@pytest.mark.parametrize("failure", ["missing", "query", "view", "integrity", "replace"])
def test_failed_database_build_preserves_previous(database_inputs, monkeypatch, failure):
    destination, tables = database_inputs
    before = destination.read_bytes()
    if failure == "missing":
        tables["reviews"][0].unlink()
    elif failure == "query":
        path = tables["hotels"][0]
        pd.read_csv(path).drop(columns="price_sar").to_csv(path, index=False)
    elif failure == "view":
        monkeypatch.setattr(build_sqlite, "VIEWS", {
            **build_sqlite.VIEWS,
            "v_hotels": "CREATE VIEW v_hotels AS SELECT absent_column FROM hotels"})
    elif failure == "integrity":
        real_connect = sqlite3.connect
        class BadIntegrity(sqlite3.Connection):
            def execute(self, sql, *args):
                if sql == "PRAGMA integrity_check":
                    class Result:
                        def fetchall(self):
                            return [("corrupt",)]
                    return Result()
                return super().execute(sql, *args)
        monkeypatch.setattr(build_sqlite.sqlite3, "connect",
                            lambda *a, **kw: real_connect(*a, factory=BadIntegrity, **kw))
    else:
        def denied(*args):
            raise PermissionError("Destination locked")
        monkeypatch.setattr(build_sqlite.os, "replace", denied)
    with pytest.raises((FileNotFoundError, sqlite3.Error, RuntimeError, PermissionError)):
        build_sqlite.build()
    assert destination.read_bytes() == before
    assert not list(destination.parent.glob("kb-*.sqlite"))

def test_all_review_mappings_unresolved(documents, mappings):
    cross, links = mappings
    links = links.assign(canonical_id=np.nan)
    out = build_index.enrich_documents(documents, cross, links)
    assert out.loc[out.entity_type.eq("review"), "canonical_id"].isna().all()
    assert out.set_index("entity_id").canonical_id["p1"] == "C_P"
