# Events — Findings Summary (Source 5: Enjoy.sa Events API)

**Endpoint:** `https://enjoy.sa/api/v1/odp/events/Get`
**Exploration:** `notebooks/05_data_exploration_events_enjoy_sa.ipynb`
**Response envelope:** `{ Status, IsSucceeded, Data, Message }` — records under `Data`.

| # | Question | Finding |
| - | -------- | ------- |
| 1 | Number of events | **5,802** (full set returned by default) |
| 2 | Available fields | **14**: `Name`, `City`, `StartDate`/`StartDateFormatted`, `EndDate`/`EndDateFormatted`, `StartTime`/`StartTimeFormatted`, `EndTime`/`EndTimeFormatted`, `IsMaleAllowed`, `IsFemaleAllowed`, `IsFamilyAllowed`, `EventMode` |
| 3 | Date coverage | Event start dates **Jan 2017 → Oct 2026**; a few long-running / open-ended events end later (into ~2030) |
| 4 | City coverage | **74 cities** (Arabic names). Top: الرياض 3,012 · جدة 1,054 · الطائف 214 · الخبر 157 · الدمام 141. Riyadh + Jeddah ≈ 70% |
| 5 | Categories / types | **None** — the API has no category field. `EventMode` is a status flag, not a category |
| 6 | Start / end dates | Present for all rows. ISO (`StartDate`) and `*Formatted` (DD-MM-YYYY) are **consistent** — same dates, two formats |
| 7 | Start / end times | Present for all 5,802 (`HH:MM:SS` + Arabic 12h). 86 distinct start times, 101 end times |
| 8 | Family / male / female | Male 5,290 ✔ / 471 �’/ 41 none · Female 5,345 / 416 / 41 · Family 5,240 / 521 / 41. Most events open to everyone |
| 9 | Missing values | Gender/family flags 41 each (0.7%); City 4 (0.1%). Dates and times complete |
| 10 | Duplicate events | **30** fully identical rows; **194** duplicates on `Name`+`StartDate`. No unique ID field exists |
| 11 | Active / future events | **Yes — 50 `IsActive`** vs **5,752 `IsExpired`** (`EventMode`). Use `EventMode` for status, not date math |
| 12 | Pagination / limits | Default returns **all 5,802** (no cap). `page`+`pageSize` honoured (`pageSize=1000`→1000); `limit/offset`, `skip/take` **ignored**; no paging metadata in envelope |

## Data-quality notes (for `src/cleaning`)
1. **Dates are consistent** across ISO and `*Formatted` columns. When parsing the
   `*Formatted` (DD-MM-YYYY) fields, pass `dayfirst=True`; otherwise a day > 12 is
   misread as a month and years get distorted (this caused a spurious "2031" in an early
   exploratory parse — **not** a real value). Prefer the ISO `StartDate`/`EndDate` for
   machine parsing.
2. **No unique ID** → deduplicate on a composite key
   (`Name` + `City` + `StartDate` + `StartTime`); expect to drop ~30–194 rows.
3. **Cities are Arabic strings** → map to the canonical city/province key used by the
   other sources (e.g. `الرياض` → Riyadh) so events can join to places/statistics.
4. **Filter with `EventMode`** (`IsActive` / `IsExpired`) to serve live events —
   50 are currently active.
5. **No categories** → if the concierge needs event types, derive them from `Name`
   (keyword or LLM tagging); the API will not provide them.

## Concierge relevance
High — structured, bilingual-ready events with city, dates, times, and audience
restrictions. Directly answers questions like "family-friendly events in Jeddah this
week". Priority after cleaning dates and mapping city names.

## Next steps
1. Save the raw pull to `data/raw/events/enjoy_events_<date>.json`.
2. Implement the cleaning above → tidy events table in `data/processed/`.
3. Embed active/upcoming events (name + city + dates + audience) into the vector store.
