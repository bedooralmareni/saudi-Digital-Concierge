# Entertainment — Findings Summary (Source 7: Entertainment in Saudi Arabia, Kaggle)

**File:** `data/raw/entertainment/Entertainment_KSA.csv`
**Exploration:** `notebooks/07_data_exploration_entertainment.ipynb`

## Overview
- **564 rows × 7 columns**: `Unnamed: 0` (redundant index), `name` (bilingual
  Arabic | English), `rating`, `review_count`, `genre`, `location`, `best_comment`.
- **No exact duplicate rows**; 271 unique names (chains repeat legitimately —
  Muvi 22, Sparky's, VOX, …).
- This is a scraped, Google-Maps-style dataset and the **messiest tabular source**.

## Signal (concierge-useful)
- Ratings range **2.5–5.0, mean ≈ 4.21**.
- Top genres: **Tourist attraction 132 · Movie theater 128 · Amusement center 57 ·
  Park 23 · Children's amusement center 21**.
- City concentration: **Riyadh ≈ 52%** (292), Jeddah 37, Dammam 15, Al Khobar 14,
  Buraydah/Hail 8 each.

## Data-quality issues (for `src/cleaning`)
1. **Column misalignment (~24 rows)** — the biggest problem. `rating` holds text
   (`"No reviews · …"`, `"Saudi Arabia"`), `review_count` holds a city, `genre` holds a
   price symbol (`₹`). Caused by unquoted commas in the source scrape. Detect via
   "rating not numeric", then re-parse from `location`/`best_comment` or drop.
2. **`rating` is text** → cast to float (~24 non-numeric = misaligned or "No reviews").
3. **`review_count` is parenthesised** with `K`/`T`/`M` suffixes (`T` = thousand, e.g.
   `(1.1T)` → 1,100) → parse to integer (range ~1–36,000).
4. **Non-Saudi rows** — ~14 venues in Bahrain/Kuwait despite the "KSA" name → filter to
   `country == "Saudi Arabia"`.
5. **`genre` needs trimming** (leading spaces) and removal of contaminated values
   (price symbols, `In <place>` location leaks).
6. **`location` is free text** → extract a canonical city (Riyadh dominates) and map to
   the city/province key used by the other sources.
7. **`best_comment` ~39% missing** — keep as optional enrichment, not a key field.
8. **Name inconsistency** — same venue sometimes with/without the Arabic half; normalise
   before any name-based dedup.

## Missing values
`best_comment` 222 (39%) · `location` 25 (4.4%) · `genre` 23 (4.1%) ·
`name` 5 · `review_count` 2.

## Concierge relevance
High — real venues with ratings, categories and cities directly answer "fun things to do
in \<city\>" and complement the events source. Needs the most cleaning of the tabular
sources.

## Next steps
1. Fix column misalignment, then parse `rating` and `review_count` to numeric.
2. Filter to Saudi venues; extract and map canonical city names.
3. Write a tidy `entertainment` table to `data/processed/`.
4. Embed name + genre + city + rating (+ best_comment) into the vector store.
