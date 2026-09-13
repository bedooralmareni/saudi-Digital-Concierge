# Data Dictionary & Data Contract

This document defines the **target schema** every dataset must conform to *after*
cleaning — the contract the cleaning stage (`src/cleaning` → `data/processed/`) must
produce and the retrieval/agent layers can rely on. It is decided **before** cleaning so
cleaning has a fixed target.

- **Raw** (`data/raw/`) — untouched source files. Not covered here (see each source's
  `FINDINGS.md` and the audit notebooks in `notebooks/02_data_quality_audit/`).
- **Processed** (`data/processed/`) — one tidy table per entity, conforming to the
  contracts below.
- **Final** (`data/final/`) — embeddings / vector-store artefacts built from processed.

Entities (the knowledge base):

```
places · reviews · restaurants · hotels · events · entertainment · tourism_statistics
```

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
- **`latitude`, `longitude`** — WGS84 decimal degrees (float). Must fall inside the Saudi
  bounding box **lat 16.0–32.5, lon 34.5–56.0** or be null. Non-Saudi rows are dropped.

### 1.5 Dates, times, numbers, booleans
- Dates: **ISO 8601** `YYYY-MM-DD` (string or `date`). Datetimes: `YYYY-MM-DDTHH:MM:SSZ`
  (UTC). Times: `HH:MM` 24-hour.
- Money: numeric **SAR** in a `*_sar` column; no currency symbols, no thousands separators.
- Booleans: real `true`/`false` (nullable); never `"True"`/`"None"` strings.
- Ratings keep their native scale but are documented per entity (0–5 stars, 0–10 guest,
  −1/0/1 sentiment).

### 1.6 Provenance (every table)
| Column | Type | Description |
| ------ | ---- | ----------- |
| `source` | string | Source key: `reviews_zenodo`, `riyadh_places_kaggle`, `tourism_kaggle`, `datasaudi`, `enjoy_sa`, `booking_kaggle`, `entertainment_kaggle` |
| `source_id` | string | The record's id in the source (if any) |
| `snapshot_date` | date | When the data represents / was retrieved (e.g. Booking = `2020`, Enjoy.sa = retrieval date) |
| `is_live` | boolean | `true` only for Enjoy.sa events; `false` for static snapshots |

### 1.7 Nullability & validation
- **Required** columns must be non-null for the row to be admitted; rows failing required
  checks are quarantined (logged), not silently kept.
- Each contract lists constraints; the cleaning stage should assert them (see §10).

---

## 2. `places` — POIs & restaurants
**Source:** Riyadh Places 8.8K (`riyadh_places_kaggle`). Restaurants are `places` rows
with `is_restaurant = true` (see also the `restaurants` view, §4).

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
| `latitude` | float | ✅ | in Saudi bbox | WGS84 |
| `longitude` | float | ✅ | in Saudi bbox | WGS84 |

---

## 3. `reviews` — Arabic reviews + aspect sentiment
**Source:** Saudi Tourism Reviews (`reviews_zenodo`, CC0).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `review_id` | string | ✅ | unique | Primary key |
| `place_name` | string | ✅ | | Reviewed place (raw name) |
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
> discussed, encoded as **null** (not 0).

---

## 4. `restaurants` — view over places
Not a separate source: **`restaurants` = `places` where `is_restaurant = true`**, same
schema as §2. Materialized separately only if the retrieval layer needs a dedicated
collection.

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
| `breakfast_included` | boolean | | | true / false (missing → false) |
| `free_cancellation` | boolean | | | From `Canelation` |
| `latitude` | float | ✅ | in Saudi bbox | `Latitude_y` |
| `longitude` | float | ✅ | in Saudi bbox | `Longitude_x` |
| `booking_url` | string | | | Source link (excluded from embeddings) |

---

## 6. `events` — events & schedules
**Source:** Enjoy.sa API (`enjoy_sa`, **live**, `is_live = true`).

| Column | Type | Required | Constraints | Description |
| ------ | ---- | :---: | ----------- | ----------- |
| `event_id` | string | ✅ | unique, `events_*` | Derived key (no native id) |
| `name` | string | ✅ | | Event name |
| `city` | string | ✅ | canonical | Mapped from Arabic `City` |
| `region` | string | | one of 13 | Region |
| `start_date` | date | ✅ | ISO, ≤ `end_date` | From `StartDateFormatted` (dayfirst) |
| `end_date` | date | ✅ | ISO | From `EndDateFormatted` (dayfirst) |
| `start_time` | string | | `HH:MM` | |
| `end_time` | string | | `HH:MM` | |
| `is_male_allowed` | boolean | | | |
| `is_female_allowed` | boolean | | | |
| `is_family_allowed` | boolean | | | |
| `is_active` | boolean | ✅ | | From `EventMode` (`IsActive`/`IsExpired`) |

> No native unique id → derive `event_id` from `name + city + start_date + start_time`,
> and dedupe on that key.

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
| `country` | string | ✅ | = `Saudi Arabia` | Non-Saudi rows dropped |
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

> **Primary key:** (`year`, `region`, `tourism_type`). Zeros that encode "no data"
> become null; ~28 exact duplicates dropped.

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
hotels, events, entertainment and statistics.

**Contract checks the cleaning stage must assert (fail → quarantine row):**
1. Primary key present and unique.
2. Required columns non-null.
3. `region` ∈ the 13-value vocabulary; `city` non-empty and mapped.
4. `latitude`/`longitude` inside the Saudi bbox or null.
5. Dates ISO and `start_date ≤ end_date` (events).
6. Numeric ranges: ratings within scale, prices/counts ≥ 0, sentiment ∈ {−1,0,1,null}.
7. Booleans are real booleans.
8. `country = Saudi Arabia` (entertainment) — non-Saudi dropped.

---

## 11. Snapshot & currency summary

| Entity | Source | Snapshot | Live? |
| ------ | ------ | -------- | ----- |
| places | Kaggle | static | No |
| reviews | Zenodo (CC0) | static | No |
| hotels | Kaggle (Booking) | **2020** | No |
| events | Enjoy.sa API | retrieval date | **Yes** |
| entertainment | Kaggle | static | No |
| tourism_statistics | Kaggle | 2015–2024 | No |
| tourism_indicators | DataSaudi | 2015–2025 | Depends |

> Only `events` is live. Surface hotel prices as **2020-era**; treat statistics as
> historical context.
