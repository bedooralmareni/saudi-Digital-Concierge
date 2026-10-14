# Saudi Digital Concierge

### A Multi-Agent LLM Framework for Personalized, Constraint-Aware, and Evidence-Grounded Travel Planning in Saudi Arabia

## Overview

Saudi Digital Concierge is a research project investigating whether a **multi-agent Large Language Model (LLM) architecture** improves Saudi travel planning compared with an equivalent **single-agent architecture**.

The system aims to recommend hotels, attractions, events, and travel itineraries while considering travel dates, trip duration, budget, traveler composition, interests, accommodation preferences, family-friendly requirements, event schedules, and available tourism evidence.

**Research scope:** This is an experimental travel-planning system, not a live booking or payment service. Recommendations depend on the coverage and freshness of the knowledge base.

## Research Question

**Does a multi-agent LLM architecture improve personalized, constraint-aware, and evidence-grounded travel planning in Saudi Arabia compared with an equivalent single-agent LLM architecture?**

## Research Hypotheses

- **H0 (Null hypothesis):** Under comparable conditions, multi-agent and single-agent systems do not show a meaningful difference in constraint satisfaction and recommendation relevance.
- **H1 (Alternative hypothesis):** Under comparable conditions, multi-agent systems improve constraint satisfaction and recommendation relevance compared with single-agent systems.

## Success Criteria

Our primary priorities are **accuracy and constraint satisfaction**, followed by recommendation relevance and user experience. We also measure execution time and cost to determine whether any quality improvements justify the additional resources.

## System Architectures and Current Status

### M4 — Implemented Single-Agent Baselines

Two single-agent baseline notebooks have been implemented and run by the project team:

- **Qwen Single-Agent:** A local Qwen-based agent.
- **OpenAI Single-Agent:** An OpenAI API-based agent.

Each baseline receives a travel request, selects relevant retrieval tools, obtains evidence from the Saudi tourism knowledge base, and generates an answer. The main tools cover hotel search, attraction/place search, and event search. The notebooks include demonstration scenarios and execution traces.

