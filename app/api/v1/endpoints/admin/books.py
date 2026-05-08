from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.services.rag.ingestion import ingest_book

router = APIRouter()


@router.post("/books/upload")
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled Book",
    author: str = "",
    use_day_chunking: bool = True,
    _: dict = Depends(require_admin),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    storage_path = f"books/{file.filename}"
    supabase_admin.storage.from_("book-pdfs").upload(storage_path, file_bytes)

    book = supabase_admin.table("books").insert({
        "title": title,
        "author": author,
        "storage_path": storage_path,
        "ingestion_status": "pending",
    }).execute()
    book_id = book.data[0]["id"]

    background_tasks.add_task(ingest_book, book_id, file_bytes, use_day_chunking)

    return {
        "book_id": book_id,
        "status": "ingestion_started",
        "chunking_mode": "day_entry" if use_day_chunking else "word_count",
    }


@router.get("/books")
async def list_books(_: dict = Depends(require_admin)):
    return supabase_admin.table("books").select("*").order("created_at", desc=True).execute().data


@router.delete("/books/{book_id}")
async def delete_book(book_id: str, _: dict = Depends(require_admin)):
    supabase_admin.table("books").delete().eq("id", book_id).execute()
    return {"deleted": True}
