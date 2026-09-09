"""Database stage.

Embeds cleaned documents and persists them in a vector store so the retrieval
stage can perform semantic search. The concrete backend (e.g. Chroma, FAISS,
pgvector) is hidden behind :class:`~src.database.vector_store.VectorStore`.
"""
