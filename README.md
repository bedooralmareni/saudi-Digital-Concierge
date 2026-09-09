# Saudi Digital Concierge

A retrieval-augmented (RAG) AI concierge for tourism in Saudi Arabia. It will
ingest open data about places, reviews, events, entertainment and tourism
statistics, clean and embed it into a vector store, and answer visitor
questions in Arabic or English with grounded context.

## Data sources

| # | Source | What we'll use it for | Lands in |
| - | ------ | --------------------- | -------- |
| 1 | **Saudi Tourism Reviews — Zenodo** | Arabic tourist reviews + sentiment/preferences | `data/raw/tourism_reviews/` |
| 2 | **Riyadh Places 8.8K — Kaggle** | POIs, categories, ratings, coordinates | `data/raw/riyadh_places/` |
| 3 | **Saudi Tourism Dataset 2015–2024 — Kaggle** | Tourism demand, spending, overnight stays | `data/raw/tourism_statistics/` |
| 4 | **DataSaudi — Tourism Indicators** | Official tourism statistics | `data/raw/tourism_statistics/` |
| 5 | **Enjoy.sa Events API** | Events, dates, times, city, family/gender constraints | `data/raw/events/` |
| 6 | **SaudiTourism — Hugging Face** | Supplementary tourism info: attractions, hotels, restaurants, events, transportation, etc. | `data/raw/huggingface/` |
| 7 | **Entertainment in Saudi Arabia — Kaggle** | Entertainment places, ratings, categories, locations | `data/raw/entertainment/` |

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
