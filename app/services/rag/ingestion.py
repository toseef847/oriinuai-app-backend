from app.utils.pdf_extractor import extract_text_from_pdf
from app.services.rag.chunker import chunk_by_day, chunk_text_generic
from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store
from app.db.supabase import supabase_admin


async def ingest_book(book_id: str, file_bytes: bytes, use_day_chunking: bool = True) -> dict:
    """
    Full RAG ingestion pipeline for ORIINU.AI books.

    For '365 African Proverbs': use_day_chunking=True (default)
      → 365 chunks, one per daily law, perfect semantic units

    For future books without daily structure: use_day_chunking=False
      → Falls back to generic 512-word overlapping chunks

    Called as a FastAPI BackgroundTask after admin PDF upload.
    """
    try:
        supabase_admin.table("books").update(
            {"ingestion_status": "processing"}
        ).eq("id", book_id).execute()

        text = extract_text_from_pdf(file_bytes)
        if not text:
            raise ValueError("No extractable text found in PDF.")

        if use_day_chunking:
            day_chunks = chunk_by_day(text)
            if len(day_chunks) < 10:
                print(f"Warning: Only {len(day_chunks)} day chunks found. Falling back to generic chunking.")
                chunk_contents = chunk_text_generic(text)
                chunk_metadata = [{"chunk_type": "generic"} for _ in chunk_contents]
                chunk_indices = list(range(len(chunk_contents)))
            else:
                chunk_contents = [c["content"] for c in day_chunks]
                chunk_metadata = [
                    {"day_number": c["day_number"], "law_name": c["law_name"], "chunk_type": "day_entry"}
                    for c in day_chunks
                ]
                chunk_indices = [c["day_number"] for c in day_chunks]
        else:
            chunk_contents = chunk_text_generic(text)
            chunk_metadata = [{"chunk_type": "generic"} for _ in chunk_contents]
            chunk_indices = list(range(len(chunk_contents)))

        all_embeddings = []
        for i, chunk in enumerate(chunk_contents):
            embedding = embedder.embed_query(chunk)
            all_embeddings.append(embedding)
            if (i + 1) % 10 == 0:
                print(f"Embedded {i + 1}/{len(chunk_contents)} chunks...")

        await vector_store.delete_book_chunks(book_id)
        await vector_store.upsert_chunks(
            book_id=book_id,
            chunks=chunk_contents,
            embeddings=all_embeddings,
            metadata_list=chunk_metadata,
            chunk_indices=chunk_indices,
        )

        supabase_admin.table("books").update({
            "ingestion_status": "ready",
            "chunk_count": len(chunk_contents),
            "ingested_at": "now()",
        }).eq("id", book_id).execute()

        return {"status": "success", "chunks": len(chunk_contents)}

    except Exception as e:
        supabase_admin.table("books").update(
            {"ingestion_status": "failed"}
        ).eq("id", book_id).execute()
        raise e
