# Saudi Digital Concierge

A retrieval-augmented (RAG) AI concierge for tourism in Saudi Arabia. It will
ingest open data about places, reviews, events, entertainment and tourism
statistics, clean and embed it into a vector store, and answer visitor
questions in Arabic or English with grounded context.

## Project structure

```
Saudi-Digital-Concierge/
├── data/
│   ├── raw/                  # unmodified source data
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

> Note: empty folders are kept under version control with `.gitkeep` files.
