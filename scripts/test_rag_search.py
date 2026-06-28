import asyncio
from dotenv import load_dotenv
from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store
from app.db.supabase import get_async_admin_client

load_dotenv()


async def test_search():
    print("--- TESTING SIMILARITY SEARCH ---")

    query = input("\nEnter your question for ORIINU: ").strip()
    if not query:
        print("Empty query. Exiting.")
        return

    # 2. Embed the query
    print("\nEmbedding query...")
    query_vec = embedder.embed_query(query)

    # 3. Search for matches
    print("Searching vector store...")
    try:
        client = await get_async_admin_client()
        chunks = await vector_store.similarity_search(client, query_vec, top_k=3)

        if not chunks:
            print(
                "❌ No matching chunks found. Make sure the book is ingested and the 'match_chunks' function exists in Supabase."
            )
            return

        # 4. Show results
        print(f"Found {len(chunks)} matches:\n")
        for i, chunk in enumerate(chunks):
            # The RPC match_chunks usually returns a 'similarity' score
            # similarity is usually 1 - distance
            score = chunk.get("similarity")
            content = chunk.get("content", "")[:200].replace("\n", " ") + "..."
            metadata = chunk.get("metadata", {})
            print(f"MATCH {i+1} [Similarity: {score:.4f}]:")
            print(f"Content: {content}")
            if metadata:
                print(f"Metadata: {metadata}")
            print("-" * 30)

    except Exception as e:
        print(f"❌ Error during search: {e}")
        print("\nEnsure you have run the 'match_chunks' SQL function in Supabase.")


if __name__ == "__main__":
    asyncio.run(test_search())

# Run examplpe: PYTHONPATH=. python3 scripts/test_rag_search.py
