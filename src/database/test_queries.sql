-- Test / smoke queries for the structured knowledge base
-- (data/final/knowledge_base.sqlite — build with:  python -m src.database.build_sqlite)
--
-- Run in any SQLite viewer, or:   sqlite3 data/final/knowledge_base.sqlite < src/database/test_queries.sql
-- The "-> " comment under each query is the result observed on the current build.


-- 0. Integrity: every table and view is present (expect 12 tables + 4 views)
SELECT type, name
FROM sqlite_master
WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
ORDER BY type, name;
-- -> 12 tables (candidate_links … tourism_statistics) + 4 views (v_entity_canonical, v_hotels, v_places, v_reviews_resolved)


-- 1. Row counts per entity table
SELECT 'places' AS entity, COUNT(*) AS n FROM places
UNION ALL SELECT 'hotels',        COUNT(*) FROM hotels
UNION ALL SELECT 'entertainment', COUNT(*) FROM entertainment
UNION ALL SELECT 'reviews',       COUNT(*) FROM reviews
UNION ALL SELECT 'events',        COUNT(*) FROM events;
-- -> places 8836 | hotels 1025 | entertainment 521 | reviews 3538 | events 5770


-- 2. Verifier hard-filter: the thesis example — budget + capacity + guest rating
--    "hotels in Riyadh under 500 SAR, sleeps >= 2, guest rating >= 8"
SELECT name, price_sar, star_rating, guest_rating, max_persons
FROM hotels
WHERE city = 'Riyadh' AND price_sar < 500 AND guest_rating >= 8 AND max_persons >= 2
ORDER BY guest_rating DESC, price_sar ASC
LIMIT 10;
-- -> 34 rows match; top: Ewaa Express Hotel - Gaber (375 SAR, guest 9.1)


-- 3. Top-rated Riyadh restaurants with enough reviews to be trustworthy
SELECT name, average_rating, rate_count
FROM places
WHERE city = 'Riyadh' AND is_restaurant = 1 AND rate_count >= 100
ORDER BY average_rating DESC, rate_count DESC
LIMIT 10;
-- -> Aqwom (5.0, 2438 reviews), Order For Them (4.9, 4208), ...


-- 4. Temporal + audience: family-allowed events overlapping a trip window (Aug 2026)
SELECT name, city, start_date, end_date, is_family_allowed
FROM events
WHERE is_family_allowed = 1
  AND date(start_date) <= '2026-08-31'
  AND date(end_date)   >= '2026-08-01'
ORDER BY start_date
LIMIT 10;
-- -> returns ongoing / open-ended family events active in the window


-- 5. Entity resolution worked: canonical entities that absorbed more than one source row
SELECT canonical_id, name, n_members, n_sources
FROM canonical_entities
WHERE n_members > 1
ORDER BY n_members DESC
LIMIT 10;
-- -> 225 canonical entities merged >1 member (e.g. RYD_003512 with 13 members)


-- 6. Join through a view: reviews resolved to their canonical place
SELECT canonical_id, COUNT(*) AS n_reviews
FROM v_reviews_resolved
WHERE canonical_id IS NOT NULL
GROUP BY canonical_id
ORDER BY n_reviews DESC
LIMIT 10;
-- -> most reviews stay unlinked (different source naming); linked ones aggregate here


-- 7. Data-quality guard: a rating of 0 must be stored as NULL (unrated), never as 0/5
SELECT SUM(average_rating IS NULL) AS null_ratings,
       SUM(average_rating = 0)     AS zero_ratings,
       MIN(average_rating)         AS min_nonnull
FROM places;
-- -> null_ratings 749 | zero_ratings 0 | min_nonnull 1.0   (no 0 ratings leaked in)


-- 8. Provenance present for evidence grounding (every hotel has a source_url)
SELECT COUNT(*) AS total,
       SUM(source_url IS NOT NULL AND source_url <> '') AS with_url,
       SUM(is_live = 1) AS live_rows
FROM hotels;
-- -> total 1025 | with_url 1025 | live_rows 0  (Booking.com is a 2020 static snapshot)


-- 9. Cross-source join hub: pick any canonical id and see all its source records
SELECT canonical_id, entity_type, source, source_entity_id, canonical_name, city
FROM v_entity_canonical
WHERE canonical_id = 'RYD_000154';   -- ALkhozama cafe (2 merged source rows)
