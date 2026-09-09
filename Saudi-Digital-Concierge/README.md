# Saudi Digital Concierge

A retrieval-augmented (RAG) AI concierge for tourism in Saudi Arabia. It ingests
open data about places, reviews, events, entertainment and tourism statistics,
cleans and embeds it into a vector store, and answers visitor questions in
Arabic or English with grounded, cited context.

## Pipeline

```
ingestion  ->  cleaning  ->  database  ->  retrieval  ->  agents
   raw           tidy       embeddings     top-k         answers
```

## Project structure

```
Saudi-Digital-Concierge/
├── data/
│   ├── raw/                  # unmodified source data (git-ignored contents)
│   │   ├── tourism_reviews/
│   │   ├── riyadh_places/
│   │   ├── tourism_statistics/
│   │   ├── entertainment/
│   │   ├── huggingface/
│   │   └── events/
│   ├── processed/            # cleaned, normalised data
│   └── final/                # embeddings / vector store artefacts
│
├── notebooks/                # exploration & prototyping
│
├── src/
│   ├── ingestion/            # load raw sources into a uniform format
│   ├── cleaning/             # normalise text (whitespace, Arabic diacritics, ...)
│   ├── database/             # embed & persist to a vector store
│   ├── retrieval/            # semantic search over stored chunks
│   └── agents/               # RAG question-answering agent
│
├── evaluation/               # metrics & test harness
├── tests/                    # unit tests (pytest)
└── README.md
```

## Getting started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env   # then fill in your keys

# 4. Run the tests
pytest
```

## How the pieces fit together

- **`src/ingestion`** — `BaseLoader` defines a common interface; add one loader
  per source under `data/raw/*` that yields `Document` objects.
- **`src/cleaning`** — `clean_text` normalises Unicode, strips Arabic diacritics
  and collapses whitespace before embedding.
- **`src/database`** — `VectorStore` is a backend-agnostic interface (Chroma,
  FAISS, pgvector, ...); it stores embeddings and does similarity search.
- **`src/retrieval`** — `Retriever` wraps a `VectorStore` and returns
  prompt-ready context for a query.
- **`src/agents`** — `ConciergeAgent` combines retrieved context with an LLM
  (any `generate` callable) to produce grounded answers.
- **`evaluation`** — run question sets through an agent and score the answers.

## Notes

- Contents of `data/raw`, `data/processed` and `data/final` are git-ignored;
  the folders are kept via `.gitkeep`. Commit small samples only if needed.
- Never commit real API keys — use `.env` (git-ignored).
