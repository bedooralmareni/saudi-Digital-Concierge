"""Entity resolution — link the same real-world place across datasets.

The same place appears in different sources with slightly different names
("Kingdom Centre" / "Kingdom Center" / "برج المملكة"). This assigns a **canonical id**
(region-prefixed, e.g. `RYD_000123`) so reviews, coordinates and ratings can refer to the
same entity — while **retaining every source-specific identifier** in a crosswalk.

Matching NEVER relies on name alone. A pair is merged only when it is in the **same city**,
of a **compatible type**, and passes a rule combining:
  - name similarity (bilingual: English and Arabic parts scored separately)
  - coordinate distance (when both have coordinates)
  - category / type compatibility

Type compatibility:
  - place  ↔ place / entertainment   (POIs & attractions may be the same venue)
  - entertainment ↔ entertainment
  - hotel  ↔ hotel only              (accommodation is a separate domain)

Merge rules (city equal + type compatible, applied conservatively):
  - name_sim ≥ 0.90                                        -> merge
  - name_sim ≥ 0.80 AND coord distance ≤ 150 m            -> merge
  - coord distance ≤ 30 m AND name_sim ≥ 0.50             -> merge (very close + plausible)
  - otherwise                                              -> do NOT merge

Outputs (data/processed/standardized/):
  - entity_crosswalk.csv   one row per source record: canonical_id + its source id
  - canonical_entities.csv one row per canonical entity (merged best attributes)
  - review_place_links.csv reviews linked to a canonical place by name+city (nullable)

Run:  python -m src.entity_resolution.resolve
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

import sys as _sys, pathlib as _pathlib
if __package__ in (None, ""):
    _sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from src.cleaning.common import PROCESSED
from src.cleaning.geo import normalize_ar

OUT = PROCESSED / "standardized"

REGION_CODE = {
    "Riyadh": "RYD", "Makkah": "MAK", "Madinah": "MED", "Eastern Province": "EAS",
    "Asir": "ASR", "Tabuk": "TBK", "Hail": "HAL", "Northern Borders": "NBS",
    "Jazan": "JAZ", "Najran": "NJR", "Al Bahah": "BAH", "Al Jawf": "JWF", "Qassim": "QSM",
}
_EN_STOP = {"the", "of", "and", "a", "al"}

# Which types may merge with which.
_COMPAT = {"place": {"place", "entertainment"}, "entertainment": {"place", "entertainment"},
           "hotel": {"hotel"}}


# ── name normalization (bilingual) ─────────────────────────────────────────────
def split_name(name):
    """Return (english_tokens_str, arabic_norm_str) from a possibly bilingual name."""
    s = str(name) if name is not None and not (isinstance(name, float) and math.isnan(name)) else ""
    en = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    en_tokens = [t for t in en.split() if t not in _EN_STOP]
    en_str = " ".join(sorted(en_tokens))
    ar = normalize_ar(s)
    ar = re.sub(r"[^؀-ۿ ]", " ", ar)
    ar_str = " ".join(sorted(t for t in ar.split() if t))
    return en_str, ar_str


def name_sim(a, b):
    """Max of English- and Arabic-part similarity (0-1); 0 if no shared script."""
    sims = []
    if a[0] and b[0]:
        sims.append(SequenceMatcher(None, a[0], b[0]).ratio())
    if a[1] and b[1]:
        sims.append(SequenceMatcher(None, a[1], b[1]).ratio())
    return max(sims) if sims else 0.0


def haversine_m(lat1, lon1, lat2, lon2):
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (lat1, lon1, lat2, lon2)):
        return None
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ── union-find ─────────────────────────────────────────────────────────────────
class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _load_nodes():
    """Unified list of point entities from places, entertainment, hotels."""
    nodes = []

    p = pd.read_csv(PROCESSED / "places" / "places_clean.csv")
    for _, r in p.iterrows():
        nodes.append(dict(src="riyadh_places_kaggle", sid=r["place_id"], etype="place",
                          name=r["name"], category=r.get("granular_category"),
                          city=r["city"], region=r["region"],
                          lat=r.get("latitude"), lon=r.get("longitude")))

    e = pd.read_csv(PROCESSED / "entertainment" / "entertainment_clean.csv")
    for _, r in e.iterrows():
        nodes.append(dict(src="entertainment_kaggle", sid=r["entertainment_id"], etype="entertainment",
                          name=r["name"], category=r.get("genre"),
                          city=r["city"], region=r.get("region"), lat=np.nan, lon=np.nan))

    h = pd.read_csv(PROCESSED / "hotels" / "hotels_clean.csv")
    for _, r in h.iterrows():
        nodes.append(dict(src="booking_kaggle", sid=r["hotel_id"], etype="hotel",
                          name=r["name"], category="hotel",
                          city=r["city"], region=r.get("region"),
                          lat=r.get("latitude"), lon=r.get("longitude")))

    for nd in nodes:
        nd["norm"] = split_name(nd["name"])
        nd["lat"] = float(nd["lat"]) if pd.notna(nd["lat"]) else None
        nd["lon"] = float(nd["lon"]) if pd.notna(nd["lon"]) else None
    return nodes


def _candidate_pairs(nodes):
    """Blocking: group by city + (name-prefix | coordinate cell); yield in-block pairs."""
    buckets = {}
    for i, nd in enumerate(nodes):
        city = nd["city"] or "?"
        keys = set()
        en, ar = nd["norm"]
        if en:
            longest = max(en.split(), key=len)
            keys.add(("en", city, longest[:4]))
        if ar:
            keys.add(("ar", city, ar.replace(" ", "")[:4]))
        if nd["lat"] is not None and nd["lon"] is not None:
            keys.add(("geo", city, round(nd["lat"], 3), round(nd["lon"], 3)))
        for k in keys:
            buckets.setdefault(k, []).append(i)

    seen = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 400:   # skip huge/degenerate blocks
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                pair = (members[a], members[b])
                if pair not in seen:
                    seen.add(pair)
                    yield pair


def _should_merge(x, y):
    """Hard-merge decision. Conservative: coordinates MUST corroborate.

    Same-name records without coordinate proof (e.g. two chain branches, or a
    no-coordinate entertainment record) are NOT merged — they are emitted as candidate
    links instead (see `_is_candidate`).
    """
    if x["city"] != y["city"] or not x["city"]:
        return False, ""
    if y["etype"] not in _COMPAT.get(x["etype"], set()):
        return False, ""
    dist = haversine_m(x["lat"], x["lon"], y["lat"], y["lon"])
    if dist is None:
        return False, ""                       # no coordinates -> never hard-merge
    ns = name_sim(x["norm"], y["norm"])
    if dist <= 20 and ns >= 0.60:
        return True, f"dist={dist:.0f}m,name={ns:.2f}"
    if dist <= 50 and ns >= 0.85:
        return True, f"name={ns:.2f},dist={dist:.0f}m"
    return False, ""


def _is_candidate(x, y):
    """A strong name match across sources that we DON'T auto-merge (needs coords/review)."""
    if x["city"] != y["city"] or not x["city"]:
        return None
    if y["etype"] not in _COMPAT.get(x["etype"], set()):
        return None
    if x["src"] == y["src"]:
        return None                            # candidates are for cross-source review
    if haversine_m(x["lat"], x["lon"], y["lat"], y["lon"]) is not None:
        return None                            # if both had coords, _should_merge handled it
    ns = name_sim(x["norm"], y["norm"])
    return ns if ns >= 0.90 else None


