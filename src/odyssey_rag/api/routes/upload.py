"""File upload endpoint — POST /api/v1/upload.

Accepts multipart file uploads and stores them in the sources directory,
making them available for subsequent ingestion via POST /api/v1/ingest.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from odyssey_rag.api.auth import verify_api_key

router = APIRouter(tags=["upload"])

SOURCES_DIR = Path(os.environ.get("SOURCES_DIR", "/app/sources"))

ALLOWED_EXTENSIONS = {".md", ".php", ".xml", ".json", ".pdf", ".txt", ".rst", ".doc", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Only allow safe filenames — alphanumeric, hyphens, underscores, dots
SAFE_FILENAME_RE = re.compile(r"^[\w\-. ]+$")


def _validate_filename(filename: str) -> str:
    """Validate and sanitize the uploaded filename."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Use only the basename to prevent path traversal
    safe_name = Path(filename).name

    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not SAFE_FILENAME_RE.match(safe_name):
        raise HTTPException(
            status_code=400,
            detail="Filename contains invalid characters",
        )

    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    return safe_name


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    _: str = Depends(verify_api_key),
):
    """Upload a file to the sources directory for later ingestion.

    The file is saved to /app/sources/{filename}. If a file with the
    same name already exists, it is overwritten (the ingestion pipeline
    handles change detection via SHA-256 hash).
    """
    safe_name = _validate_filename(file.filename or "")

    # Read content with size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB",
        )

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    dest = SOURCES_DIR / safe_name
    dest.write_bytes(content)

    return {
        "filename": safe_name,
        "size_bytes": len(content),
        "path": str(dest),
    }
