# Booking.com Hotels — Findings Summary (Source 6)

**File:** `data/raw/Booking.com/project3_df1.csv`
**Exploration:** `notebooks/06_data_exploration_booking_hotels.ipynb`

> **Snapshot date:** booking links carry `checkin=2020-04-24` → this is a **2020 snapshot**.
> Treat prices and availability as historical, not live.

## Overview
- **1,025 rows × 21 columns**. `Property_id` is a clean **unique key** (0 duplicates).
  `Unnamed: 0` is a redundant index.
- Fills the **accommodation ("where to stay")** gap the other sources don't cover.

## Columns
`Name`, `City`, `Price`, `Star_Rating`, `Property_Demand`, `Property_id`,
`Customers_Rating`, `Customers_Review`, `Type_of_room`, `reservations_Payment`,
`Canelation`, `Max_persons`, `Bed_type`, `Tax`, `Review_title`, `Credit_card`,
`Breakfst_included`, `Longitude_x`, `Latitude_y`, `Link` (+ index).

## Coverage & signal
- Prices **SAR 23–7,907**, median **~130 / night**.
- **Nationwide coordinates** (lat 16.8–31.7, lon 35–50) — the only source with geo
  outside Riyadh. 112 raw locations; top cities Riyadh 132, Jeddah 98, Dammam 59,
  Makkah 50, Al Khobar, Abha, Taif, Yanbu, Buraydah.
- Guest ratings **3.4–9.6 (mean ~7.4)**; qualitative labels Good → Exceptional.

## Data-quality issues (for `src/cleaning`)
1. **`Star_Rating == 0` for 532 rows (52%)** = *unrated* (apartments/unclassified), not
   zero-star. Treat 0 as "unrated"; don't average it in.
2. **2020 snapshot** — flag pricing/availability as historical.
3. **`Price` is text** (`SAR 179`) → parse to numeric SAR.
4. **`City` mixes neighbourhood + city** (`Ajyad, Makkah`, `Al Olayya, Al Khobar`) →
   extract base city and map to the canonical city/province key used by the other sources.
5. **Sparse columns**: `Breakfst_included` 92% missing (treat missing as
   "not included / unknown"); `Credit_card` 321, `reservations_Payment` 290,
   `Property_Demand` 275, `Canelation` 179 missing;
   `Customers_Rating`/`Customers_Review`/`Review_title` 69 each; `Bed_type` 19.
6. **Column-name typos**: `Canelation`, `Breakfst_included`, `Longitude_x`, `Latitude_y`
   → rename to clean, consistent names.
7. **`Max_persons`, `Tax`, `Customers_Review` are text** → parse to numeric where useful.
8. **`Link`** is a long URL — keep as a source reference, exclude from embeddings.

## Concierge relevance
High — the **accommodation** source with price, star & guest ratings, occupancy, and
**nationwide coordinates**, enabling "affordable family hotel in Makkah near the Haram"
answers. Complements places / events / entertainment. Flag results as 2020-era pricing.

## Next steps
1. Rename columns, parse price/occupancy/tax, treat `Star_Rating==0` as unrated.
2. Extract base city; map to the canonical city/province key.
3. Write a tidy `hotels` table to `data/processed/`.
4. Embed name + city + star/guest rating + room type + price into the vector store.