def _region_of(members, nodes):
    regs = [nodes[i]["region"] for i in members if nodes[i]["region"] in REGION_CODE]
    return max(set(regs), key=regs.count) if regs else None


def resolve():
    OUT.mkdir(parents=True, exist_ok=True)
    nodes = _load_nodes()
    n = len(nodes)
    uf = UF(n)

    merges = 0
    candidates = []
    for a, b in _candidate_pairs(nodes):
        ok, reason = _should_merge(nodes[a], nodes[b])
        if ok:
            uf.union(a, b)
            merges += 1
            continue
        cs = _is_candidate(nodes[a], nodes[b])
        if cs is not None:
            candidates.append((a, b, cs))

    # Group by cluster root, assign canonical ids (region-prefixed, stable ordering).
    clusters = {}
    for i in range(n):
        clusters.setdefault(uf.find(i), []).append(i)

    counters = {}
    root_to_cid = {}
    def _sort_key(r):
        reg = nodes[r]["region"]
        reg = reg if isinstance(reg, str) and reg in REGION_CODE else "zz"
        return (reg, str(nodes[r]["name"]))
    for root in sorted(clusters, key=_sort_key):
        members = clusters[root]
        reg = _region_of(members, nodes)
        code = REGION_CODE.get(reg, "SAU")
        counters[code] = counters.get(code, 0) + 1
        root_to_cid[root] = f"{code}_{counters[code]:06d}"

    # Crosswalk: one row per source record (retains source-specific ids).
    cross = pd.DataFrame([{
        "canonical_id": root_to_cid[uf.find(i)],
        "source": nd["src"], "source_entity_id": nd["sid"], "entity_type": nd["etype"],
        "name": nd["name"], "city": nd["city"], "region": nd["region"],
    } for i, nd in enumerate(nodes)]).sort_values(["canonical_id", "source"])
    cross.to_csv(OUT / "entity_crosswalk.csv", index=False)

    # Canonical entities: one row per canonical id (best attributes).
    rows = []
    for root, members in clusters.items():
        cid = root_to_cid[root]
        ms = [nodes[i] for i in members]
        primary = max(ms, key=lambda m: len(str(m["name"])))  # most complete name
        lats = [m["lat"] for m in ms if m["lat"] is not None]
        lons = [m["lon"] for m in ms if m["lon"] is not None]
        rows.append({
            "canonical_id": cid, "name": primary["name"],
            "entity_types": "|".join(sorted({m["etype"] for m in ms})),
            "city": primary["city"], "region": _region_of(members, nodes),
            "latitude": np.mean(lats) if lats else None,
            "longitude": np.mean(lons) if lons else None,
            "n_members": len(ms), "n_sources": len({m["src"] for m in ms}),
            "sources": "|".join(sorted({m["src"] for m in ms})),
            "member_ids": "|".join(m["sid"] for m in ms),
        })
    canon = pd.DataFrame(rows).sort_values("canonical_id")
    canon.to_csv(OUT / "canonical_entities.csv", index=False)

    # Candidate cross-source links (NOT merged — for review / future coordinate proof).
    cand_rows = []
    for a, b, cs in candidates:
        cand_rows.append({
            "canonical_id_a": root_to_cid[uf.find(a)], "source_a": nodes[a]["src"],
            "id_a": nodes[a]["sid"], "name_a": nodes[a]["name"],
            "canonical_id_b": root_to_cid[uf.find(b)], "source_b": nodes[b]["src"],
            "id_b": nodes[b]["sid"], "name_b": nodes[b]["name"],
            "city": nodes[a]["city"], "name_sim": round(cs, 3)})
    cand = pd.DataFrame(cand_rows).drop_duplicates()
    cand.to_csv(OUT / "candidate_links.csv", index=False)

    _link_reviews(nodes, uf, root_to_cid)

    multi = canon[canon["n_members"] > 1]
    print(f"nodes (place+entertainment+hotel): {n}")
    print(f"hard merges (coordinate-corroborated): {merges}")
    print(f"canonical entities: {len(canon)}  (clusters with >1 member: {len(multi)}, "
          f"max cluster size: {int(canon['n_members'].max())})")
    print(f"candidate cross-source links (not merged): {len(cand)}")
    print("saved -> entity_crosswalk.csv, canonical_entities.csv, candidate_links.csv, "
          "review_place_links.csv")
    return cross, canon


