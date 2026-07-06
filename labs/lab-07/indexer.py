# indexer.py - Reads all markdown docs, chunks them, and stores in ChromaDB
# Run this ONCE to build the vector database
# Uses OpenRouter's text-embedding-3-small for embeddings

import os
import glob
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from chunker import chunk_markdown

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

# Custom embedding function using OpenRouter
openai_ef = OpenAIEmbeddingFunction(
    api_key=os.environ["OPENROUTER_API_KEY"],
    model_name="openai/text-embedding-3-small",
    api_base="https://openrouter.ai/api/v1",
)

# PersistentClient saves the database to disk automatically
# No need to run a separate server!
client = chromadb.PersistentClient(path="./chroma_db")

def main():
    print("🚀 Starting indexer...")

    # 1. Create or get the collection
    collection = client.get_or_create_collection(
        name="node-docs",
        embedding_function=openai_ef,
        configuration={
            "hnsw": {
                "space": "cosine",
            }
        },
    )

    # 2. Read all markdown files from docs/ folder
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    files = glob.glob(os.path.join(docs_dir, "*.md"))
    print(f"📂 Found {len(files)} markdown files")

    total_chunks = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        print(f"   Processing {filename}...")

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        # 3. Chunk the markdown file
        chunks = chunk_markdown(text, filename)

        if len(chunks) == 0:
            continue

        # 4. Add chunks to ChromaDB
        # ChromaDB will automatically embed them using our embedding function
        ids = [c["id"] for c in chunks]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Use upsert so it's safe to run multiple times
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)

    print(f"\n✅ Indexing complete!")
    print(f"   Total chunks indexed: {total_chunks}")
    print(f"   Collection size: {collection.count()}")

if __name__ == "__main__":
    main()