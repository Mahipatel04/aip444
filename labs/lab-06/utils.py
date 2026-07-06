# utils.py - Shared helper functions for the semantic search engine
# Contains: product serialization, dot product math,
# database loading, search, and reranking functions

import json
import os
import requests
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

# Set up OpenAI client pointing to OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


# ─────────────────────────────────────────────
# SERIALIZE PRODUCT
# Converts a raw product dict into a clean string for embedding
# We only keep the fields that matter for search
# ─────────────────────────────────────────────

def serialize_product(product: dict) -> str:
    title = product.get("title", "")
    category = product.get("category", "")
    description = product.get("description", "")
    tags = ", ".join(product.get("tags", []))
    brand = product.get("brand", "")

    return f"Title: {title} | Category: {category} | Description: {description} | Tags: {tags} | Brand: {brand}"


# ─────────────────────────────────────────────
# DOT PRODUCT
# Since OpenAI embeddings are normalized, dot product = cosine similarity
# Returns a score between -1 and 1 (higher = more similar)
# ─────────────────────────────────────────────

def dot_product(vec_a: list[float], vec_b: list[float]) -> float:
    return sum(a * b for a, b in zip(vec_a, vec_b))


# ─────────────────────────────────────────────
# LOAD DATABASE
# Loads products.json and vectors.tsv and zips them together
# so each product has its embedding attached
# ─────────────────────────────────────────────

def load_database() -> list[dict]:
    # Read products JSON
    with open("products.json", "r", encoding="utf-8") as f:
        products = json.load(f)

    # Read vectors TSV
    with open("vectors.tsv", "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")

    # Zip products and vectors together
    products_with_embeddings = []
    for product, line in zip(products, lines):
        vector = [float(x) for x in line.split("\t")]
        product["embedding"] = vector
        products_with_embeddings.append(product)

    return products_with_embeddings


# ─────────────────────────────────────────────
# EMBED TEXT
# Sends text to OpenAI embedding model and returns the vector
# ─────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model="openai/text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


# ─────────────────────────────────────────────
# RERANK RESULTS
# Uses Cohere reranker to re-score and reorder candidates
# More accurate than vector search alone
# ─────────────────────────────────────────────

def rerank_results(query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
    # Serialize each candidate into a document string
    documents = [serialize_product(p) for p in candidates]

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

    # Map results back to product objects with rerank score attached
    return [
        {**candidates[r["index"]], "rerank_score": r["relevance_score"]}
        for r in data["results"]
    ]


# ─────────────────────────────────────────────
# SEARCH PRODUCTS
# Main search function:
# 1. Embed the query
# 2. Dot product against all products
# 3. Filter by threshold
# 4. Take top 20 candidates
# 5. Rerank and return top 5
# ─────────────────────────────────────────────

# Minimum similarity score — anything below this is ignored
MIN_SIMILARITY_SCORE = 0.25

def search_products(query: str, products: list[dict], min_score: float = MIN_SIMILARITY_SCORE) -> list[dict]:
    # Step 1: Embed the query
    query_vector = embed_text(query)

    # Step 2: Calculate dot product against all products
    scored = []
    for product in products:
        score = dot_product(query_vector, product["embedding"])
        scored.append({**product, "vector_score": score})

    # Step 3: Sort by score descending
    scored.sort(key=lambda x: x["vector_score"], reverse=True)

    # Step 4: Filter out anything below min_score
    filtered = [p for p in scored if p["vector_score"] >= min_score]

    # Step 5: Take top 20 candidates (wider net for reranker)
    candidates = filtered[:20]

    # Step 6: If no candidates found, return empty list
    if not candidates:
        return []

# Step 7: Rerank candidates and return top 5
    reranked = rerank_results(query, candidates, top_n=5)
    
    # Filter out results with very low rerank scores
    # This prevents returning irrelevant results
    return [r for r in reranked if r.get("rerank_score", 0) >= 0.05]