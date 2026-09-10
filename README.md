# Saudi Digital Concierge

A retrieval-augmented (RAG), multi-agent AI concierge for tourism in Saudi Arabia.
It ingests open data about places, reviews, events, entertainment, hotels and
tourism statistics, cleans and embeds it into a vector store, and uses a team of
agents (Manager → Retrieval → Planning → Verifier) to answer visitor questions
and build grounded trip itineraries in Arabic or English.

## Data sources

Six sources feed the concierge. Each has an exploration notebook in `notebooks/` and a
`FINDINGS.md` alongside its data.

| # | Source | Size | What we'll use it for | Lands in |
| - | ------ | ---- | --------------------- | -------- |
| 1 | **Saudi Tourism Reviews — Zenodo** | 3,543 × 10 | Arabic reviews + aspect sentiment | `data/raw/tourism_reviews/` |
| 2 | **Riyadh Places 8.8K — Kaggle** | 8,836 × 9 | POIs, categories, ratings, coordinates | `data/raw/riyadh_places/` |
| 3 | **Saudi Tourism Dataset 2015–2024 — Kaggle** | 1,058 × 9 | Tourism demand, spending, overnight stays | `data/raw/tourism_statistics/` |
| 4 | **DataSaudi — Tourism Indicators** | ~1,915 (11 files) | Official tourism statistics | `data/raw/tourism_statistics/tourism_statistics_datasaudi/` |
| 5 | **Enjoy.sa Events API** | 5,802 × 14 | Events: dates, times, city, family/gender constraints | `data/raw/events/` |
| 6 | **Booking.com Hotels — Kaggle** | 1,025 × 21 | Hotels & apartments: price, ratings, rooms, coordinates | `data/raw/Booking.com/` |
| 7 | **Entertainment in Saudi Arabia — Kaggle** | 564 × 7 | Entertainment places, ratings, categories, locations | `data/raw/entertainment/` |

> The *SaudiTourism — Hugging Face* source was evaluated and dropped; Booking.com replaces
> it as the accommodation source.

### Provenance & licensing

| Source | License | Original source | Snapshot / date | Current / live? | Main use |
| ------ | ------- | --------------- | --------------- | --------------- | -------- |
| Tourism Reviews | CC0 | Zenodo | — | No | Reviews |
| Riyadh Places | TBD | Kaggle | — | No | POIs |
| Saudi Tourism | TBD | Kaggle | 2015–24 | No | Statistics |
| DataSaudi | Official | DataSaudi | 2015–25 | Depends | Statistics |
| Enjoy.sa | Official API | Enjoy.sa | Retrieved 2026 | **Yes / current API** | Events |
| Entertainment | TBD | Kaggle | — | No | Entertainment |
| Booking.com | TBD | Kaggle | **2020** | **No** | Hotels |

> Only the Enjoy.sa events API is live/current; every other source is a static snapshot.
> Booking.com prices are **2020-era** and should be surfaced as historical.

## Project structure

```
Saudi-Digital-Concierge/
├── data/
│   ├── raw/                  # unmodified source data
│   │   ├── tourism_reviews/
│   │   ├── riyadh_places/
│   │   ├── tourism_statistics/  # + tourism_statistics_datasaudi/
│   │   ├── entertainment/
│   │   ├── events/
│   │   └── Booking.com/
│   ├── processed/            # cleaned, normalised data
│   └── final/                # embeddings / vector store artefacts
│
├── notebooks/                # exploration & prototyping
│
├── src/
│   ├── ingestion/            # load raw sources
│   ├── cleaning/             # normalise & clean text
│   ├── database/             # embed & store vectors
│   ├── retrieval/            # semantic search
│   └── agents/               # RAG question-answering agent
│
├── evaluation/               # metrics & test harness
├── tests/                    # unit tests
└── README.md
```

## Pipeline

```
ingestion  ->  cleaning  ->  database  ->  retrieval  ->  agents
```

## Agent architecture (planned)

A **4-agent** design for building trip itineraries: a Manager orchestrates, a
Retrieval agent gathers evidence, a Planning agent builds the itinerary, and a
Verifier checks it — looping back to Planning until the plan is valid.

```
User
 ↓
Manager
 ↓
Retrieval
 ↓
Planning
 ↓
Verifier
 ↓
 ├── PASS → Final Itinerary
 │
 └── FAIL → Planning → Verifier
```

**1. Manager / Orchestrator Agent**
Understands the request and coordinates the other agents. Extracts:
destination · dates · number of travelers · budget · family/individual ·
preferences · constraints — then decides what needs to happen.

**2. Retrieval Agent**
Finds the relevant evidence from the knowledge base. Draws on:
Source 1 → reviews · Source 2 → places/restaurants · Source 5 → events ·
Source 6 → hotels · Source 7 → entertainment · Sources 3/4 → tourism statistics
when relevant. Returns **evidence, not the final itinerary**.

**3. Planning Agent**
Constructs the actual itinerary from the retrieved candidates, satisfying:
budget · dates · preferences · group size · activities · hotels · events ·
geographic efficiency. Produces a sequenced plan
(e.g. `Day 1 → Hotel → Museum → Restaurant → Event`) rather than a flat list.

**4. Verifier Agent** ⭐
Tries to catch mistakes in the proposed itinerary. Checks:
every user constraint is satisfied · events on the correct dates · hotel within
budget · hotel suitable for the group size · activities geographically reasonable ·
no unsupported information · nothing hallucinated by the planner.
If valid → final answer; if invalid → send back to Planning for revision.

> Note: empty folders are kept under version control with `.gitkeep` files.
