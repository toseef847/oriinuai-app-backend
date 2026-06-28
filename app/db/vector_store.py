from typing import List
from postgrest import AsyncPostgrestClient

from app.db.supabase import get_async_admin_client


class VectorStore:
    """
    Supabase pgvector wrapper.
    Dimension: 768 (Google gemini-embedding-2).
    """

    async def upsert_chunks(
        self,
        book_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata_list: List[dict] = None,
        chunk_indices: List[int] = None,
    ) -> None:
        metadata_list = metadata_list or [{} for _ in chunks]
        chunk_indices = chunk_indices or list(range(len(chunks)))

        client = await get_async_admin_client()

        rows = [
            {
                "book_id": book_id,
                "content": chunk,
                "embedding": embedding,
                "metadata": meta,
                "chunk_index": idx,
            }
            for chunk, embedding, meta, idx in zip(
                chunks, embeddings, metadata_list, chunk_indices
            )
        ]
        for i in range(0, len(rows), 50):
            await client.table("book_chunks").insert(rows[i : i + 50]).execute()

    async def similarity_search(
        self,
        client: AsyncPostgrestClient,
        query_embedding: List[float],
        top_k: int = 5,
        book_id: str = None,
    ) -> List[dict]:
        result = await client.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "filter_book_id": book_id,
            },
        ).execute()
        return result.data or []

    async def delete_book_chunks(self, book_id: str) -> None:
        client = await get_async_admin_client()
        await client.table("book_chunks").delete().eq("book_id", book_id).execute()


vector_store = VectorStore()
