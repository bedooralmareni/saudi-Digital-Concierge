# Data Dictionary & Data Contract

This document defines the **target schema** every dataset must conform to *after*
cleaning — the contract the cleaning stage (`src/cleaning` → `data/processed/`) must
produce and the retrieval/agent layers can rely on. It is decided **before** cleaning so
cleaning has a fixed target.

- **Raw** (`data/raw/`) — untouched source files. Not covered here (see each source's
  `FINDINGS.md` and the audit notebooks in `notebooks/02_data_quality_audit/`).
- **Processed** (`data/processed/`) — one tidy table per entity, conforming to the
  contracts below.
- **Final** (`data/final/`) — the retrieval knowledge base: documents (§12) and the
  embeddings / vector-store artefacts built from them.

Entities (the knowledge base):

```
places · reviews · hotels · events · entertainment · tourism_statistics · tourism_indicators
```

> **`restaurants` is not a separate entity** — it is a derived view of `places` where
> `is_restaurant = true` (§4). "One file per entity" therefore applies to the seven
> entities above; `restaurants` is materialized only if the retrieval layer needs a
> dedicated collection.

---

## 1. Global conventions

These apply to **every** processed table.

### 1.1 File format & naming
- One file per entity: `data/processed/<entity>.parquet` (Parquet preferred for typed
  columns; a `.csv` mirror may be written for inspection).
- Column names: `snake_case`, ASCII, lower-case.
- One row = one entity instance (one place, one hotel, one event, …).

### 1.2 Identifiers
- Every table has a primary key **`<entity>_id`** (string), globally unique and stable.
- Format: `<source>_<n>` — e.g. `places_00042`, `hotels_00517`, `events_01890`.
- Where the source has its own stable id (hotels `Property_id`, places `id`) keep it in
  **`source_id`** and derive `<entity>_id` from it.
- Where the source has **no** stable id (events), generate a **deterministic hash** of
  normalized identifying fields (see §6) so the id is reproducible across re-pulls.

### 1.3 Text & language
- Encoding UTF-8. Arabic text normalized: Unicode **NFKC**, tatweel + diacritics removed,
  whitespace collapsed.
- Bilingual names use three columns where available: **`name`** (display, original),
  **`name_ar`**, **`name_en`**. If only one language exists, fill `name` and leave the
  other null.

### 1.4 Geography (controlled vocabulary)
- **`region`** — one of the 13 official administrative regions, canonical English spelling:
  `Riyadh, Makkah, Madinah, Eastern Province, Asir, Tabuk, Hail, Northern Borders, Jazan,
  Najran, Al Bahah, Al Jawf, Qassim`.
- **`city`** — canonical city name (English), title-case; mapped from the source's raw
  city/neighbourhood text via `src/cleaning` city-mapping. Neighbourhoods collapse to
  their city (`Ajyad, Makkah` → `Makkah`).
- **`latitude`, `longitude`** — WGS84 decimal degrees (float).
- **Saudi membership is decided by country/region/city mapping, not by coordinates.**
  The Saudi bounding box (**lat 16.0–32.5, lon 34.5–56.0**) is only a *coordinate-validity*
  check (a point outside it is invalid → set to null); it does **not** prove a row is in
  Saudi Arabia (the box overlaps neighbouring countries). A row is admitted as Saudi only
  when its `country`/`region`/`city` mapping confirms it (for Riyadh Places, `city = Riyadh`
  suffices; for Entertainment, apply the Saudi/non-Saudi location filter). Non-Saudi rows
  are dropped.

### 1.5 Dates, times, numbers, booleans
- Dates: **ISO 8601** `YYYY-MM-DD` (string or `date`). Datetimes: `YYYY-MM-DDTHH:MM:SSZ`
  (UTC). Times: `HH:MM` 24-hour.
- Money: numeric **SAR** in a `*_sar` column; no currency symbols, no thousands separators.
- Booleans: **three-state** — real `true` / `false` / `null`. `null` means *unknown*, and
  must never be collapsed to `false`. Never store `"True"`/`"None"` strings.
- Ratings/scores keep their native scale but are documented per entity (0–5 stars, 0–10
  guest score, −1/0/1 sentiment). Note: −1/0/1 is **sentiment**, not a rating.

