import hashlib
import logging
from uuid import UUID, uuid4
from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    BackgroundTasks,
    HTTPException,
    Query,
)
from pydantic import BaseModel
from postgrest.exceptions import APIError
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.services.rag.ingestion import ingest_book
from app.utils.response import api_success
from app.core.config import settings
from app.utils.uploads import read_upload_with_limit

router = APIRouter()
logger = logging.getLogger(__name__)

BOOK_PDF_BUCKET = "book-pdfs"


class IngestBookPayload(BaseModel):
    use_day_chunking: bool = False


class UpdateBookStatusPayload(BaseModel):
    published: bool


def _log_admin_action(
    admin_id: str, action: str, target_type: str, target_id: str, metadata: dict = None
):
    try:
        supabase_admin.table("admin_logs").insert(
            {
                "admin_id": admin_id,
                "action": action,
                "target_type": target_type,
                "target_id": target_id,
                "metadata": metadata or {},
            }
        ).execute()
    except Exception as e:
        print(f"Failed to log admin action: {e}")


@router.get("/books/dashboard")
async def books_dashboard(admin: dict = Depends(require_admin)):
    # Count books by status
    total_res = supabase_admin.table("books").select("id").execute()
    total_uploaded = len(total_res.data) if total_res.data else 0

    published_res = (
        supabase_admin.table("books")
        .select("id")
        .eq("ingestion_status", "ready")
        .execute()
    )
    total_published = len(published_res.data) if published_res.data else 0

    failed_res = (
        supabase_admin.table("books")
        .select("id")
        .eq("ingestion_status", "failed")
        .execute()
    )
    total_failed = len(failed_res.data) if failed_res.data else 0

    return api_success(
        data={
            "total_books_uploaded": total_uploaded,
            "total_books_published": total_published,
            "total_books_failed": total_failed,
        },
        message="Books dashboard retrieved",
    )


@router.get("/books")
async def list_books(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("all", pattern="^(all|pending|processing|ready|failed)$"),
    admin: dict = Depends(require_admin),
):
    # Build query
    query = supabase_admin.table("books").select("*")

    # Apply status filter
    if status != "all":
        query = query.eq("ingestion_status", status)

    # Get total count before pagination
    total_res = query.execute()
    total = len(total_res.data) if total_res.data else 0

    # Paginate
    offset = (page - 1) * limit
    result = query.order("created_at", desc=True).offset(offset).limit(limit).execute()

    return api_success(
        data={"books": result.data or [], "total": total, "page": page, "limit": limit},
        message="Books retrieved",
    )


@router.post("/books/upload")
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled Book",
    author: str = "",
    use_day_chunking: bool = False,
    admin: dict = Depends(require_admin),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await read_upload_with_limit(
        file,
        settings.MAX_BOOK_UPLOAD_BYTES,
        "Book PDF",
    )

    # Compute SHA-256 hash of the file
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check if book already exists by hash
    existing_book = (
        supabase_admin.table("books")
        .select("id, title, ingestion_status")
        .eq("file_hash", file_hash)
        .limit(1)
        .execute()
    )
    if existing_book and existing_book.data and len(existing_book.data) > 0:
        book_data = existing_book.data[0]
        return api_success(
            data={
                "book_id": book_data["id"],
                "status": "already_exists",
                "ingestion_status": book_data["ingestion_status"],
            },
            message=f"Book already exists (Title: {book_data['title']})",
        )

    book_id = uuid4()
    storage_path = f"books/{book_id}.pdf"

    # Persist the PDF before creating the database record. A successful response
    # therefore guarantees that the book's storage object already exists.
    try:
        supabase_admin.storage.from_(BOOK_PDF_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"},
        )
    except Exception:
        logger.exception("Failed to upload book PDF to Supabase Storage")
        raise HTTPException(
            status_code=502,
            detail="Book storage upload failed. Please try again.",
        )

    book_data = {
        "id": str(book_id),
        "title": title,
        "author": author,
        "file_hash": file_hash,
        "storage_path": storage_path,
        "ingestion_status": "pending",
    }

    try:
        book = supabase_admin.table("books").insert(book_data).execute()
        if not book.data:
            raise RuntimeError("Book insert returned no data")
    except Exception:
        logger.exception("Failed to create database record for uploaded book")
        try:
            supabase_admin.storage.from_(BOOK_PDF_BUCKET).remove([storage_path])
        except Exception:
            logger.exception("Failed to remove book PDF after database insert failure")
        raise HTTPException(
            status_code=500,
            detail="Book record creation failed. Please try again.",
        )

    # Only extraction, chunking, and embedding continue in the background.
    background_tasks.add_task(ingest_book, str(book_id), use_day_chunking)

    # Log action
    _log_admin_action(
        admin_id=admin["id"],
        action="book_uploaded",
        target_type="book",
        target_id=str(book_id),
        metadata={"title": title},
    )

    return api_success(
        data={
            "book_id": book_id,
            "status": "ingestion_started",
            "chunking_mode": "word_count",
        },
        message="Book uploaded. Ingestion continuing in background.",
    )


