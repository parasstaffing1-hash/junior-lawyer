from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._()\-\u0900-\u097F ]+")
SUPPORTED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}


@dataclass(frozen=True, slots=True)
class StagedUpload:
    path: Path
    original_filename: str
    safe_filename: str
    extension: str
    mime_type: str
    sha256: str
    size_bytes: int


def sanitize_filename(filename: str) -> str:
    basename = Path(filename or "document").name.strip()
    cleaned = SAFE_FILENAME_RE.sub("_", basename).strip(" .")
    return cleaned[:240] or "document"


def validate_extension(filename: str) -> tuple[str, str]:
    extension = Path(filename).suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported document type '{extension or 'unknown'}'. Supported: {supported}",
        )
    return extension, SUPPORTED_EXTENSIONS[extension]


async def stage_upload(upload: UploadFile) -> StagedUpload:
    original_filename = upload.filename or "document"
    safe_filename = sanitize_filename(original_filename)
    extension, fallback_mime = validate_extension(safe_filename)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    staging_root = settings.storage_root / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="upload-", suffix=extension, dir=staging_root)
    os.close(fd)
    temp_path = Path(temp_name)

    digest = hashlib.sha256()
    size = 0

    try:
        with temp_path.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit",
                    )
                digest.update(chunk)
                target.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    validate_staged_content(temp_path, extension)

    return StagedUpload(
        path=temp_path,
        original_filename=original_filename,
        safe_filename=safe_filename,
        extension=extension,
        mime_type=fallback_mime,
        sha256=digest.hexdigest(),
        size_bytes=size,
    )



def validate_staged_content(path: Path, extension: str) -> None:
    """Reject obvious extension spoofing before any parser sees the file."""
    with path.open("rb") as source:
        head = source.read(4096)
    valid = True

    if extension == ".pdf":
        valid = head.startswith(b"%PDF-")
    elif extension == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                total_uncompressed = sum(item.file_size for item in archive.infolist())
                valid = (
                    "[Content_Types].xml" in names
                    and "word/document.xml" in names
                    and total_uncompressed <= 300 * 1024 * 1024
                    and len(names) <= 10_000
                )
        except zipfile.BadZipFile:
            valid = False
    elif extension == ".png":
        valid = head.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension in {".jpg", ".jpeg"}:
        valid = head.startswith(b"\xff\xd8\xff")
    elif extension in {".tif", ".tiff"}:
        valid = head.startswith((b"II*\x00", b"MM\x00*"))
    elif extension == ".bmp":
        valid = head.startswith(b"BM")
    elif extension == ".webp":
        valid = len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    elif extension == ".txt":
        valid = b"\x00" not in head

    if not valid:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="File content does not match its extension or is not a safe supported document",
        )


def _safe_relative_key(storage_key: str) -> Path:
    relative = Path(storage_key)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("Invalid storage key")
    return relative


def _s3_client():
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - dependency is declared for production builds
        raise RuntimeError("S3 storage requires boto3") from exc
    if not settings.storage_s3_bucket:
        raise RuntimeError("STORAGE_S3_BUCKET is required for S3 storage")
    kwargs = {
        "service_name": "s3",
        "region_name": settings.storage_s3_region,
    }
    if settings.storage_s3_endpoint_url:
        kwargs["endpoint_url"] = settings.storage_s3_endpoint_url
    if settings.storage_s3_access_key:
        kwargs["aws_access_key_id"] = settings.storage_s3_access_key
    if settings.storage_s3_secret_key:
        kwargs["aws_secret_access_key"] = settings.storage_s3_secret_key
    return boto3.client(**kwargs)

def _gdrive_service():
    import json
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("GDrive storage requires google-api-python-client and google-auth") from exc
        
    if not settings.storage_gdrive_credentials_json or not settings.storage_gdrive_root_folder_id:
        raise RuntimeError("STORAGE_GDRIVE_CREDENTIALS_JSON and STORAGE_GDRIVE_ROOT_FOLDER_ID are required")
        
    try:
        import base64
        decoded_json = base64.b64decode(settings.storage_gdrive_credentials_json).decode('utf-8')
        creds_dict = json.loads(decoded_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive.readonly']
        )
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google Drive client: {e}")