**M4 repository folder:** [M4 — Baseline running](https://github.com/bedooralmareni/saudi-Digital-Concierge/tree/main/M4%20-%20Baseline%20running)

For notebook-specific requirements and exact run instructions, refer to the README in that folder. Successful runs reported by the team do not, by themselves, establish that every local environment has been verified.

### Planned Multi-Agent Treatments

The multi-agent versions will coordinate specialized responsibilities for hotel, attraction, and event retrieval and itinerary assembly/checking. Their exact coordination design and implementation will be documented when the treatments are built. **The multi-agent treatments are planned work, not part of the completed M4 baseline.**

## Experimental Design

The study has **four configurations**:

| Model family | Baseline | Treatment |
|---|---|---|
| Qwen | Qwen Single-Agent | Qwen Multi-Agent |
| OpenAI | OpenAI Single-Agent | OpenAI Multi-Agent |

The primary comparisons are **within each model family** (Qwen Single-Agent vs. Qwen Multi-Agent; OpenAI Single-Agent vs. OpenAI Multi-Agent). Cross-model comparisons are secondary.

Within each matched comparison, we aim to keep the following consistent:

- Knowledge base and data snapshot
- Available information and equivalent retrieval capabilities
- User scenarios and expected output schema
- Evaluation criteria and scoring procedures
- Generation settings where supported and applicable

The main independent variable is **agent architecture (single-agent vs. multi-agent)**. Model family is an additional experimental factor.

## Task Suite and Dataset Split

The **planned evaluation suite** contains **100 distinct scenarios**: **70 typical tasks** and **30 edge cases**. Scenarios will cover multiple Saudi cities, budgets, preferences, and Arabic and English requests.

**Typical tasks:** hotel recommendations, attraction discovery, event recommendations, and complete itinerary planning.

**Edge cases:** limited budgets, conflicting constraints, missing or outdated information, and multiple complex requirements.

| Split | Number of scenarios | Purpose |
|---|---:|---|
| Development | 60 | Debugging and system improvement |
| Validation | 20 | Monitoring regressions and selecting configurations |
| Final test (held out) | 20 | Final comparative evaluation |
| **Total** | **100** | |

The splits will include a mixture of task types and difficulty levels. Near-duplicate scenarios should not be distributed across different splits. **These counts describe the agreed evaluation plan, not a claim that the complete 100-case suite has already been executed.**

### Example Scenario

```text
Destination: Riyadh
Duration: 4 days
Travelers: 2 adults and 2 children
Budget: 3,000 SAR
Interests: Culture, food, and entertainment
Hotel: 4 stars or higher
Preferences: Family-friendly
Additional constraint: Include an event during the trip
```

The evaluator will check which requirements are satisfied, whether recommended items are supported by evidence, and whether the itinerary is internally consistent.

## Evaluation Metrics

We will combine **rule-based checks** and **LLM judges** to assess both final outcomes and execution processes.

| Metric | Evaluation method | Process or outcome |
|---|---|---|
| Constraint satisfaction | Rule-based checks | Outcome |
| Itinerary consistency | Rule-based checks | Outcome |
| Itinerary completeness | Rule-based checks | Outcome |
| Recommendation relevance | LLM judge with a fixed rubric | Outcome |
| Tool usage | Rule-based checks and LLM judge | Process |
| Execution steps | Rule-based checks and LLM judge | Process |
| Errors | Rule-based checks | Process |
| Execution time | Recorded runtime measurement | Process / efficiency |
| API or inference cost | Usage-based calculation or resource estimate | Process / efficiency |

Rule-based checks require structured outputs and explicit reference criteria. For example, consistency checks can flag conflicting activity times or violations of itinerary duration. LLM-judge assessments will use a documented rubric and consistent judging settings; human spot-checking may be used to assess judge reliability.

At least one **trajectory-level metric** will be computed from agent traces, such as tool-call success rate. We will distinguish between successful tool execution and whether the chosen tool was appropriate for the task.

## Iteration and Regression Detection

We will evaluate the systems after major changes to prompts, tools, retrieval methods, or agent architecture.

1. Use the **development set (60)** to diagnose failures and improve the systems.
2. Use the **validation set (20)** to compare versions and detect regressions in quality, reliability, time, and cost.
3. Freeze configurations before using the **held-out final test set (20)**.
4. Evaluate the four configurations on the same final scenarios, with **three recorded runs per scenario/configuration** under controlled settings.
5. Analyze failures and execution traces, and report performance differences and variability.

The planned final evaluation therefore contains **20 scenarios × 4 configurations × 3 runs = 240 executions**. Repeated runs and seed support will be documented for each model/API; changing a seed does not guarantee independent or different outputs.

Final-test cases will not be used to tune the evaluated versions. If a genuine system weakness is discovered during final testing, it will be reported rather than silently tuned away; any revised version requires a new, untouched final test for an unbiased estimate. Scoring-code defects may be corrected transparently and rescored consistently across configurations.

## Data Sources

The project inventory lists the following tourism-related sources. **Counts below are the figures recorded in the project documentation and should be rechecked against the current repository/data snapshot before publication.**

| Source | Documented size | Intended role | Data directory |
|---|---:|---|---|
| Saudi Tourism Reviews — Zenodo | 3,543 × 10 | Reviews and personalization | `data/raw/tourism_reviews/` |
| Riyadh Places — Kaggle | 8,836 × 9 | Places, ratings, and coordinates | `data/raw/riyadh_places/` |
| Saudi Tourism Dataset 2015–2024 — Kaggle | 1,058 × 9 | Tourism statistics and regional context | `data/raw/tourism_statistics/` |
| DataSaudi Tourism Indicators | ~1,915 records across 11 files | Official tourism indicators | `data/raw/tourism_statistics/tourism_statistics_datasaudi/` |
| Enjoy.sa Events API export | 5,802 × 14 | Events, schedules, and audience restrictions | `data/raw/events/` |
| Booking.com Hotels — Kaggle | 1,025 × 21 | Hotel details and snapshot prices | `data/raw/Booking.com/` |
| Entertainment in Saudi Arabia — Kaggle | 564 × 7 | Entertainment and attraction recommendations | `data/raw/entertainment/` |

### Data Provenance, Freshness, and Licensing

- Most imported datasets are **static snapshots**, not real-time inventories.
- Event records sourced from an API should **not** be described as live unless the running system fetches and refreshes them during execution. A saved API export can become outdated.
- Hotel prices and event availability may have changed. Missing prices or availability must not be interpreted as confirmed values.
- Licensing and redistribution rights for each dataset must be verified from its original source before publishing raw data. Entries previously marked `TBD` remain **unverified**; an official source or API is not itself a license statement.
- Source links, retrieval dates, and dataset versions should be maintained in a provenance manifest.

## Knowledge Base

The project uses a **hybrid knowledge base**, combining structured retrieval for exact constraints and vector retrieval for semantic relevance.

```text
                  Saudi Tourism Knowledge Base
                              |
               +--------------+--------------+
               |                             |
       Structured layer                 Vector layer
            SQLite                  Multilingual embeddings
       Exact attributes              Descriptions and reviews
               |                             |
               +--------------+--------------+
                              |
                      Retrieved evidence
                              |
                       Single-Agent LLM
                              |
                      Travel recommendation
```

### Structured Layer

The documented SQLite artifact is `data/final/knowledge_base.sqlite`. It stores standardized tourism entities and supports exact predicates such as city, hotel price, ratings, and dates. The project documentation references query functions in `src.database.kb`, including `find_hotels`, `find_places`, and `find_events`.

Build command (from the repository root, after required processed data are available):

```bash
python -m src.database.build_sqlite
```

### Vector Layer

The documented vector index is stored under `data/final/vector_store/`. The recorded default embedding model is `intfloat/multilingual-e5-base`, supporting Arabic and English semantic retrieval. The previous documentation reports **13,920 embedded KB documents**; this figure must be confirmed against the current index build.

Build command:

```bash
python -m src.vector_store.build_index
```

### Hybrid Retrieval

Structured filtering is used for measurable requirements, while semantic search helps match preferences such as culture, entertainment, or family suitability. Where supported, retrieved records are linked by entity identifiers and source references to support evidence-grounded recommendations.

The SQLite database and vector index may be generated artifacts rather than tracked Git files. Rebuilding them requires the relevant input data and dependencies. See the M4 README for notebook setup instructions.

## Evaluation Procedure (Planned)

```text
User scenario
    |
Run selected agent configuration
    |
Save final answer and execution trace
    |
Rule-based outcome checks
    |
LLM-judge relevance scoring
    |
Process, latency, and cost measurements
    |
Compare results across models and architectures
    |
Failure analysis and reporting
```

Where possible, objective requirements will be scored with deterministic checks rather than relying solely on LLM judgments.

## Repository Organization

The repository documentation describes these functional areas (verify exact paths against the current checkout):

```text
saudi-Digital-Concierge/
├── data/
│   ├── raw/                  # Source datasets
│   ├── processed/            # Cleaned and standardized datasets
│   └── final/                # Generated KB and retrieval artifacts
├── src/
│   ├── ingestion/            # Source loading
│   ├── cleaning/             # Data preparation
│   ├── entity_resolution/    # Record matching (if present)
│   ├── database/             # SQLite build and query functions
│   └── vector_store/         # Embedding/index build and retrieval
├── M4 - Baseline running/    # Baseline notebooks and M4 documentation
├── evaluation/               # Evaluation code (planned/in progress)
├── tests/                    # Automated tests (where implemented)
└── README.md
```

Do not interpret every listed folder as a verified, already-completed component. The M4 folder contains the baseline submission; subsequent milestones will add the multi-agent treatments and evaluation harness.

## Research and Implementation Roadmap

| Stage | Status |
|---|---|
| Data collection, cleaning, and KB construction | Developed for baseline use; details depend on current repository snapshot |
| Single-Agent baselines (Qwen and OpenAI) | Implemented and run by the team for M4 |
| Evaluation scenario suite and scoring harness | Planned for M5 |
| Multi-Agent treatments and comparative experiments | Planned for M6 |
| Final analysis and research reporting | Planned for later milestones |

## Limitations and Responsible Use

- The system does **not** make hotel bookings, payments, or reservations.
- Recommendations may be limited by incomplete, outdated, or inconsistent source records.
- The agent may still produce unsupported claims; outputs should be checked against retrieved evidence.
- Real-time prices, opening hours, and event availability are **not guaranteed**.
- API keys and other secrets must never be committed to the repository.
- Model, dataset, prompt, and evaluation versions should be recorded to support reproducibility.

## Getting Started

For exact notebook paths, dependencies, environment setup, API-key instructions, and demonstration steps, see the [M4 — Baseline running folder](https://github.com/bedooralmareni/saudi-Digital-Concierge/tree/main/M4%20-%20Baseline%20running).

**Project status:** The current M4 deliverable is the working **Single-Agent baseline**. Multi-agent coordination and the 100-scenario comparative evaluation are **planned subsequent work**.