@router.post("/books/{book_id}/ingest")
async def trigger_ingestion(
    book_id: UUID,
    background_tasks: BackgroundTasks,
    payload: IngestBookPayload | None = None,
    admin: dict = Depends(require_admin),
):
    """
    Manually re-trigger RAG ingestion for an existing book.
    Useful for retrying failed ingestions.
    """
    try:
        # Check if book exists
        result = (
            supabase_admin.table("books")
            .select("id, ingestion_status")
            .eq("id", str(book_id))
            .limit(1)
            .execute()
        )

        if not result or not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Book not found.")

        book = result.data[0]
        status = book["ingestion_status"]

        # Only allow ingestion for books with status: 'pending' or 'failed'
        if status not in ["pending", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot ingest book with status '{status}'. Only pending or failed books can be ingested.",
            )

        # Mark as processing
        supabase_admin.table("books").update({"ingestion_status": "processing"}).eq(
            "id", str(book_id)
        ).execute()

        use_day_chunking = payload.use_day_chunking if payload else False
        background_tasks.add_task(ingest_book, str(book_id), use_day_chunking)

        # Log admin action
        _log_admin_action(
            admin_id=admin["id"],
            action="book_ingest",
            target_type="book",
            target_id=str(book_id),
            metadata={"use_day_chunking": use_day_chunking},
        )

        return api_success(
            message="Ingestion process re-triggered successfully",
            data={"book_id": str(book_id), "status": "processing"},
        )
    except APIError as e:
        raise HTTPException(status_code=400, detail=f"Database error: {e.message}")


@router.put("/books/{book_id}/status")
async def update_book_status(
    book_id: UUID,
    payload: UpdateBookStatusPayload,
    admin: dict = Depends(require_admin),
):
    # Verify book exists
    book_res = (
        supabase_admin.table("books")
        .select("*")
        .eq("id", str(book_id))
        .limit(1)
        .execute()
    )
    if not book_res or not book_res.data or len(book_res.data) == 0:
        raise HTTPException(status_code=404, detail="Book not found")

    book_data = book_res.data[0]
    published = payload.published

    # Only allow publishing if book is ready (ingestion complete)
    if published and book_data.get("ingestion_status") != "ready":
        raise HTTPException(
            status_code=400,
            detail="Cannot publish book that is not ready. Book must complete ingestion first.",
        )

    # Update
    result = (
        supabase_admin.table("books")
        .update({"published": published})
        .eq("id", str(book_id))
        .execute()
    )

    # Log admin action
    _log_admin_action(
        admin_id=admin["id"],
        action="book_published" if published else "book_unpublished",
        target_type="book",
        target_id=str(book_id),
    )

    return api_success(data=result.data[0], message="Book published status updated")


@router.delete("/books/{book_id}")
async def delete_book(book_id: UUID, admin: dict = Depends(require_admin)):
    # Verify book exists
    result = (
        supabase_admin.table("books")
        .select("id, storage_path")
        .eq("id", str(book_id))
        .limit(1)
        .execute()
    )
    if not result or not result.data or len(result.data) == 0:
        raise HTTPException(status_code=404, detail="Book not found")

    storage_path = result.data[0]["storage_path"]

    # Delete from storage (don't fail if already gone)
    try:
        supabase_admin.storage.from_("book-pdfs").remove([storage_path])
    except Exception:
        pass

    # Delete from DB (cascade handles chunks)
    supabase_admin.table("books").delete().eq("id", str(book_id)).execute()

    # Log admin action
    _log_admin_action(
        admin_id=admin["id"],
        action="book_deleted",
        target_type="book",
        target_id=str(book_id),
    )

    return api_success(data=None, message="Book deleted successfully")
