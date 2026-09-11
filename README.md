# Saudi Digital Concierge

### A Multi-Agent LLM Framework for Personalized, Constraint-Aware, and Evidence-Grounded Travel Planning in Saudi Arabia

## Overview

Saudi Digital Concierge is a research project investigating whether a multi-agent Large Language Model (LLM) architecture can improve travel planning compared with an equivalent single-agent LLM architecture.

The system generates personalized travel itineraries for destinations in Saudi Arabia while considering constraints such as:

- Travel dates
- Trip duration
- Budget
- Number and type of travelers
- Personal interests
- Accommodation preferences
- Family-friendly requirements
- Events and their schedules
- Geographic efficiency
- Evidence from tourism data sources

#### The primary goal is not to build a commercial travel-booking application, but to experimentally investigate the benefits and costs of multi-agent LLM planning.

## Research Question

Does a multi-agent LLM architecture improve personalized, constraint-aware, and evidence-grounded travel planning in Saudi Arabia compared with an equivalent single-agent LLM?

## Research Hypotheses

## System Architectures

The experiment compares two architectures while keeping the underlying model, knowledge base, test scenarios, and evaluation methodology consistent.

### Baseline — Single-Agent


### Treatment — Multi-Agent

# Experimental Design

The independent variable is:

#### Agent architecture: Single-Agent vs. Multi-Agent

Both systems will use:

- The same LLM model
- The same Saudi tourism knowledge base
- The same retrieval resources
- The same user scenarios
- The same output format
- The same evaluation criteria
- The same generation configuration where applicable

This ensures that the experiment primarily measures the effect of architecture, rather than differences in data or model capability

## Evaluation Metrics

The systems will be evaluated using three groups of metrics.

## Evaluation Dataset

The evaluation set will consist of realistic Saudi travel scenarios containing different levels and types of constraints.

Scenario categories

| Category | Purpose |
| --- | --- |
| Simple | Basic itinerary planning |
| Constraint-heavy | Multiple simultaneous constraints |
| Temporal | Date/time and event constraints |
| Spatial | Geographic planning |
| Preference-heavy | Personalization |
| Conflicting constraints | Ability to recognize infeasible requirements |

An initial target is approximately 50–100 scenarios, with a possible initial set of around 70 scenarios.

Each scenario will be provided to both architectures using the exact same user request.

### Example Test Scenario

```text
Destination: Riyadh
Duration: 4 days
Travelers: 2 adults + 2 children
Budget: 3,000 SAR
Interests: Culture + Food + Entertainment
Hotel: 4 stars or higher
Preference: Family-friendly
Additional constraint: Include an event during the trip
```

The evaluator will compare how well each architecture satisfies these requirements.

## Repeated Evaluation

Because LLM outputs can vary between runs, each scenario may be executed multiple times under the same configuration.

For example: 70 scenarios × 3 runs × 2 architectures = 420 generated itineraries.

The final number of runs will depend on computational resources.

## Data sources

The project uses publicly available Saudi tourism datasets and event data.

| # | Source | Size | Role | Lands in |
| - | ------ | ---- | --------------------- | -------- |
| 1 | **Saudi Tourism Reviews — Zenodo** | 3,543 × 10 | Review evidence and personalization | `data/raw/tourism_reviews/` |
| 2 | **Riyadh Places 8.8K — Kaggle** | 8,836 × 9 | Places, restaurants, ratings, coordinates | `data/raw/riyadh_places/` |
| 3 | **Saudi Tourism Dataset 2015–2024 — Kaggle** | 1,058 × 9 | Tourism statistics and regional context | `data/raw/tourism_statistics/` |
| 4 | **DataSaudi — Tourism Indicators** | ~1,915 (11 files) | Official tourism statistics | `data/raw/tourism_statistics/tourism_statistics_datasaudi/` |
| 5 | **Enjoy.sa Events API** | 5,802 × 14 | Events, dates, times, cities, audience restrictions | `data/raw/events/` |
| 6 | **Booking.com Hotels — Kaggle** | 1,025 × 21 | Hotel information and static benchmark prices | `data/raw/Booking.com/` |
| 7 | **Entertainment in Saudi Arabia — Kaggle** | 564 × 7 | Attractions and entertainment recommendations | `data/raw/entertainment/` |


### Provenance & licensing

| Source | License | Original source | Current / live? | Main use |
| ------ | ------- | --------------- | --------------- | -------- |
| Tourism Reviews | CC0 | Zenodo | No | Reviews |
| Riyadh Places | TBD | Kaggle | No | POIs |
| Saudi Tourism | TBD | Kaggle | No | Statistics |
| DataSaudi | Official | DataSaudi | Depends | Statistics |
| Enjoy.sa | Official API | Enjoy.sa | **Yes / current API** | Events |
| Entertainment | TBD | Kaggle | No | Entertainment |
| Booking.com | TBD | Kaggle | **No** | Hotels |

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