### 1.6 Provenance (every table)
| Column | Type | Description |
| ------ | ---- | ----------- |
| `source` | string | Source key: `reviews_zenodo`, `riyadh_places_kaggle`, `tourism_kaggle`, `datasaudi`, `enjoy_sa`, `booking_kaggle`, `entertainment_kaggle` |
| `source_id` | string | The record's id in the source (if any) |
| `source_url` | string | Traceable URL: Zenodo DOI/record, Kaggle dataset URL, Enjoy.sa endpoint, per-row `booking_url` where available |
| `data_period` | string | What period the data *represents* (e.g. `2020`, `2015-2024`, `2024-Q3`) |
| `snapshot_date` | date | Exact date the snapshot corresponds to, when known (e.g. Booking `2020-04-24`); else null |
| `retrieved_at` | datetime | When we fetched/downloaded the data (UTC) — critical for the live API |
| `is_live` | boolean | `true` only for Enjoy.sa events; `false` for static snapshots |

> Provenance is required for **evidence-grounded generation and hallucination
> evaluation**: any claim in an itinerary must be traceable back to a `source` +
> `source_url` + `source_id`.

### 1.7 Nullability & validation
- **Required** columns must be non-null for the row to be admitted; rows failing required
  checks are quarantined (logged), not silently kept.
- Each contract lists constraints; the cleaning stage should assert them (see §10).

---

## 2. `places` — POIs & restaurants
**Source:** Riyadh Places 8.8K (`riyadh_places_kaggle`). Restaurants are `places` rows
with `is_restaurant = true` (see the `restaurants` view, §4).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `place_id` | string | ✅ | unique, `places_*` | Primary key |
| `source_id` | string | ✅ | | Source `id` |
| `name` | string | ✅ | | Place name |
| `is_restaurant` | boolean | ✅ | | True if a restaurant |
| `categories` | list<string> | | | Multi-value; split from `A|B|C` |
| `granular_category` | string | | | Single coarse category |
| `average_rating` | float | | 0–5, null if unrated | Star/user rating (0 → null) |
| `rate_count` | int | | ≥ 0 | Number of ratings |
| `city` | string | ✅ | = `Riyadh` | Canonical city |
| `region` | string | ✅ | = `Riyadh` | Region |
| `latitude` | float | ✅ | valid + in bbox | WGS84 |
| `longitude` | float | ✅ | valid + in bbox | WGS84 |

---

## 3. `reviews` — Arabic reviews + aspect sentiment
**Source:** Saudi Tourism Reviews (`reviews_zenodo`, CC0).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `review_id` | string | ✅ | unique | Primary key |
| `place_name_raw` | string | ✅ | | Reviewed place, as spelled in the source |
| `place_id` | string | | nullable FK → `places.place_id` | Resolved by entity matching (Phase 6), **not** cleaning; often null (reviews span cities beyond Riyadh) |
| `review_text` | string | ✅ | | Normalized Arabic review text |
| `city` | string | | canonical | Mapped from `المدينة` |
| `category` | string | | park/garden/heritage/museum | From `الفئة` |
| `sent_price` | int | | −1 / 0 / 1 / null | Price sentiment |
| `sent_cleanliness` | int | | −1 / 0 / 1 / null | Cleanliness |
| `sent_facilities` | int | | −1 / 0 / 1 / null | Facilities |
| `sent_service` | int | | −1 / 0 / 1 / null | Service & staff |
| `sent_environment` | int | | −1 / 0 / 1 / null | Ambiance (fix the 1 non-numeric value) |
| `sent_overall` | int | | −1 / 0 / 1 / null | Overall experience |

> Aspect scores are sparse by design (only scored when mentioned). Missing = aspect not
> discussed, encoded as **null** (not 0). `place_id` links Review → Place but is
> best-effort: it is populated by fuzzy `place_name_raw` + `city` matching during entity
> resolution, and stays null where no confident match exists.

---

## 4. `restaurants` — derived view of places
Not a separate source or file by default: **`restaurants` = `places` where
`is_restaurant = true`**, same schema as §2. Materialized to its own file only if the
retrieval layer needs a dedicated collection.

---

