# ask_node.py - Full RAG CLI application
# Usage: python ask_node.py "How do I read a file?"
# Retrieves relevant Node.js docs and uses LLM to answer

import os
import sys
import requests
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from openai import OpenAI

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

# Set up OpenAI client for LLM calls
llm_client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

# Set up embedding function
openai_ef = OpenAIEmbeddingFunction(
    api_key=os.environ["OPENROUTER_API_KEY"],
    model_name="openai/text-embedding-3-small",
    api_base="https://openrouter.ai/api/v1",
)

# Connect to ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(
    name="node-docs",
    embedding_function=openai_ef,
)

LLM_MODEL = "google/gemini-2.5-flash-lite"


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
        {**candidates[r["index"]], "rerank_score": r["relevance_score"]}
        for r in data["results"]
    ]


def retrieve_context(question: str) -> list:
    """Retrieves and reranks the most relevant doc chunks."""

    # Step 1: Query ChromaDB for top 25
    results = collection.query(
        query_texts=[question],
        n_results=25,
        include=["documents", "metadatas", "distances"]
    )

    # Step 2: Build candidates
    candidates = []
    for i in range(len(results["ids"][0])):
        candidates.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "chroma_rank": i + 1,
        })

    # Step 3: Rerank to get top 5
    return rerank(question, candidates, top_n=5)


def build_prompt(question: str, chunks: list) -> str:
    """Builds the RAG system prompt with retrieved context."""

    # Format each chunk as an XML doc tag
    context_docs = ""
    for chunk in chunks:
        source = chunk["metadata"]["source"]
        breadcrumb = chunk["metadata"]["breadcrumb"]
        content = chunk["document"]
        context_docs += f'  <doc source="{source}" breadcrumb="{breadcrumb}">\n{content}\n  </doc>\n\n'

    return f"""You are ask-node, an expert Node.js assistant that answers questions about Node.js APIs.

Here is some context from the official Node.js documentation:

<context>
{context_docs}</context>

Instructions:
1. Answer the user's question based ONLY on the provided context.
2. If the answer is not in the context, say "I don't have enough information to answer that."
3. Cite the source file(s) (e.g., fs.md) for your information.
4. Be clear and concise. Include code examples when relevant.
""".strip()


def ask(question: str):
    """Main RAG function — retrieves context and generates answer."""

    print(f"\n❓ Question: {question}", file=sys.stderr)
    print("🔍 Retrieving relevant docs...", file=sys.stderr)

    # Retrieve relevant chunks
    chunks = retrieve_context(question)

    # Print sources to stderr for transparency
    print(f"\n📚 Sources used:", file=sys.stderr)
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"]["source"]
        breadcrumb = chunk["metadata"]["breadcrumb"]
        rerank_score = chunk.get("rerank_score", 0)
        print(f"   {i}. [{rerank_score:.3f}] {source} — {breadcrumb}", file=sys.stderr)

    print("\n🤖 Generating answer...\n", file=sys.stderr)

    # Build prompt with context
    system_prompt = build_prompt(question, chunks)

    # Call LLM
    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content

    # Print answer to stdout
    print(answer)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ask_node.py \"your question here\"")
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    ask(question)