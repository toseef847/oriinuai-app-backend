from fastapi import HTTPException, UploadFile, status

UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


async def read_upload_with_limit(
    upload: UploadFile,
    max_bytes: int,
    file_label: str,
) -> bytes:
    """Read at most max_bytes without ever buffering an unbounded upload."""
    content = bytearray()

    while len(content) <= max_bytes:
        remaining = max_bytes + 1 - len(content)
        chunk = await upload.read(min(UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        content.extend(chunk)

    if len(content) > max_bytes:
        max_mebibytes = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{file_label} must not exceed {max_mebibytes} MiB.",
        )

    return bytes(content)
