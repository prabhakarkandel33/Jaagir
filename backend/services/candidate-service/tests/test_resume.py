"""Resume upload, replacement, deletion and guarded download (M7A)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.applications import services as application_services
from apps.candidates import services
from apps.candidates.models import Candidate
from apps.jobs.models import Job
from apps.jobs.services import upsert_job_from_snapshot
from contracts import EmploymentType, JobSnapshot
from contracts import JobStatus as ContractJobStatus

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
def media_root(tmp_path: Path, settings) -> Path:
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def make_candidate(email: str = "cand@example.com") -> Candidate:
    return Candidate.objects.create_user(email=email, password="correct horse battery")


def auth_client(candidate: Candidate) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {services.issue_access_token(candidate)}")
    return client


def upload(client: APIClient, content: bytes = PDF, name: str = "My CV.pdf"):
    return client.post(
        "/candidates/me/resume",
        {"file": SimpleUploadedFile(name, content, content_type="application/pdf")},
        format="multipart",
    )


def seed_job(recruiter_id: UUID) -> Job:
    snapshot = JobSnapshot(
        id=uuid4(),
        recruiter_id=recruiter_id,
        title="Backend Engineer",
        description="Build services",
        company="Example",
        location="Remote",
        employment_type=EmploymentType.FULL_TIME,
        skills=["python"],
        status=ContractJobStatus.PUBLISHED,
        version=2,
        published_at=timezone.now(),
        closed_at=None,
        updated_at=timezone.now(),
    )
    upsert_job_from_snapshot(snapshot)
    return Job.objects.get(id=snapshot.id)


def recruiter_token(recruiter_id: UUID) -> str:
    now = timezone.now()
    payload = {
        "sub": str(recruiter_id),
        "jti": str(uuid4()),
        "role": "recruiter",
        "iss": "job-service",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "token_type": "access",
    }
    return jwt.encode(payload, settings.JOB_SERVICE_TEST_SIGNING_KEY, algorithm="ES256")


def test_upload_accepts_pdf(media_root: Path) -> None:
    candidate = make_candidate()
    response = upload(auth_client(candidate))

    assert response.status_code == 200
    body = response.json()
    assert body["has_resume"] is True
    assert body["resume_filename"] == "My CV.pdf"
    candidate.refresh_from_db()
    stored = Path(candidate.resume_file.path)
    assert stored.exists()
    assert stored.read_bytes().startswith(b"%PDF-")
    assert stored.parent == media_root / "resumes"
    assert candidate.resume_uploaded_at is not None


def test_upload_rejects_non_pdf(media_root: Path) -> None:
    candidate = make_candidate()
    response = upload(auth_client(candidate), content=b"not a pdf")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESUME_FILE"
    candidate.refresh_from_db()
    assert candidate.resume_file == ""


def test_upload_rejects_empty_file(media_root: Path) -> None:
    candidate = make_candidate()
    response = upload(auth_client(candidate), content=b"")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RESUME_FILE"


def test_upload_rejects_file_over_five_mib(media_root: Path) -> None:
    candidate = make_candidate()
    too_big = b"%PDF-" + b"0" * settings.RESUME_MAX_BYTES
    response = upload(auth_client(candidate), content=too_big)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RESUME_TOO_LARGE"
    candidate.refresh_from_db()
    assert candidate.resume_file == ""


def test_replace_deletes_the_old_file(media_root: Path) -> None:
    candidate = make_candidate()
    client = auth_client(candidate)
    assert upload(client, content=PDF + b"one").status_code == 200
    candidate.refresh_from_db()
    old_path = Path(candidate.resume_file.path)

    assert upload(client, content=PDF + b"two").status_code == 200
    candidate.refresh_from_db()
    new_path = Path(candidate.resume_file.path)

    assert old_path != new_path
    assert not old_path.exists()
    assert new_path.exists()
    assert len(list((media_root / "resumes").iterdir())) == 1


def test_delete_removes_fields_and_file(media_root: Path) -> None:
    candidate = make_candidate()
    client = auth_client(candidate)
    upload(client)
    candidate.refresh_from_db()
    stored = Path(candidate.resume_file.path)

    response = client.delete("/candidates/me/resume")

    assert response.status_code == 200
    assert response.json()["has_resume"] is False
    assert not stored.exists()
    candidate.refresh_from_db()
    assert candidate.resume_file == ""
    assert candidate.resume_filename == ""
    assert candidate.resume_uploaded_at is None


def test_candidate_can_download_own_resume(media_root: Path) -> None:
    candidate = make_candidate()
    client = auth_client(candidate)
    upload(client)

    response = client.get("/candidates/me/resume")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"].startswith("attachment;")
    assert b"".join(response.streaming_content).startswith(b"%PDF-")


def test_missing_resume_is_404(media_root: Path) -> None:
    candidate = make_candidate()
    response = auth_client(candidate).get("/candidates/me/resume")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESUME_NOT_FOUND"


def test_anonymous_resume_download_is_401(media_root: Path) -> None:
    response = APIClient().get("/candidates/me/resume")
    assert response.status_code == 401


def test_recruiter_reads_resume_only_for_own_applicant(media_root: Path) -> None:
    candidate = make_candidate()
    upload(auth_client(candidate))
    recruiter_a = uuid4()
    recruiter_b = uuid4()
    job = seed_job(recruiter_a)
    application = application_services.apply_to_job(candidate, str(job.id), "")

    owner = APIClient()
    owner.credentials(HTTP_AUTHORIZATION=f"Bearer {recruiter_token(recruiter_a)}")
    response = owner.get(f"/recruiter/applications/{application.id}/resume")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content).startswith(b"%PDF-")

    foreign = APIClient()
    foreign.credentials(HTTP_AUTHORIZATION=f"Bearer {recruiter_token(recruiter_b)}")
    denied = foreign.get(f"/recruiter/applications/{application.id}/resume")
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "APPLICATION_NOT_FOUND"