def _link_reviews(nodes, uf, root_to_cid):
    """Best-effort link reviews -> canonical place/attraction by name + city (nullable)."""
    rv = pd.read_csv(PROCESSED / "reviews" / "reviews_clean.csv")
    # index attraction nodes by city
    by_city = {}
    for i, nd in enumerate(nodes):
        if nd["etype"] in ("place", "entertainment"):
            by_city.setdefault(nd["city"], []).append(i)

    out = []
    for _, r in rv.iterrows():
        target = split_name(r["place_name_raw"])
        best_cid, best = None, 0.0
        for i in by_city.get(r.get("city"), []):
            s = name_sim(target, nodes[i]["norm"])
            if s > best:
                best, best_cid = s, root_to_cid[uf.find(i)]
        linked = best >= 0.85
        out.append({"review_id": r["review_id"], "place_name_raw": r["place_name_raw"],
                    "city": r.get("city"),
                    "canonical_id": best_cid if linked else None,
                    "name_sim": round(best, 3) if best_cid else None})
    links = pd.DataFrame(out)
    links.to_csv(OUT / "review_place_links.csv", index=False)
    print(f"reviews linked to a canonical place: {int(links['canonical_id'].notna().sum())} / {len(links)}")


if __name__ == "__main__":
    resolve()
