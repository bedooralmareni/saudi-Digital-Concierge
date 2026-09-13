# Processed data

Cleaned, contract-conforming tables produced by `src/cleaning/` from `data/raw/`
(**raw is never modified**). Run everything with:

```bash
python -m src.cleaning.run_all        # all datasets
python -m src.cleaning.clean_events   # events only, where enjoy.sa is reachable
```

Pipeline per dataset: **raw → clean → validate → save**. Each cleaner asserts the data
contract (`docs/data_dictionary.md`) and prints a report. Cleaning decisions are
documented inline in each `src/cleaning/clean_*.py`.

## Outputs

| Entity | File | Rows (clean) | From |
| ------ | ---- | -----------: | ---- |
| places | `places/places_clean.csv` | 8,836 | Riyadh Places |
| reviews | `reviews/reviews_clean.csv` | 3,538 | Tourism Reviews |
| hotels | `hotels/hotels_clean.csv` | 1,025 | Booking.com |
| entertainment | `entertainment/entertainment_clean.csv` | 521 | Entertainment KSA |
| tourism_statistics | `tourism_statistics/tourism_statistics_clean.csv` | 259 | Saudi Tourism 2015–24 |
| tourism_indicators | `tourism_indicators/tourism_indicators_clean.csv` | 403 | DataSaudi (5 of 11 files) |
| events | `events/events_clean.csv` | *(run locally)* | Enjoy.sa API |

## Key cleaning decisions (preserve, don't destroy)

- **Ratings of 0 → null, not a real 0/5.** Places `average_rating == 0` (with 0 ratings)
  and hotels `Star_Rating == 0` (unrated apartments, 532 rows) become null so they don't
  poison "best rated" queries.
- **Unknown ≠ negative.** Hotel `breakfast_included` / `free_cancellation` are three-state
  (`true`/`false`/`null`); missing stays `null`.
- **Sentiment kept as {-1,0,1}/null**; the one non-numeric review value is coerced to null.
- **Zeros retained** in tourism statistics (not forced to null); averages are recomputed
  from summed totals, division-by-zero → null.
- **Granularity resolved**: tourism_statistics collapsed to one row per
  (year, region, tourism_type) — 1,030 sub-rows → 259.
- **Rows dropped only for documented reasons**: entertainment drops 24 column-misaligned
  + 15 non-Saudi + 4 nameless rows; nothing else is deleted.
- **Canonical geography**: all `city`/`region` values mapped via `src/cleaning/geo.py`
  (the join key). Hotel `region` is best-effort — 44 obscure towns keep city + coordinates
  with a null region rather than a wrong guess.
- **Provenance on every row**: `source`, `source_url`, `data_period`, `snapshot_date`,
  `retrieved_at`, `is_live` (see `docs/data_dictionary.md`).

> `events` is the only live source and is not committed here — run `clean_events` where
> `enjoy.sa` is reachable. Booking.com prices are **2020-era** (historical).
