# search.py - Interactive semantic search CLI
# Loads the product database and lets you search using natural language
# Uses vector embeddings + reranking for accurate results

from utils import load_database, search_products

def main():
    print("🔍 Semantic Product Search Engine")
    print("=" * 40)

    # Load products and embeddings from disk
    print("📂 Loading database...")
    products = load_database()
    print(f"   ✅ Loaded {len(products)} products\n")

    print("Type your search query, or 'quit' to exit.\n")

    # Interactive search loop
    while True:
        query = input("What are you looking for? > ").strip()

        if not query:
            continue

        if query.lower() in ["quit", "exit", "q"]:
            print("👋 Goodbye!")
            break

        print(f"\n🔎 Searching for: '{query}'...")

        results = search_products(query, products)

        if not results:
            print("❌ I'm sorry, we don't have anything like that in stock.\n")
            continue

        print(f"\n✅ Found {len(results)} matches:\n")
        for i, product in enumerate(results, 1):
            rerank = product.get("rerank_score", 0)
            vector = product.get("vector_score", 0)
            title = product.get("title", "Unknown")
            price = product.get("price", 0)
            category = product.get("category", "")
            print(f"{i}. [Rerank: {rerank:.2f} | Vector: {vector:.2f}] {title} - ${price:.2f} ({category})")

        print()

if __name__ == "__main__":
    main()