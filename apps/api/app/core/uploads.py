from __future__ import annotations

from fastapi import UploadFile


class UploadTooLargeError(ValueError):
    """Raised when an upload exceeds the configured per-file limit."""


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    try:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise UploadTooLargeError(f"file exceeds maximum upload size of {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        await upload.close()
