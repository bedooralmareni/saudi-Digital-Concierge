# Saudi Digital Concierge

### A Multi-Agent LLM Framework for Personalized, Constraint-Aware, and Evidence-Grounded Travel Planning in Saudi Arabia

## M4 — Working single-agent baseline

**Travel request → retrieve KB evidence → generate an answer → display it.**

Repository: [bedooralmareni/saudi-Digital-Concierge](https://github.com/bedooralmareni/saudi-Digital-Concierge).
The baseline uses local **Qwen3.5:4B** through Ollama and the existing hybrid KB.
Multilingual E5 ranks records by meaning; SQLite provides their exact source facts.
The runner is explained with comments in `src/inference/local_runner.py`.

### 1. Install prerequisites and Python dependencies

Install Git, **Python 3.11**, and [Ollama](https://ollama.com/download).
Use the Windows/macOS installer or follow the official Linux installation instructions.
Allow disk space for both model downloads and Python dependencies. CPU inference
works; runtime depends on hardware. The development machine has 16 GB RAM.

Clone the repository and enter it:

```text
git clone https://github.com/bedooralmareni/saudi-Digital-Concierge.git
cd saudi-Digital-Concierge
```

Windows PowerShell (activation is unnecessary):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

In the remaining examples, `python` means the virtual environment interpreter:
`.\.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux.
Run all commands from the repository root. No notebook or API key is needed.

### 2. Prepare local Qwen

Start the Ollama desktop app, or run `ollama serve` in another terminal if the
server is not already running. Then download the explicit model tag:

```text
ollama pull qwen3.5:4b
ollama list
```

Confirm `qwen3.5:4b` appears in the list. The baseline connects to
`http://localhost:11434` and does not download models automatically.

### 3. Build the knowledge base

The cleaned and standardized CSVs are included in the repository. Build the
local artifacts from them in this order; re-cleaning raw data is unnecessary:

```text
python -m src.entity_resolution.resolve
python -m src.database.build_sqlite
python -m src.vector_store.build_index
```

The last command downloads `intfloat/multilingual-e5-base` on first use and embeds
the KB documents. It can take several minutes on CPU. Leave `EMBED_MODEL` unset
to use the default real multilingual model; the test stub is not accepted here.
Keep internet access available for dependency and first-time model downloads.
Inference subsequently uses the cached embedding weights and local Ollama.

These generated artifacts are ignored by Git and must be built on a fresh clone:

- `data/final/knowledge_base.sqlite`
- `data/final/vector_store/vectors.npy`
- `data/final/vector_store/vector_meta.csv`
- `data/final/vector_store/index_info.json`

### 4. Run a travel request

Interactive:

```text
python run_single_model.py
```

Enter your travel request, then the exact KB city name. Examples include `Riyadh`,
`Jeddah`, `Dammam`, and `Al Khobar`. The request itself may be Arabic or English.

English example:

```text
python run_single_model.py --city Riyadh --type hotel --prompt "Suggest one hotel in Riyadh and explain its recorded price and guest rating."
```

Arabic example:

```text
python run_single_model.py --city Riyadh --type place --prompt "اقترح مكانًا للقهوة في الرياض واذكر تقييمه من البيانات المتاحة."
```

`--type` is optional: `place`, `hotel`, or `entertainment`. Without it, the runner
searches all three types. It retrieves up to six unique canonical entities and
makes one Qwen generation call. The terminal displays supporting entity names
and IDs, then the generated answer. It does not save experiment files.

Expected output structure (names and answer vary):

```text
Retrieving KB evidence...

KB evidence:
- [RYD_...] <recorded entity name> (hotel)

Generating with local Qwen...

Answer:
<answer based on the retrieved facts>
```

Defaults: thinking off, context 4096, output limit 1024, temperature 0.7, seed 42,
and request timeout 300 seconds. Hotel prices are historical, not live quotes.
City/type filters are exact; budget and other natural-language requirements are
assessed by Qwen against retrieved facts. This small retrieved set is not an
exhaustive search for every constraint. Citations are requested in the prompt;
answer accuracy and citation correctness still need review. Opening hours, live
availability, accessibility, and certifications may be unknown. Events are outside
this baseline's retrieval scope.

### 5. Verify and troubleshoot

```text
python -m pytest -q
```

Automated tests use fixtures and mocked Ollama responses, with no model downloads.
For the M4 acceptance check, follow the setup from a fresh checkout, run the English
and Arabic examples, and confirm both show KB evidence followed by a nonempty answer.
Windows with Python 3.14.2 is the available verification environment; Python 3.11
is the recommended setup version above. macOS/Linux commands are provided
but should not be interpreted as completed platform testing.

| Problem | Action |
| --- | --- |
| Cannot connect to Ollama | Start the app or `ollama serve`; confirm port 11434 is available. |
| Missing `qwen3.5:4b` | Run `ollama pull qwen3.5:4b`. |
| Missing KB artifact or canonical IDs | Repeat step 3 in order. |
| Embedding weights missing from cache | With internet enabled, rebuild the real vector index using the same user account. |
| No retrieved evidence | Check the exact city spelling and selected type; city coverage varies. |
| Slow response or timeout | Close memory-heavy applications and try a shorter request. |
| Python package not found | Use the virtual environment interpreter from step 1. |

The sections below describe the broader research project; M4 implements the
single-agent baseline described above.

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

The M4 baseline retrieves city-filtered KB records, enriches them with SQLite facts,
and makes one local Qwen3.5:4B call to answer the travel request. It displays both
supporting records and the answer. Follow the M4 setup steps at the top of this README.

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

## Knowledge Base

The data is organized into logical entities rather than merged into a single dataset, and
served through a **hybrid knowledge base** — a structured layer for exact constraints and a
vector layer for semantic meaning, joined on `canonical_id` / `entity_id`.

```
                     Knowledge Base
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                      ▼
   Structured layer                       Vector layer
   SQLite (src/database)                  embeddings (src/vector_store)
   exact filters & the                    semantic search over
   Verifier's hard checks                 reviews / descriptions
        │                                      │
        └──────────────────┬──────────────────┘
                           ▼
                  Hybrid retrieval
             (metadata pre-filter → semantic rank)
```

**Entities:** Places · Reviews · Restaurants (a view of Places) · Hotels · Events ·
Entertainment · Tourism Statistics · Tourism Indicators.

### Structured layer — `data/final/knowledge_base.sqlite` (`src/database/`)
Typed SQLite over the cleaned, standardized and entity-resolved tables, with indexes and
views (`v_hotels`, `v_places`, `v_entity_canonical`, `v_reviews_resolved`). Answers exact
predicates — *"hotels in Riyadh under 500 SAR with guest rating ≥ 8"* — via a small query
API (`src.database.kb`: `find_hotels`, `find_places`, `find_events`, …). `embed=False`
statistics/indicators live here only. Build: `python -m src.database.build_sqlite`.

### Vector layer — `data/final/vector_store/` (`src/vector_store/`)
Multilingual embeddings (default `intfloat/multilingual-e5-base`; Arabic + English) of the
**`embed=True`** KB documents (13,920: places, reviews, hotels, entertainment). Answers
meaning-based queries — *"places suitable for someone into traditional Saudi culture"* —
via `src.vector_store.search` (`semantic_search`, `hybrid_search`). Build:
`python -m src.vector_store.build_index`.

### How they combine
- **Structured retrieval** → hard filters (budget, capacity, dates, city) the Verifier
  checks deterministically.
- **Semantic retrieval** → subjective/thematic matching over review & description text.
- **Hybrid** → metadata pre-filter (structured) then semantic ranking; every result
  resolves to a `canonical_id` and `source_url` for evidence grounding.

> Both `.sqlite` and the vector index are **regenerable build artifacts** (git-ignored);
> rebuild them from the processed/standardized CSVs with the two build commands above.
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
```
RAW DATA
   ↓
QUALITY ASSESSMENT
"What problems are here?"
   ↓
 CLEANING
"Fix the problems."
   ↓
 STANDARDIZATION
"Make all datasets use compatible structures."
   ↓
 ENTITY RESOLUTION
"Which records refer to the same real-world thing?"
   ↓
 KNOWLEDGE BASE
"Store it so the AI can retrieve it."
   ↓
 ┌──────────────────────┐
 │                      │
Structured          Semantic
SQLite              Vector Store
 │                      │
Exact facts          Meaning/evidence
 │                      │
dates                reviews
prices               descriptions
ratings              preferences
coordinates          contextual text
```
