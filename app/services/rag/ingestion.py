import asyncio
from app.utils.pdf_extractor import extract_text_from_pdf
from app.services.rag.chunker import chunk_by_day, chunk_text_generic
from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store
from app.db.supabase import supabase_admin


async def ingest_book(book_id: str, use_day_chunking: bool = False) -> dict:
    """
    Full RAG ingestion pipeline for ORIINU.AI.

    The API persists the PDF before scheduling ingestion, so this pipeline always
    reads from the durable storage object.
    """
    try:
        supabase_admin.table("books").update({"ingestion_status": "processing"}).eq(
            "id", book_id
        ).execute()

        book_res = (
            supabase_admin.table("books")
            .select("storage_path")
            .eq("id", book_id)
            .limit(1)
            .execute()
        )
        if not book_res or not book_res.data or len(book_res.data) == 0:
            raise ValueError(f"Book with ID {book_id} not found.")
        storage_path = book_res.data[0]["storage_path"]

        file_bytes = supabase_admin.storage.from_("book-pdfs").download(storage_path)

        text = extract_text_from_pdf(file_bytes)
        if not text:
            raise ValueError("No extractable text found in PDF.")

        if use_day_chunking:
            day_chunks = chunk_by_day(text)
            if len(day_chunks) < 10:
                print(
                    f"Warning: Only {len(day_chunks)} day chunks found. Falling back to word chunking."
                )
                chunk_contents = chunk_text_generic(text)
                chunk_metadata = [{"chunk_type": "word_count"} for _ in chunk_contents]
                chunk_indices = list(range(len(chunk_contents)))
            else:
                chunk_contents = [c["content"] for c in day_chunks]
                chunk_metadata = [
                    {
                        "day_number": c["day_number"],
                        "law_name": c["law_name"],
                        "chunk_type": "day_entry",
                    }
                    for c in day_chunks
                ]
                chunk_indices = [c["day_number"] for c in day_chunks]
        else:
            chunk_contents = chunk_text_generic(text, chunk_size=512, overlap=50)
            chunk_metadata = [{"chunk_type": "word_count"} for _ in chunk_contents]
            chunk_indices = list(range(len(chunk_contents)))

        batch_size = 20
        all_embeddings = []

        for i in range(0, len(chunk_contents), batch_size):
            batch = chunk_contents[i : i + batch_size]

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    embeddings = embedder.embed_texts(batch)
                    all_embeddings.extend(embeddings)
                    print(
                        f"Embedded {min(i + batch_size, len(chunk_contents))}/{len(chunk_contents)} chunks..."
                    )
                    break
                except Exception as e:
                    if (
                        "429" in str(e)
                        or "quota" in str(e).lower()
                        or "exhausted" in str(e).lower()
                    ):
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 30  # 30s, 60s, 90s
                            print(
                                f"Rate limit hit. Retrying in {wait_time}s (Attempt {attempt + 1}/{max_retries})..."
                            )
                            await asyncio.sleep(wait_time)
                            continue
                    raise e

            if i + batch_size < len(chunk_contents):
                await asyncio.sleep(15)

        print(f"Generated embeddings for all {len(chunk_contents)} chunks.")

        await vector_store.delete_book_chunks(book_id)
        await vector_store.upsert_chunks(
            book_id=book_id,
            chunks=chunk_contents,
            embeddings=all_embeddings,
            metadata_list=chunk_metadata,
            chunk_indices=chunk_indices,
        )

        print(f"Upserted all chunks into vector store for book ID {book_id}.")

        supabase_admin.table("books").update(
            {
                "ingestion_status": "ready",
                "chunk_count": len(chunk_contents),
                "ingested_at": "now()",
                "published": True,
            }
        ).eq("id", book_id).execute()

        return {"status": "success", "chunks": len(chunk_contents)}

    except Exception as e:
        supabase_admin.table("books").update({"ingestion_status": "failed"}).eq(
            "id", book_id
        ).execute()
        raise e
