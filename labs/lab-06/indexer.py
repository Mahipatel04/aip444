# indexer.py - Fetches product data, embeds it, and saves to disk
# Run this ONCE to generate products.json, vectors.tsv, and metadata.tsv
# After running, you can use search.py to search the index

import json
import requests
from openai import OpenAI
from utils import serialize_product, load_env, client

print("🚀 Starting indexer...")

# ─────────────────────────────────────────────
# STEP 1: FETCH PRODUCTS FROM DUMMYJSON API
# ─────────────────────────────────────────────

print("📦 Fetching products from DummyJSON API...")
response = requests.get("https://dummyjson.com/products?limit=200")
data = response.json()
products = data["products"]
print(f"   ✅ Fetched {len(products)} products")


# ─────────────────────────────────────────────
# STEP 2: SAVE PRODUCTS.JSON
# The full product database saved to disk
# ─────────────────────────────────────────────

with open("products.json", "w", encoding="utf-8") as f:
    json.dump(products, f, indent=2)
print("   ✅ Saved products.json")


# ─────────────────────────────────────────────
# STEP 3: SERIALIZE PRODUCTS
# Convert each product to a clean string for embedding
# This removes noise like SKU, dimensions, QR codes etc.
# ─────────────────────────────────────────────

print("📝 Serializing products...")
serialized = [serialize_product(p) for p in products]
print(f"   ✅ Serialized {len(serialized)} products")
print(f"   Example: {serialized[0][:100]}...")


# ─────────────────────────────────────────────
# STEP 4: EMBED ALL PRODUCTS IN ONE API CALL
# We pass the entire array at once — no loop needed!
# This is much faster and cheaper than one call per product
# ─────────────────────────────────────────────

print("🧠 Generating embeddings (this may take a moment)...")
embedding_response = client.embeddings.create(
    model="openai/text-embedding-3-small",
    input=serialized,
)
embeddings = [item.embedding for item in embedding_response.data]
print(f"   ✅ Generated {len(embeddings)} embeddings")
print(f"   Vector dimensions: {len(embeddings[0])}")


# ─────────────────────────────────────────────
# STEP 5: SAVE VECTORS.TSV
# Each line = one product's embedding vector
# Numbers separated by tabs
# Line 1 = Product 1, Line 2 = Product 2, etc.
# ─────────────────────────────────────────────

print("💾 Saving vectors.tsv...")
with open("vectors.tsv", "w", encoding="utf-8") as f:
    for vector in embeddings:
        line = "\t".join(str(x) for x in vector)
        f.write(line + "\n")
print("   ✅ Saved vectors.tsv")


# ─────────────────────────────────────────────
# STEP 6: SAVE METADATA.TSV
# Special file for TensorFlow Embedding Projector visualization
# Must have a header row: Title\tCategory
# Tabs and newlines in data must be removed or they break the TSV format
# ─────────────────────────────────────────────

print("📊 Saving metadata.tsv...")
with open("metadata.tsv", "w", encoding="utf-8") as f:
    # Header row required by TensorFlow Projector
    f.write("Title\tCategory\n")
    for product in products:
        # Sanitize: remove tabs and newlines from title and category
        title = product["title"].replace("\t", " ").replace("\n", " ")
        category = product["category"].replace("\t", " ").replace("\n", " ")
        f.write(f"{title}\t{category}\n")
print("   ✅ Saved metadata.tsv")

print("\n🎉 Indexing complete!")
print("   Files created: products.json, vectors.tsv, metadata.tsv")
print("   Now run: python search.py")