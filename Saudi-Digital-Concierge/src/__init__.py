"""Saudi Digital Concierge — source package.

A retrieval-augmented (RAG) assistant for tourism in Saudi Arabia. The package
is organised as a linear data pipeline followed by a retrieval/agent layer:

    ingestion  ->  cleaning  ->  database  ->  retrieval  ->  agents

Each sub-package owns one stage and exposes a small, documented interface so the
stages can be developed and tested in isolation.
"""

__version__ = "0.1.0"