## 5. `hotels` — accommodation
**Source:** Booking.com (`booking_kaggle`, **2020 snapshot**, `is_live = false`).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `hotel_id` | string | ✅ | unique, `hotels_*` | Primary key |
| `source_id` | string | ✅ | | `Property_id` |
| `name` | string | ✅ | | Property name |
| `city` | string | ✅ | canonical | Base city (from `Ajyad, Makkah` → `Makkah`) |
| `region` | string | ✅ | one of 13 | Region |
| `price_sar` | float | ✅ | > 0 | Nightly price (2020) |
| `star_rating` | int | | 1–5, **null if unrated** | Official class (`0` → null) |
| `guest_rating` | float | | 0–10 | `Customers_Rating` |
| `guest_rating_count` | int | | ≥ 0 | Parsed from `Customers_Review` |
| `room_type` | string | | | `Type_of_room` |
| `bed_type` | string | | | |
| `max_persons` | int | | ≥ 1 | Parsed from `Max persons: N` |
| `breakfast_included` | boolean | | true / false / **null** | `null` = unknown (missing → null, **not** false) |
| `free_cancellation` | boolean | | true / false / **null** | From `Canelation`; missing → null |
| `latitude` | float | ✅ | valid + in bbox | `Latitude_y` |
| `longitude` | float | ✅ | valid + in bbox | `Longitude_x` |
| `source_url` | string | | | `booking_url` (also excluded from embeddings) |

> Missing information ≠ negative fact. `breakfast_included = null` and
> `free_cancellation = null` mean *the dataset does not say* — the Verifier must not
> conclude "breakfast not included" from a null.

---

## 6. `events` — events & schedules
**Source:** Enjoy.sa API (`enjoy_sa`, **live**, `is_live = true`).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `event_id` | string | ✅ | unique, deterministic | Hash-derived key (no native id) |
| `name` | string | ✅ | | Event name |
| `city` | string | ✅ | canonical | Mapped from Arabic `City` |
| `region` | string | | one of 13 | Region |
| `start_date` | date | ✅ | ISO, ≤ `end_date` | From `StartDateFormatted` (parse `dayfirst=True`) |
| `end_date` | date | ✅ | ISO | From `EndDateFormatted` (parse `dayfirst=True`) |
| `start_time` | string | | `HH:MM` | |
| `end_time` | string | | `HH:MM` | |
| `is_male_allowed` | boolean | | true/false/null | |
| `is_female_allowed` | boolean | | true/false/null | |
| `is_family_allowed` | boolean | | true/false/null | |
| `is_active` | boolean | ✅ | | From `EventMode` (`IsActive`/`IsExpired`) |

> **ID generation ≠ duplicate detection.**
> `event_id = hash(normalized_name + canonical_city + start_date + start_time + end_date)`
> — a deterministic, reproducible id computed on *normalized* inputs.
> Duplicate detection is a **separate** cleaning step (two genuinely different instances
> could share those fields); flag and review duplicates rather than assuming the id
> collision means the same event.

---

## 7. `entertainment` — entertainment venues
**Source:** Entertainment in Saudi Arabia (`entertainment_kaggle`). Drop the ~24
column-misaligned rows and the ~14 non-Saudi venues during cleaning.

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `entertainment_id` | string | ✅ | unique | Primary key |
| `name` | string | ✅ | | Venue name (bilingual) |
| `genre` | string | | trimmed, no `₹`/leaks | Category |
| `rating` | float | | 0–5, null if none | Parsed numeric rating |
| `review_count` | int | | ≥ 0 | Parsed from `(1.1T)` → 1100 |
| `city` | string | ✅ | canonical | From `location` |
| `region` | string | | one of 13 | |
| `country` | string | ✅ | = `Saudi Arabia` | Non-Saudi rows dropped (country/city confirms membership) |
| `best_comment` | string | | | Optional review snippet |

---

## 8. `tourism_statistics` — demand/spending by region-year
**Source:** Saudi Tourism 2015–2024 (`tourism_kaggle`). Resolve the non-unique
granularity: **one row per (year, region, tourism_type)**.

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `year` | int | ✅ | 2015–2024 | |
| `region` | string | ✅ | one of 13 | Mapped from `Province` |
| `tourism_type` | string | ✅ | Domestic / Inbound | |
| `tourists_thousands` | float | | ≥ 0 | |
| `overnight_stays_thousands` | float | | ≥ 0 | |
| `spending_million_sar` | float | | ≥ 0 | |
| `avg_stay_nights` | float | | ≥ 0 | Recompute from totals, not averaged |
| `avg_spend_per_trip_sar` | float | | ≥ 0 | |
| `avg_spend_per_night_sar` | float | | ≥ 0 | |

> **Primary key:** (`year`, `region`, `tourism_type`). ~28 exact duplicates dropped.
> **Zeros are retained as valid values by default**; a zero is converted to null **only
> where the source documentation or data semantics confirm** it encodes missing /
> not-applicable data — the pipeline must not silently overwrite legitimate zeros.

---

