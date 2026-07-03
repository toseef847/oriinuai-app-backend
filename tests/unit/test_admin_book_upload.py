from __future__ import annotations

import io
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

import app.api.v1.endpoints.admin.books as books_endpoint
import app.services.rag.ingestion as ingestion_service


class _BookQuery:
    def __init__(self, client: "_FakeSupabase", table_name: str):
        self.client = client
        self.table_name = table_name
        self.action = "select"
        self.payload: dict | None = None

    def select(self, _fields: str):
        return self

    def eq(self, _field: str, _value: object):
        return self

    def limit(self, _value: int):
        return self

    def insert(self, payload: dict):
        self.action = "insert"
        self.payload = payload
        return self

    def execute(self):
        if self.table_name == "books" and self.action == "select":
            return SimpleNamespace(data=[])
        if self.table_name == "books" and self.action == "insert":
            self.client.events.append("database_insert")
            if self.client.database_error:
                raise RuntimeError("database unavailable")
            self.client.inserted_book = self.payload
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=[self.payload] if self.payload else [])


class _FakeBucket:
    def __init__(self, client: "_FakeSupabase"):
        self.client = client

    def upload(self, *, path: str, file: bytes, file_options: dict):
        self.client.events.append("storage_upload")
        self.client.upload = {
            "path": path,
            "file": file,
            "file_options": file_options,
        }
        if self.client.storage_error:
            raise RuntimeError("provider detail must not escape")

    def remove(self, paths: list[str]):
        self.client.events.append("storage_cleanup")
        self.client.removed_paths.extend(paths)


class _FakeStorage:
    def __init__(self, client: "_FakeSupabase"):
        self.client = client

    def from_(self, bucket: str):
        assert bucket == books_endpoint.BOOK_PDF_BUCKET
        return _FakeBucket(self.client)


class _FakeSupabase:
    def __init__(self, *, storage_error: bool = False, database_error: bool = False):
        self.storage_error = storage_error
        self.database_error = database_error
        self.storage = _FakeStorage(self)
        self.events: list[str] = []
        self.upload: dict | None = None
        self.inserted_book: dict | None = None
        self.removed_paths: list[str] = []

    def table(self, table_name: str):
        return _BookQuery(self, table_name)


def _unicode_pdf() -> UploadFile:
    return UploadFile(
        filename="Olódùmarè UPDATED.pdf",
        file=io.BytesIO(b"%PDF-1.7 test content"),
    )


@pytest.mark.asyncio
async def test_upload_uses_uuid_key_before_database_insert(monkeypatch) -> None:
    client = _FakeSupabase()
    monkeypatch.setattr(books_endpoint, "supabase_admin", client)
    background_tasks = BackgroundTasks()

    response = await books_endpoint.upload_book(
        background_tasks=background_tasks,
        file=_unicode_pdf(),
        title="Olódùmarè Updated",
        author="Author",
        admin={"id": "admin-id"},
    )

    assert response.status_code == 200
    assert client.events[:2] == ["storage_upload", "database_insert"]
    assert client.upload is not None
    storage_path = client.upload["path"]
    assert storage_path.startswith("books/")
    assert storage_path.endswith(".pdf")
    assert "Ol" not in storage_path
    book_id = storage_path.removeprefix("books/").removesuffix(".pdf")
    UUID(book_id)
    assert client.inserted_book == {
        "id": book_id,
        "title": "Olódùmarè Updated",
        "author": "Author",
        "file_hash": client.inserted_book["file_hash"],
        "storage_path": storage_path,
        "ingestion_status": "pending",
    }
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func is books_endpoint.ingest_book
    assert task.args == (book_id, False)


@pytest.mark.asyncio
async def test_storage_failure_does_not_create_book_record(monkeypatch) -> None:
    client = _FakeSupabase(storage_error=True)
    monkeypatch.setattr(books_endpoint, "supabase_admin", client)

    with pytest.raises(HTTPException) as exc_info:
        await books_endpoint.upload_book(
            background_tasks=BackgroundTasks(),
            file=_unicode_pdf(),
            admin={"id": "admin-id"},
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Book storage upload failed. Please try again."
    assert client.events == ["storage_upload"]
    assert client.inserted_book is None


@pytest.mark.asyncio
async def test_database_failure_removes_uploaded_object(monkeypatch) -> None:
    client = _FakeSupabase(database_error=True)
    monkeypatch.setattr(books_endpoint, "supabase_admin", client)

    with pytest.raises(HTTPException) as exc_info:
        await books_endpoint.upload_book(
            background_tasks=BackgroundTasks(),
            file=_unicode_pdf(),
            admin={"id": "admin-id"},
        )

    assert exc_info.value.status_code == 500
    assert client.events == [
        "storage_upload",
        "database_insert",
        "storage_cleanup",
    ]
    assert client.upload is not None
    assert client.removed_paths == [client.upload["path"]]


class _IngestionQuery:
    def __init__(self, client: "_IngestionSupabase"):
        self.client = client
        self.action = "select"
        self.payload: dict | None = None

    def update(self, payload: dict):
        self.action = "update"
        self.payload = payload
        return self

    def select(self, _fields: str):
        self.action = "select"
        return self

    def eq(self, _field: str, _value: object):
        return self

    def limit(self, _value: int):
        return self

    def execute(self):
        if self.action == "select":
            return SimpleNamespace(data=[{"storage_path": self.client.storage_path}])
        self.client.status_updates.append(self.payload)
        return SimpleNamespace(data=[self.payload])


class _DownloadBucket:
    def __init__(self, client: "_IngestionSupabase"):
        self.client = client

    def download(self, path: str):
        self.client.downloaded_paths.append(path)
        return b"%PDF-1.7 stored content"


class _IngestionStorage:
    def __init__(self, client: "_IngestionSupabase"):
        self.client = client

    def from_(self, bucket: str):
        assert bucket == "book-pdfs"
        return _DownloadBucket(self.client)


class _IngestionSupabase:
    def __init__(self):
        self.storage_path = "books/11111111-1111-1111-1111-111111111111.pdf"
        self.storage = _IngestionStorage(self)
        self.downloaded_paths: list[str] = []
        self.status_updates: list[dict | None] = []

    def table(self, table_name: str):
        assert table_name == "books"
        return _IngestionQuery(self)


@pytest.mark.asyncio
async def test_ingestion_always_downloads_the_stored_pdf(monkeypatch) -> None:
    client = _IngestionSupabase()
    monkeypatch.setattr(ingestion_service, "supabase_admin", client)
    monkeypatch.setattr(ingestion_service, "extract_text_from_pdf", lambda _data: "")

    with pytest.raises(ValueError, match="No extractable text"):
        await ingestion_service.ingest_book("book-id")

    assert client.downloaded_paths == [client.storage_path]
    assert client.status_updates == [
        {"ingestion_status": "processing"},
        {"ingestion_status": "failed"},
    ]
