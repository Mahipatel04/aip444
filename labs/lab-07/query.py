# query.py - Test retrieval against the ChromaDB collection
# Usage: python query.py "How do I read a file?"

import os
import sys
import requests
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Load API key
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Set up embedding function
openai_ef = OpenAIEmbeddingFunction(
    api_key=os.environ["OPENROUTER_API_KEY"],
    model_name="openai/text-embedding-3-small",
    api_base="https://openrouter.ai/api/v1",
)

# Connect to ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection(
    name="node-docs",
    embedding_function=openai_ef,
)


def rerank(query: str, candidates: list, top_n: int = 5) -> list:
    """Reranks candidates using Cohere reranker via OpenRouter."""
    documents = [c["document"] for c in candidates]

    response = requests.post(
        "https://openrouter.ai/api/v1/rerank",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": "cohere/rerank-v3.5",
            "query": query,
            "documents": documents,
            "top_n": top_n,
        },
    )

    data = response.json()

    return [
        {
            **candidates[r["index"]],
            "rerank_score": r["relevance_score"],
        }
        for r in data["results"]
    ]


def query_docs(query: str):
    print(f"\n🔎 Query: '{query}'")
    print("=" * 60)

    # Step 1: Query ChromaDB for top 25 results
    results = collection.query(
        query_texts=[query],
        n_results=25,
        include=["documents", "metadatas", "distances"]
    )

    # Step 2: Build candidates list
    candidates = []
    for i in range(len(results["ids"][0])):
        # Convert distance to similarity (cosine distance = 1 - similarity)
        distance = results["distances"][0][i]
        similarity = 1 - distance

        candidates.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "chroma_similarity": similarity,
            "chroma_rank": i + 1,
        })

    print(f"📦 ChromaDB returned {len(candidates)} candidates")

    # Step 3: Rerank top 25 to get top 5
    print("🔄 Reranking...")
    reranked = rerank(query, candidates, top_n=5)

    # Step 4: Print results
    print(f"\n✅ Top {len(reranked)} results after reranking:\n")
    for i, result in enumerate(reranked, 1):
        breadcrumb = result["metadata"]["breadcrumb"]
        source = result["metadata"]["source"]
        chroma_rank = result["chroma_rank"]
        chroma_sim = result["chroma_similarity"]
        rerank_score = result["rerank_score"]

        print(f"{i}. [Rerank: {rerank_score:.3f} | Vector: {chroma_sim:.3f} | Was rank #{chroma_rank}]")
        print(f"   📄 {source} — {breadcrumb}")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query.py \"your question here\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    query_docs(query)