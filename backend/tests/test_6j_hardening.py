"""Phase 6J Targeted Hardening Regression Tests.

Tests:
1. Path traversal filenames are sanitized.
2. Consecutive analysis calls do not duplicate findings.
3. /review endpoint cannot bypass /finalize guardrails.
4. ReviewDecision rows survive re-analysis.
5. Invalid inspection UUID returns clean 404.
6. UPLOAD_ROOT is absolute (invariant for PDF report generation).
7. Report endpoint returns valid PDF for a finalized inspection.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.storage import UPLOAD_ROOT
from app.db.session import SessionLocal
from app.main import app
from app.models.review_decision import ReviewDecision


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_png() -> bytes:
    def _chunk(t: bytes, d: bytes) -> bytes:
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
        + _chunk(b"IEND", b"")
    )


PNG = _make_png()
FIXTURE = Path(__file__).parent / "fixtures" / "package_label.png"


def _create(client: TestClient, sfx: str = "") -> str:
    tag = uuid4().hex[:8] + sfx
    r = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-6J-{tag}", "title": "6J Regression Test"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client: TestClient, iid: str) -> None:
    img = FIXTURE.read_bytes() if FIXTURE.exists() else PNG
    r = client.post(
        f"/api/v1/inspections/{iid}/upload-image",
        files={"file": ("package_label.png", img, "image/png")},
    )
    assert r.status_code == 201, r.text


def _review_all(client: TestClient, iid: str) -> list:
    fs = client.get(f"/api/v1/inspections/{iid}/findings").json()
    for f in fs:
        client.post(
            f"/api/v1/inspections/{iid}/findings/{f['id']}/review",
            json={"inspection_id": iid, "decision": "confirm", "reviewer_name": "t", "notes": "ok"},
        )
    return fs


# ---------------------------------------------------------------------------
# 1 — Path traversal
# ---------------------------------------------------------------------------


def test_path_traversal_filename_sanitized(client: TestClient) -> None:
    """Traversal filename must not escape the upload directory."""
    iid = _create(client, "-TRAV")
    img = FIXTURE.read_bytes() if FIXTURE.exists() else PNG
    r = client.post(
        f"/api/v1/inspections/{iid}/upload-image",
        files={"file": ("../../traversal.png", img, "image/png")},
    )
    if r.status_code == 201:
        jdata = r.json()
        saved = (jdata[0] if isinstance(jdata, list) else jdata).get("storage_path", "")
        # storage_path is relative to backend/app/ (the app package root)
        # UPLOAD_ROOT = backend/app/storage/uploads  →  UPLOAD_ROOT.parent.parent = backend/app
        app_root = UPLOAD_ROOT.parent.parent
        resolved = (app_root / saved).resolve()
        assert str(resolved).startswith(str(UPLOAD_ROOT.resolve()))
    else:
        assert r.status_code == 400


def test_upload_root_is_absolute() -> None:
    """UPLOAD_ROOT must be an absolute path."""
    assert UPLOAD_ROOT.is_absolute(), f"UPLOAD_ROOT must be absolute, got: {UPLOAD_ROOT}"


# ---------------------------------------------------------------------------
# 2 — Re-analysis idempotency
# ---------------------------------------------------------------------------


def test_reanalysis_does_not_duplicate_findings(client: TestClient) -> None:
    """Running /analyze twice must not double the finding count."""
    iid = _create(client, "-IDEM")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    c1 = len(client.get(f"/api/v1/inspections/{iid}/findings").json())
    assert c1 >= 1
    client.post(f"/api/v1/inspections/{iid}/analyze")
    c2 = len(client.get(f"/api/v1/inspections/{iid}/findings").json())
    assert c2 == c1, f"Idempotency violated: {c1} -> {c2}"


def test_reanalysis_preserves_review_decision_rows(client: TestClient) -> None:
    """ReviewDecision rows must survive a re-analysis."""
    iid = _create(client, "-RDPRS")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    fs = client.get(f"/api/v1/inspections/{iid}/findings").json()
    assert len(fs) >= 1
    client.post(
        f"/api/v1/inspections/{iid}/findings/{fs[0]['id']}/review",
        json={"inspection_id": iid, "decision": "confirm", "reviewer_name": "t", "notes": "pre"},
    )
    with SessionLocal() as db:
        before = len(db.scalars(select(ReviewDecision).where(ReviewDecision.inspection_id == iid)).all())
    client.post(f"/api/v1/inspections/{iid}/analyze")
    with SessionLocal() as db:
        after = len(db.scalars(select(ReviewDecision).where(ReviewDecision.inspection_id == iid)).all())
    assert after >= before, f"ReviewDecision rows lost: {before} -> {after}"


# ---------------------------------------------------------------------------
# 3 — Review endpoint cannot bypass finalize guardrails
# ---------------------------------------------------------------------------


def test_review_does_not_set_completed(client: TestClient) -> None:
    """POST /review must NOT advance status to COMPLETED."""
    iid = _create(client, "-BYPAS")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    client.post(
        f"/api/v1/inspections/{iid}/review",
        json={"inspection_id": iid, "decision": "confirm", "reviewer_name": "t", "notes": "bypass"},
    )
    st = client.get(f"/api/v1/inspections/{iid}").json()["status"]
    assert st != "COMPLETED", "review endpoint bypassed finalize guardrail"


def test_finalize_blocked_without_review(client: TestClient) -> None:
    """POST /finalize is blocked when findings are unreviewed."""
    iid = _create(client, "-NOREV")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    fs = client.get(f"/api/v1/inspections/{iid}/findings").json()
    assert len(fs) >= 1
    r = client.post(f"/api/v1/inspections/{iid}/finalize")
    assert r.status_code == 400
    assert "not been reviewed" in r.json()["detail"].lower()


def test_finalize_succeeds_after_all_reviewed(client: TestClient) -> None:
    """POST /finalize succeeds when all findings are reviewed."""
    iid = _create(client, "-FINOK")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    _review_all(client, iid)
    r = client.post(f"/api/v1/inspections/{iid}/finalize")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 4 — Invalid inspection UUID returns clean 404
# ---------------------------------------------------------------------------


def test_invalid_inspection_id_returns_404(client: TestClient) -> None:
    bogus = "00000000-dead-beef-0000-000000000000"
    for url in [
        f"/api/v1/inspections/{bogus}",
        f"/api/v1/inspections/{bogus}/findings",
        f"/api/v1/inspections/{bogus}/analysis",
        f"/api/v1/inspections/{bogus}/images",
        f"/api/v1/inspections/{bogus}/summary",
    ]:
        assert client.get(url).status_code == 404, f"Expected 404 for GET {url}"
    assert client.post(f"/api/v1/inspections/{bogus}/analyze").status_code == 404
    assert client.post(f"/api/v1/inspections/{bogus}/finalize").status_code == 404


# ---------------------------------------------------------------------------
# 5 — Report uses absolute storage path
# ---------------------------------------------------------------------------


def test_report_uses_absolute_storage_path(client: TestClient) -> None:
    """PDF report generation must not fail regardless of working directory."""
    iid = _create(client, "-RPATH")
    _upload(client, iid)
    client.post(f"/api/v1/inspections/{iid}/analyze")
    _review_all(client, iid)
    client.post(f"/api/v1/inspections/{iid}/finalize")
    r = client.get(f"/api/v1/inspections/{iid}/report")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