def promote_upload(staged: StagedUpload, *, matter_id: UUID, document_id: UUID) -> str:
    relative = Path(str(matter_id)) / str(document_id) / staged.safe_filename
    storage_key = relative.as_posix()
    backend = settings.storage_backend.casefold()

    if backend == "s3":
        client = _s3_client()
        client.upload_file(str(staged.path), settings.storage_s3_bucket, storage_key)
        staged.path.unlink(missing_ok=True)
        return storage_key
        
    if backend == "gdrive":
        from googleapiclient.http import MediaFileUpload
        service = _gdrive_service()
        file_metadata = {
            'name': f"{matter_id}_{document_id}_{staged.safe_filename}",
            'parents': [settings.storage_gdrive_root_folder_id]
        }
        media = MediaFileUpload(str(staged.path), mimetype=staged.mime_type, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        staged.path.unlink(missing_ok=True)
        # For gdrive, the storage_key is simply the Google Drive File ID
        return file.get('id')

    if backend != "local":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend}")

    destination = (settings.storage_root / relative).resolve()
    root = settings.storage_root.resolve()
    if root not in destination.parents:
        raise RuntimeError("Refusing to write outside document storage root")
    destination.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.move(str(staged.path), destination)
    return storage_key


def discard_staged(staged: StagedUpload) -> None:
    staged.path.unlink(missing_ok=True)


def resolve_storage_key(storage_key: str) -> Path:
    backend = settings.storage_backend.casefold()
    
    if backend == "local":
        relative = _safe_relative_key(storage_key)
        root = settings.storage_root.resolve()
        path = (settings.storage_root / relative).resolve()
        if root not in path.parents:
            raise RuntimeError("Invalid storage key")
        return path
        
    cache_root = settings.storage_cache_root.resolve()
    
    if backend == "gdrive":
        path = (settings.storage_cache_root / storage_key).resolve()
        if cache_root not in path.parents:
            raise RuntimeError("Invalid storage key")
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".download")
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            service = _gdrive_service()
            request = service.files().get_media(fileId=storage_key)
            with io.FileIO(str(temp), 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
        return path

    if backend != "s3":
        raise RuntimeError(f"Unsupported storage backend: {settings.storage_backend}")

    relative = _safe_relative_key(storage_key)
    path = (settings.storage_cache_root / relative).resolve()
    if cache_root not in path.parents:
        raise RuntimeError("Invalid storage key")
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".download")
    try:
        _s3_client().download_file(settings.storage_s3_bucket, storage_key, str(temp))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def delete_storage_key(storage_key: str | None) -> None:
    if not storage_key:
        return
    backend = settings.storage_backend.casefold()
    
    if backend == "gdrive":
        try:
            _gdrive_service().files().delete(fileId=storage_key).execute()
        except Exception:
            pass
        cache = (settings.storage_cache_root / storage_key).resolve()
        cache.unlink(missing_ok=True)
        return
        
    relative = _safe_relative_key(storage_key)
    if backend == "s3":
        _s3_client().delete_object(Bucket=settings.storage_s3_bucket, Key=storage_key)
        cache = (settings.storage_cache_root / relative).resolve()
        cache.unlink(missing_ok=True)
        try:
            cache.parent.rmdir()
        except OSError:
            pass
        return
    path = resolve_storage_key(storage_key)
    path.unlink(missing_ok=True)
    try:
        path.parent.rmdir()
    except OSError:
        pass


def check_storage_health() -> dict:
    backend = settings.storage_backend.casefold()
    if backend == "s3":
        try:
            _s3_client().head_bucket(Bucket=settings.storage_s3_bucket)
            return {"ready": True, "backend": "s3", "bucket": settings.storage_s3_bucket}
        except Exception as exc:
            return {"ready": False, "backend": "s3", "error": type(exc).__name__}
    if backend == "gdrive":
        try:
            service = _gdrive_service()
            folder_id = settings.storage_gdrive_root_folder_id
            service.files().get(fileId=folder_id, fields="id").execute()
            return {"ready": True, "backend": "gdrive", "folder_id": folder_id}
        except Exception as exc:
            return {"ready": False, "backend": "gdrive", "error": str(exc)}
    if backend != "local":
        return {"ready": False, "backend": backend, "error": "unsupported_backend"}
    try:
        root = settings.storage_root
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".health-probe"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return {"ready": True, "backend": "local"}
    except OSError as exc:
        return {"ready": False, "backend": "local", "error": type(exc).__name__}



def backup_object_storage_to_zip(archive: zipfile.ZipFile, *, prefix: str = "object-storage") -> int:
    """Stream S3-compatible source objects into an already-open ZIP backup."""
    if settings.storage_backend.casefold() != "s3":
        return 0
    client = _s3_client()
    count = 0
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.storage_s3_bucket):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key:
                continue
            relative = _safe_relative_key(key)
            arcname = (Path(prefix) / relative).as_posix()
            with archive.open(arcname, "w") as target:
                client.download_fileobj(settings.storage_s3_bucket, key, target)
            count += 1
    return count
