import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from postgrest.exceptions import APIError
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.services.rag.ingestion import ingest_book
from app.utils.response import api_success

router = APIRouter()


@router.post("/books/upload")
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled Book",
    author: str = "",
    use_day_chunking: bool = False,
    _: dict = Depends(require_admin),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    
    # Compute SHA-256 hash of the file
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check if book already exists by hash
    existing_book = supabase_admin.table("books").select("id, title, ingestion_status").eq("file_hash", file_hash).limit(1).execute()
    if existing_book and existing_book.data and len(existing_book.data) > 0:
        book_data = existing_book.data[0]
        return api_success(
            data={
                "book_id": book_data["id"],
                "status": "already_exists",
                "ingestion_status": book_data["ingestion_status"]
            },
            message=f"Book already exists (Title: {book_data['title']})"
        )

    # Step 1: Create DB record first (so we can return ID immediately)
    book_data = {
        "title": title,
        "author": author,
        "file_hash": file_hash,
        "storage_path": f"books/{file.filename}",
        "ingestion_status": "pending",
    }
    
    book = supabase_admin.table("books").insert(book_data).execute()
    book_id = book.data[0]["id"]

    # Step 2: Handoff everything else to background
    # We pass file_bytes so ingestion doesn't need to wait for storage upload
    background_tasks.add_task(ingest_book, book_id, file_bytes, use_day_chunking)

    return api_success(
        data={
            "book_id": book_id,
            "status": "ingestion_started",
            "chunking_mode": "word_count",
        }, 
        message="Book record created. Upload and ingestion continuing in background."
    )


@router.get("/books")
async def list_books(_: dict = Depends(require_admin)):
    data = supabase_admin.table("books").select("*").order("created_at", desc=True).execute().data
    return api_success(data=data, message="Books retrieved successfully")


@router.post("/books/{book_id}/ingest")
async def trigger_ingestion(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    use_day_chunking: bool = False,
    _: dict = Depends(require_admin),
):
    """
    Manually re-trigger RAG ingestion for an existing book.
    Useful for retrying failed ingestions.
    """
    try:
        # Check if book exists
        result = supabase_admin.table("books").select("id, ingestion_status").eq("id", str(book_id)).limit(1).execute()
        
        if not result or not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Book not found.")

        book = result.data[0]

        # Prevent concurrent ingestion if already processing
        if book["ingestion_status"] == "processing":
            raise HTTPException(status_code=400, detail="Book is already being processed.")

        background_tasks.add_task(ingest_book, str(book_id), None, use_day_chunking)

        return api_success(
            message="Ingestion process re-triggered successfully",
            data={"book_id": str(book_id), "status": "processing"}
        )
    except APIError as e:
        # Handle cases where Postgrest might fail
        raise HTTPException(status_code=400, detail=f"Database error: {e.message}")


@router.delete("/books/{book_id}")
async def delete_book(book_id: UUID, _: dict = Depends(require_admin)):
    # 1. Get storage path first
    result = supabase_admin.table("books").select("storage_path").eq("id", str(book_id)).limit(1).execute()
    
    if result and result.data and len(result.data) > 0:
        storage_path = result.data[0]["storage_path"]
        # 2. Delete from storage (don't fail if already gone)
        try:
            supabase_admin.storage.from_("book-pdfs").remove([storage_path])
        except Exception:
            pass

    # 3. Delete from DB
    supabase_admin.table("books").delete().eq("id", str(book_id)).execute()
    
    return api_success(data={"deleted": True}, message="Book and its storage file deleted successfully")
