# Tourism Statistics — Findings Summary

This folder holds two related sources of official Saudi tourism statistics:

- **Source 3 — Saudi Tourism Dataset 2015–2024 (Kaggle):** `tourism_data.csv`
- **Source 4 — DataSaudi Tourism Indicators:** the per-region `*2024 Tourism Indicator Spending*.csv` files (and the additional DataSaudi tables listed below)

Both are **supporting statistical context** for the concierge, not core conversational
content. The reviews, places, and events sources carry most of the user-facing value.

---

## Source 3 — `tourism_data.csv` (2015–2024)

**Full exploration:** `notebooks/03_data_exploration_tourism_statistics.ipynb`

### Shape & coverage
- **1,058 rows × 9 columns**
- **Years:** 2015–2024 (10 years)
- **Provinces:** 13 (Albaha, Alqassim, Aseer, Eastern_region, Hail, Jazan, Jouf,
  Madinah, Makkah, Najran, Northern_borders, Riyadh, Tabuk)
- **Tourism_Type:** Domestic (540) / Inbound (518)

### Columns
| Column | Type | Meaning (units inferred — confirm on source) |
| ------ | ---- | -------------------------------------------- |
| `YEARS` | int | Year (2015–2024) |
| `Tourists_Number` | float | Number of tourists (thousands) |
| `Overnight_Stay` | float | Total overnight stays (thousands of nights) |
| `Tourists_Spending` | float | Total spending (millions SAR) |
| `Avg_Stay` | float | Average length of stay (nights) |
| `Avg_Spending_Trip` | float | Average spending per trip (SAR) |
| `Avg_Spending_Night` | float | Average spending per night (SAR) |
| `Province` | str | One of 13 administrative regions |
| `Tourism_Type` | str | Domestic / Inbound |

### Key signal
- **Clear COVID-19 shock:** inbound tourists collapse in 2020–2021 (~8–9K vs ~35K
  before) and recover strongly through 2022–2024. Domestic tourism grows steadily and
  ends well above pre-pandemic levels.

### Data-quality issues (to handle in `src/cleaning`)
1. **28 exact duplicate rows** — drop them.
2. **~20 all-zero metric rows** (and ~21 with `Tourists_Number == 0`) — likely
   suppressed/missing data encoded as `0`; treat as `NaN` so they don't deflate averages.
3. **Granularity is not unique** — instead of one row per (year, province, type), groups
   have **2–6 rows**, suggesting a sub-category dimension was flattened or observations
   were stacked. Resolve before aggregating: sum the volume columns and **recompute** the
   `Avg_*` columns from the summed totals (do not average pre-computed averages).
4. **Standardise labels** — `Eastern_region`, `Northern_borders` → human-readable names
   for retrieval; keep a canonical province key.
5. **No literal `NaN`** values present, but confirm units (thousands / millions SAR) on
   the Kaggle source page and record them in the schema.

---

## Source 4 — DataSaudi Tourism Indicators

**Question:** Should all 11 official DataSaudi datasets be included?
**Finding:** **No.** A curated subset of ~5–6 files (~380 rows) is better than all 11
(~3,400 rows) for a RAG concierge — the rest either duplicate Source 3 or add noise.

| DataSaudi dataset | Rows | Verdict | Reason |
| ----------------- | ---- | ------- | ------ |
| Overnight Tourists by **Purpose of Visit** & Type | 127 | ✅ Keep | New "purpose of visit" dimension |
| Spending by **Purpose of Visit** & Category | 126 | ✅ Keep | New dimension; budgeting context |
| Tourism **Satisfaction Index** — Quarterly | 6 | ✅ Keep | Tiny, unique sentiment signal |
| **Net Promoter Score** — Quarterly | 6 | ✅ Keep | Tiny, unique sentiment signal |
| Tourism **Complementary Indicators** — Annual | 6 | ✅ Keep | Tiny summary indicators |
| Tourism **Occupancy Rate** — Annual | 116 | ⚪ Optional | "How busy" context; keep annual only |
| Average Length of Stay by Category | 49 | ❌ Skip | Duplicates `Avg_Stay` in Source 3 |
| Average Spending Per Trip by Category | 49 | ❌ Skip | Duplicates `Avg_Spending_Trip` |
| Number of Overnight Stays by Type | 49 | ❌ Skip | Duplicates `Overnight_Stay` |
| Spending Rate Per Night by Category | 49 | ❌ Skip | Duplicates `Avg_Spending_Night` |
| Tourism Occupancy Rate — **Monthly** | 1,392 | ❌ Skip | Heavy operational series; poor RAG material |

**Recommendation:** keep the 5 ✅ (optionally + annual occupancy). Treat statistics as
supporting context, not core concierge content.

> **Caveat:** if this doubles as a data-engineering showcase, ingesting all 11 (small
> except monthly occupancy) is defensible to demonstrate a multi-source pipeline — but
> for answer quality, curation wins.

---

## Next steps
1. Decide the final Source-4 file list (curated vs. all).
2. Clean Source 3 per the notes above → write one tidy row per (year, province, type)
   to `data/processed/` with documented units.
3. Explore the chosen Source-4 files (purpose-of-visit and sentiment tables add the most
   distinct value).
