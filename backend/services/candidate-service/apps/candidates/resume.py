"""Resume storage and guarded streaming (M7A).

Files live under ``MEDIA_ROOT/resumes`` with a random name and are never served
through ``MEDIA_URL``. Every download passes an ownership check in the view and
streams the bytes with ``attachment`` + ``nosniff`` headers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status

from apps.candidates.models import Candidate
from config.exceptions import ApiError

PDF_MAGIC = b"%PDF-"
DEFAULT_FILENAME = "resume.pdf"


def _invalid(code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST) -> ApiError:
    return ApiError(code=code, message=message, http_status=http_status)


def validate_pdf(upload: Any) -> None:
    """Reject empty, oversized and non-PDF uploads before they touch disk."""
    size = getattr(upload, "size", 0) or 0
    if size <= 0:
        raise _invalid("INVALID_RESUME_FILE", "The uploaded file is empty.")
    if size > settings.RESUME_MAX_BYTES:
        raise _invalid(
            "RESUME_TOO_LARGE",
            "The resume must be 5 MB or smaller.",
            status.HTTP_400_BAD_REQUEST,
        )
    upload.seek(0)
    magic = upload.read(len(PDF_MAGIC))
    upload.seek(0)
    if magic != PDF_MAGIC:
        raise _invalid("INVALID_RESUME_FILE", "Only PDF resumes are accepted.")


def display_filename(upload: Any) -> str:
    """Sanitized, human-readable name stored next to the random file name."""
    raw = Path(str(getattr(upload, "name", "") or "")).name
    cleaned = "".join(ch for ch in raw if ch.isprintable()).strip()
    if not cleaned:
        cleaned = DEFAULT_FILENAME
    return cleaned[:255]


def save_resume(candidate: Candidate, upload: Any) -> Candidate:
    validate_pdf(upload)
    old_name = candidate.resume_file.name if candidate.resume_file else ""
    old_storage = candidate.resume_file.storage if candidate.resume_file else None

    candidate.resume_file = upload
    candidate.resume_filename = display_filename(upload)
    candidate.resume_uploaded_at = timezone.now()
    candidate.save(
        update_fields=[
            "resume_file",
            "resume_filename",
            "resume_uploaded_at",
            "updated_at",
        ]
    )

    if old_name and old_storage is not None and old_name != candidate.resume_file.name:
        old_storage.delete(old_name)
    return candidate


def remove_resume(candidate: Candidate) -> Candidate:
    old_name = candidate.resume_file.name if candidate.resume_file else ""
    old_storage = candidate.resume_file.storage if candidate.resume_file else None

    candidate.resume_file = ""
    candidate.resume_filename = ""
    candidate.resume_uploaded_at = None
    candidate.save(
        update_fields=[
            "resume_file",
            "resume_filename",
            "resume_uploaded_at",
            "updated_at",
        ]
    )

    if old_name and old_storage is not None:
        old_storage.delete(old_name)
    return candidate


def _content_disposition(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode() or DEFAULT_FILENAME
    ascii_name = ascii_name.replace('"', "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def resume_response(candidate: Candidate) -> FileResponse:
    """Stream the candidate's PDF, or raise the uniform 404 envelope."""
    if not candidate.resume_file:
        raise _invalid("RESUME_NOT_FOUND", "No resume uploaded.", status.HTTP_404_NOT_FOUND)
    try:
        path = candidate.resume_file.path
    except (NotImplementedError, ValueError):
        raise _invalid(
            "RESUME_NOT_FOUND",
            "No resume uploaded.",
            status.HTTP_404_NOT_FOUND,
        ) from None
    if not os.path.exists(path):
        raise _invalid("RESUME_NOT_FOUND", "No resume uploaded.", status.HTTP_404_NOT_FOUND)

    filename = candidate.resume_filename or DEFAULT_FILENAME
    response = FileResponse(open(path, "rb"), content_type="application/pdf")  # noqa: SIM115
    response["Content-Disposition"] = _content_disposition(filename)
    response["X-Content-Type-Options"] = "nosniff"
    return response
