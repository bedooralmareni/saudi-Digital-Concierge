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

## knowledge Base

The data will be organized into logical entities rather than merged into a single dataset.

```
Saudi Tourism Knowledge Base
│
├── Places
├── Reviews
├── Restaurants
├── Hotels
├── Events
├── Entertainment
└── Tourism Statistics
```
## Evaluation Procedure

The evaluation follows the same process for both architectures.

```
Traveler Scenario
       ↓
Generate Itinerary
       ↓
Objective Constraint Checks
       ↓
Temporal Validation
       ↓
Spatial Validation
       ↓
Evidence Verification
       ↓
Human Evaluation
       ↓
Efficiency Measurements
       ↓
Statistical Comparison
```

Where possible, objective metrics will be evaluated using deterministic rules rather than relying exclusively on LLM-as-a-judge.

Human evaluation will primarily be used for subjective dimensions such as personalization and itinerary quality.

## Planned Project Structure

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

## Research Pipeline

The project follows the following development pipeline:

```
1. Data Source Inventory
        ↓
2. Raw Data Collection
        ↓
3. Dataset Exploration
        ↓
4. Data Quality Audit
        ↓
5. Data Cleaning & Standardization
        ↓
6. Entity Matching / Deduplication
        ↓
7. Knowledge Base Construction
        ↓
8. Structured + Semantic Retrieval
        ↓
9. Single-Agent Baseline
        ↓
10. Multi-Agent Architecture
        ↓
11. Evaluation Test Set
        ↓
12. Experimental Runs
        ↓
13. Metric Evaluation
        ↓
14. Statistical Analysis
        ↓
15. Failure Analysis
        ↓
16. Thesis Results
```

