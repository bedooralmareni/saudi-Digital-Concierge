import chromadb

client = chromadb.PersistentClient(
    path="data/knowledge_base/vector_store"
)

collection = client.get_collection("saudi_concierge")

query = "family-friendly activities in Riyadh"

results = collection.query(
    query_texts=[query],
    n_results=5
)

print("QUERY:")
print(query)

print("\nRETRIEVED DOCUMENTS:")
for i, doc in enumerate(results["documents"][0]):
    metadata = results["metadatas"][0][i]
    distance = results["distances"][0][i]

    print(f"\n--- Result {i+1} ---")
    print(f"Distance: {distance:.4f}")
    print(f"Type: {metadata.get('entity_type')}")
    print(f"City: {metadata.get('city')}")
    print(f"Source: {metadata.get('source')}")
    print(f"Text: {doc[:300]}")