## 9. `tourism_indicators` — official DataSaudi indicators (curated)
**Source:** DataSaudi (`datasaudi`, official). Keep the curated ~5 tables (purpose of
visit, spending by purpose, NPS, satisfaction, complementary indicators); drop
Source-3-duplicating and heavy monthly-occupancy tables. Long format:

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `indicator` | string | ✅ | | Indicator name (e.g. `net_promoter_score`) |
| `period` | string | ✅ | year or `YYYY-Qn` | Time period |
| `dimension` | string | | | e.g. trip purpose / tourist type (nullable) |
| `dimension_value` | string | | | e.g. `Religious`, `Inbound` |
| `value` | float | ✅ | | Indicator value |
| `unit` | string | ✅ | ratio / index / sar_million / count | Unit of `value` |

> Drop constant `Economic Sectors` and `*_ID` columns; exclude `Grand Total` rollup rows.

---

## 10. Cross-entity keys & validation

**Join key across entities:** `region` (13-value controlled vocab) and `city`
(canonical). All city/region values must resolve through the single mapping table in
`src/cleaning` — this is the contract that lets the agents cross-reference places,
hotels, events, entertainment and statistics. `reviews.place_id` is the one *soft* link,
resolved by entity matching and allowed to be null.

**Contract checks the cleaning stage must assert (fail → quarantine row):**
1. Primary key present and unique.
2. Required columns non-null.
3. `region` ∈ the 13-value vocabulary; `city` non-empty and mapped.
4. Saudi membership confirmed by country/region/city mapping; `latitude`/`longitude`
   coordinate-valid (inside the bbox) or null — bbox is validity only, not proof of Saudi.
5. Dates ISO and `start_date ≤ end_date` (events).
6. Numeric ranges: ratings within scale, prices/counts ≥ 0, sentiment ∈ {−1,0,1,null}.
7. Booleans are real three-state booleans; unknown = null (never false).
8. Zeros retained unless semantics confirm they mean missing.

---

## 11. Snapshot & currency summary

| Entity | Source | Data period | Snapshot date | Live? |
| ------ | ------ | ----------- | ------------- | ----- |
| places | Kaggle | static | — | No |
| reviews | Zenodo (CC0) | static | — | No |
| hotels | Kaggle (Booking) | **2020** | 2020-04-24 | No |
| events | Enjoy.sa API | retrieval date | = `retrieved_at` | **Yes** |
| entertainment | Kaggle | static | — | No |
| tourism_statistics | Kaggle | 2015–2024 | — | No |
| tourism_indicators | DataSaudi | 2015–2025 | — | Depends |

> Only `events` is live. Surface hotel prices as **2020-era**; treat statistics as
> historical context.

---

## 12. Knowledge base / retrieval documents (`data/final/`)

After the processed tables are built, each entity record is turned into one or more
**retrieval documents** that are embedded into the vector store. This document schema is
what preserves the **claim → evidence** trace for grounding and hallucination evaluation.

| Column | Type | Required | Description |
| ------ | ---- | :---: | ----------- |
| `document_id` | string | ✅ | Unique document id |
| `chunk_id` | string | | Set when a record's text is split; chunks share the parent `document_id` |
| `entity_type` | string | ✅ | `place` / `review` / `hotel` / `event` / `entertainment` / `tourism_statistics` / `tourism_indicators` |
| `entity_id` | string | ✅ | FK back to the processed record (e.g. `hotels_00517`) |
| `text` | string | ✅ | The embedded natural-language text (name + key attributes / review) |
| `language` | string | ✅ | `ar` / `en` / `mixed` |
| `city` | string | | Canonical city (retrieval filter) |
| `region` | string | | Region (retrieval filter) |
| `category` | string | | Entity category/genre where applicable (retrieval filter) |
| `source` | string | ✅ | Provenance (carried from the record) |
| `source_id` | string | | Provenance |
| `source_url` | string | | Provenance — the traceable link |
| `data_period` | string | | Carried from the record |
| `snapshot_date` | date | | Carried from the record |
| `retrieved_at` | datetime | | Carried from the record |
| `is_live` | boolean | | Carried from the record |

**Traceability chain:**

```
retrieved chunk
   → document_id (+ chunk_id)
   → entity_id
   → processed record (structured fields)
   → source / source_id / source_url   ← evidence
```

Every generated claim must resolve down this chain to a `source_url`, which is what the
Verifier and the Evidence-Grounding / Hallucination-Rate metrics check against.
