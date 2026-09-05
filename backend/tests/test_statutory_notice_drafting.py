from __future__ import annotations

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from uuid import uuid4
from sqlalchemy import select

from app.main import app
from app.db.session import SessionLocal
from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage
from app.models.finding import Finding
from app.models.product import Product
from app.models.notice import Notice
from app.services.notice_drafting_service import get_legal_catalog_context

client = TestClient(app)


def _create_test_image_file(tmp_path: Path, filename: str = "panel_front.jpg") -> str:
    img_path = tmp_path / filename
    img = Image.new("RGB", (300, 300), color="white")
    img.save(img_path, format="JPEG")
    return str(img_path)


@pytest.fixture
def finalized_inspection(tmp_path):
    """Creates a completed inspection with known, unknown, and conflicting findings."""
    db = SessionLocal()
    try:
        # Create a linked product
        product = Product(
            name="PRAMAN Test Biscuits 500g",
            brand="Praman Foods",
            category="Food Articles",
            manufacturer="M/s Praman Food Industries Ltd",
        )

        db.add(product)
        db.flush()

        # Create completed inspection with unique number
        unique_insp_num = f"INSP-P13-{uuid4().hex[:8].upper()}"
        inspection = Inspection(
            inspection_number=unique_insp_num,
            status="COMPLETED",
            title="PRAMAN Test Inspection for Statutory Notice",
            product_id=product.id,
        )

        db.add(inspection)
        db.flush()

        # Create images
        img1_path = _create_test_image_file(tmp_path, "front.jpg")
        img2_path = _create_test_image_file(tmp_path, "back.jpg")

        img1 = InspectionImage(
            inspection_id=inspection.id,
            image_type="front",
            file_name="front.jpg",
            storage_path=img1_path,
        )
        img2 = InspectionImage(
            inspection_id=inspection.id,
            image_type="back",
            file_name="back.jpg",
            storage_path=img2_path,
        )
        db.add_all([img1, img2])
        db.flush()

        # Create findings:
        # 1. Known PCR-001 violation (Manufacturer name/address missing)
        f1 = Finding(
            inspection_id=inspection.id,
            severity="critical",
            status="confirmed",
            title="Missing Manufacturer Declaration",
            description="Name and address of the manufacturer is missing on the package.",
            rule_check_id="PCR-001",
            evidence_reference='{"panel_type": "front", "source_file": "front.jpg"}',
        )
        # 2. Known PCR-006 violation (MRP missing)
        f2 = Finding(
            inspection_id=inspection.id,
            severity="critical",
            status="confirmed",
            title="Missing MRP Declaration",
            description="Maximum Retail Price (inclusive of all taxes) was not declared.",
            rule_check_id="PCR-006",
            evidence_reference='{"panel_type": "back", "source_file": "back.jpg"}',
        )
        # 3. Unsupported / unmapped rule check
        f3 = Finding(
            inspection_id=inspection.id,
            severity="warning",
            status="confirmed",
            title="Unrecognized Packaging Condition",
            description="Custom packaging condition not in standard catalog.",
            rule_check_id="CUSTOM-999-UNMAPPED",
            evidence_reference='{"panel_type": "back", "source_file": "back.jpg"}',
        )
        # 4. Conflicting multi-panel finding
        f4 = Finding(
            inspection_id=inspection.id,
            severity="major",
            status="manual_review",
            title="Conflicting Net Quantity Detection",
            description="Front panel declared 500g while back panel declared 450g.",
            rule_check_id="PCR-004",
            evidence_reference='{"panel_type": "back", "source_file": "back.jpg", "has_conflict": true}',
        )
        db.add_all([f1, f2, f3, f4])
        db.commit()

        yield inspection.id
    finally:
        # Cleanup
        db.close()


def test_statutory_notice_drafting_and_statutory_mapping(finalized_inspection):
    """
    Verifies:
    1. Notice draft is created with DRAFT status.
    2. PCR-001 and PCR-006 map to Section 36(1) of Legal Metrology Act, 2009.
    3. Unsupported rule and conflicting panel route to MANUAL_LEGAL_REVIEW.
    4. Catalog version and SHA-256 are captured accurately.
    5. No hardcoded fine amounts (₹/INR) are asserted.
    """
    resp = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["status"] == "DRAFT"
    assert data["is_immutable"] is False
    assert data["notice_reference"].startswith("SCN-")

    # Recipient populated from product
    assert "M/s Praman Food Industries Ltd" in data["recipient_name"]
    assert data["recipient_address"] == "Premises Inspected"
    assert data["recipient_role"] == "manufacturer"


    # Catalog context
    cat_context = get_legal_catalog_context()
    assert data["legal_version_context"]["catalog_version"] == cat_context["catalog_version"]
    assert data["legal_version_context"]["catalog_sha256"] == cat_context["catalog_sha256"]
    assert len(data["legal_version_context"]["catalog_sha256"]) == 64

    # Charges mapping inspection
    charges = {c["rule_id"]: c for c in data["statutory_charges"]}
    assert "PCR-001" in charges
    assert "PCR-006" in charges
    assert "CUSTOM-999-UNMAPPED" in charges
    assert "PCR-004" in charges

    # PCR-001 maps to Section 36(1)
    pcr1 = charges["PCR-001"]
    assert "Section 36(1)" in pcr1["statutory_provision"]
    assert pcr1["requires_manual_review"] is False
    # No hardcoded rupee amounts
    assert "₹" not in pcr1["statutory_provision"] and "25,000" not in pcr1["statutory_provision"]

    # PCR-006 maps to Section 36(1)
    pcr6 = charges["PCR-006"]
    assert "Section 36(1)" in pcr6["statutory_provision"]
    assert pcr6["requires_manual_review"] is False

    # CUSTOM-999 routes to MANUAL_LEGAL_REVIEW
    custom = charges["CUSTOM-999-UNMAPPED"]
    assert custom["requires_manual_review"] is True
    assert "MANUAL_LEGAL_REVIEW" in custom["liability_basis"]

    # PCR-004 has conflict -> routes to MANUAL_LEGAL_REVIEW
    pcr4 = charges["PCR-004"]
    assert pcr4["requires_manual_review"] is True
    assert "Multi-panel conflicting evidence detected" in pcr4["liability_basis"]

    # Procedural term
    assert data["response_period_days"] == 15
    assert "not a fixed statutory mandate" in data["response_period_basis"]


def test_recipient_role_does_not_mutate_statutory_charge(finalized_inspection):
    """
    Changing recipient role (e.g., from manufacturer to retailer or distributor)
    does not alter the underlying statutory charges or substantive provisions.
    """
    # Create draft
    draft_res = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    assert draft_res.status_code in (200, 201)
    notice_id = draft_res.json()["id"]

    # Update recipient role to retailer
    update_res = client.put(f"/api/v1/notices/{notice_id}", json={
        "recipient_role": "retailer",
        "recipient_name": "M/s Corner Grocery Store",
        "recipient_address": "Shop 12, Main Market",
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["recipient_role"] == "retailer"

    # Verify charges still point to Section 36(1)
    pcr1 = [c for c in updated_data["statutory_charges"] if c["rule_id"] == "PCR-001"][0]
    assert "Section 36(1)" in pcr1["statutory_provision"]


def test_review_and_issuance_lifecycle_and_immutability(finalized_inspection):
    """
    Verifies:
    1. Attempting to issue directly from DRAFT returns 400.
    2. Reviewing with unacknowledged manual review charges returns 400.
    3. Reviewing with officer verification notes succeeds -> REVIEWED.
    4. Issuing with missing officer credentials returns 400.
    5. Issuing with valid credentials succeeds -> ISSUED_BY_OFFICER and is_immutable=True.
    6. Updating an issued notice returns 409 Conflict.
    7. Underlying inspection, findings, and images remain completely untouched.
    """
    # 1. Fetch or create draft
    draft_res = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    notice_id = draft_res.json()["id"]

    # 2. Attempt to issue from DRAFT -> rejected
    bad_issue = client.post(f"/api/v1/notices/{notice_id}/issue", json={
        "officer_notes": "Attempting issue while in DRAFT",
    })
    assert bad_issue.status_code == 400
    assert "must be transitioned to REVIEWED" in bad_issue.json()["detail"]

    # 3. Attempt review without notes when manual review charges exist -> rejected
    bad_review = client.post(f"/api/v1/notices/{notice_id}/review", json={})
    assert bad_review.status_code == 400
    assert "MANUAL LEGAL REVIEW" in bad_review.json()["detail"]

    # 4. Review with officer notes -> succeeds
    good_review = client.post(f"/api/v1/notices/{notice_id}/review", json={
        "officer_notes": "Inspecting officer verified physical package sample on 04-Sep-2026. Confirmed net quantity discrepancy and approved charge sheet."
    })
    assert good_review.status_code == 200
    assert good_review.json()["status"] == "REVIEWED"
    assert good_review.json()["reviewed_at"] is not None

    # 5. Attempt issuance with spoofed client officer fields -> rejected (422)
    bad_creds = client.post(f"/api/v1/notices/{notice_id}/issue", json={
        "officer_name": "Spoofed Officer",
        "officer_designation": "Inspector",
        "officer_office": "HQ",
    })
    assert bad_creds.status_code == 422

    # 6. Issue notice formally -> succeeds and locks with authenticated officer identity
    issue_res = client.post(f"/api/v1/notices/{notice_id}/issue", json={
        "officer_notes": "Verified inspection evidence and confirmed legal notice."
    })
    assert issue_res.status_code == 200
    issued_data = issue_res.json()
    assert issued_data["status"] == "ISSUED_BY_OFFICER"
    assert issued_data["is_immutable"] is True
    assert issued_data["issued_at"] is not None
    assert issued_data["officer_name"] == "Default Test Officer"

    # 7. Attempt to update issued notice -> 409 Conflict
    conflict_update = client.put(f"/api/v1/notices/{notice_id}", json={
        "recipient_name": "Attempt to Tamper with Issued Notice",
    })
    assert conflict_update.status_code == 409
    assert "permanently locked and immutable" in conflict_update.json()["detail"]

    # 8. Attempt to review issued notice -> 409 Conflict
    conflict_review = client.post(f"/api/v1/notices/{notice_id}/review", json={"officer_notes": "re-review"})
    assert conflict_review.status_code == 409

    # 9. Verify historical inspection & findings remain untouched
    db = SessionLocal()
    try:
        insp = db.get(Inspection, finalized_inspection)
        assert insp.status == "COMPLETED"
        assert insp.inspection_number.startswith("INSP-P13-")
        assert len(insp.findings) == 4
        assert len(insp.images) == 2

    finally:
        db.close()


def test_pdf_draft_watermark_until_issued(finalized_inspection):
    """
    Verifies that generated PDF contains the DRAFT watermark string
    while in DRAFT or REVIEWED status, and omits it once ISSUED_BY_OFFICER.
    """
    # Create draft
    draft_res = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    notice_id = draft_res.json()["id"]

    # Download PDF in DRAFT status
    pdf_res_draft = client.get(f"/api/v1/notices/{notice_id}/pdf")
    assert pdf_res_draft.status_code == 200
    assert pdf_res_draft.headers["content-type"] == "application/pdf"
    pdf_bytes_draft = pdf_res_draft.content
    assert len(pdf_bytes_draft) > 1000
    # In ReportLab, literal text in the page stream contains the watermark
    assert b"DRAFT" in pdf_bytes_draft
    assert b"FOR OFFICER REVIEW ONLY" in pdf_bytes_draft

    # Review and issue notice
    client.post(f"/api/v1/notices/{notice_id}/review", json={"officer_notes": "Verified"})
    issue_res = client.post(f"/api/v1/notices/{notice_id}/issue", json={
        "officer_notes": "Formal issuance by authorized officer",
    })
    assert issue_res.status_code == 200

    # Download PDF in ISSUED_BY_OFFICER status
    pdf_res_issued = client.get(f"/api/v1/notices/{notice_id}/pdf")
    assert pdf_res_issued.status_code == 200
    pdf_bytes_issued = pdf_res_issued.content
    assert len(pdf_bytes_issued) > 1000
    # Watermark text is omitted from the canvas
    assert b"DRAFT \xe2\x80\x94 FOR OFFICER REVIEW ONLY" not in pdf_bytes_issued
    assert b"DRAFT \x97 FOR OFFICER REVIEW ONLY" not in pdf_bytes_issued
    assert b"FOR OFFICER REVIEW ONLY" not in pdf_bytes_issued
    # Officer details are present in the PDF
    assert b"Default Test Officer" in pdf_bytes_issued


def test_compounding_clause_toggle(finalized_inspection):
    """
    Verifies compounding clause can be explicitly configured and included in PDF.
    """
    draft_res = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    notice_id = draft_res.json()["id"]

    # Toggle compounding clause on
    up_res = client.put(f"/api/v1/notices/{notice_id}", json={
        "compounding_eligible": True,
        "compounding_clause_included": True,
    })
    assert up_res.status_code == 200
    assert up_res.json()["compounding_clause_included"] is True

    # Check PDF includes compounding text
    pdf_res = client.get(f"/api/v1/notices/{notice_id}/pdf")
    assert pdf_res.status_code == 200
    assert b"COMPOUNDING OF OFFENSE UNDER SECTION 48" in pdf_res.content


def test_non_completed_inspection_cannot_draft_notice():
    """
    Verifies that drafting a notice for an inspection with status != 'COMPLETED' is rejected with 400.
    """
    db = SessionLocal()
    try:
        insp = Inspection(
            inspection_number=f"INSP-INCOMPLETE-{uuid4().hex[:8].upper()}",
            status="DRAFT",
            title="Incomplete Inspection",
        )
        db.add(insp)
        db.commit()
        db.refresh(insp)

        resp = client.post(f"/api/v1/inspections/{insp.id}/notice/draft")
        assert resp.status_code == 400
        assert "status must be COMPLETED" in resp.json()["detail"]
    finally:
        db.close()


def test_clean_inspection_with_no_violations_cannot_draft_notice():
    """
    Verifies that drafting a notice for an inspection with zero violations is rejected with 400.
    """
    db = SessionLocal()
    try:
        insp = Inspection(
            inspection_number=f"INSP-CLEAN-{uuid4().hex[:8].upper()}",
            status="COMPLETED",
            title="Clean Inspection",
        )
        db.add(insp)
        db.flush()

        # Add only a passed finding
        f = Finding(
            inspection_id=insp.id,
            severity="pass",
            status="resolved",
            title="Compliant Declaration",
            description="All mandatory declarations compliant.",
            rule_check_id="PCR-001",
        )
        db.add(f)
        db.commit()
        db.refresh(insp)

        resp = client.post(f"/api/v1/inspections/{insp.id}/notice/draft")
        assert resp.status_code == 400
        assert "no confirmed or actionable violations" in resp.json()["detail"]
    finally:
        db.close()


def test_issued_notice_cannot_be_deleted_via_inspection_orm_deletion(finalized_inspection):
    """
    Historical Integrity Regression Test:
    Proves that an issued immutable Notice CANNOT be deleted or orphaned through
    Inspection ORM deletion or direct notice deletion.
    """
    # 1. Draft, review, and issue notice
    draft_res = client.post(f"/api/v1/inspections/{finalized_inspection}/notice/draft")
    assert draft_res.status_code in (200, 201)
    notice_id = draft_res.json()["id"]

    # Review notice
    review_res = client.post(f"/api/v1/notices/{notice_id}/review", json={
        "officer_notes": "Officer verified inspection evidence."
    })
    assert review_res.status_code == 200

    # Issue notice
    issue_res = client.post(f"/api/v1/notices/{notice_id}/issue", json={
        "officer_notes": "Issued after formal verification.",
    })
    assert issue_res.status_code == 200
    assert issue_res.json()["status"] == "ISSUED_BY_OFFICER"
    assert issue_res.json()["is_immutable"] is True

    # 2. Attempt Inspection ORM deletion
    db = SessionLocal()
    try:
        insp = db.get(Inspection, finalized_inspection)
        assert insp is not None
        notice = db.get(Notice, notice_id)
        assert notice is not None
        assert notice.is_immutable is True

        # Attempt to delete the parent Inspection
        db.delete(insp)
        import pytest
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()

        # 3. Verify issued Notice remains completely intact and immutable in the database
        preserved_notice = db.get(Notice, notice_id)
        assert preserved_notice is not None
        assert preserved_notice.id == notice_id
        assert preserved_notice.inspection_id == finalized_inspection
        assert preserved_notice.status == "ISSUED_BY_OFFICER"
        assert preserved_notice.is_immutable is True
        assert preserved_notice.officer_name == "Default Test Officer"

        # 4. Attempt direct ORM deletion on the issued Notice record
        db.delete(preserved_notice)
        with pytest.raises(ValueError, match="Cannot delete an issued statutory notice"):
            db.commit()

        db.rollback()

        # 5. Final check: Notice is still preserved
        final_check = db.get(Notice, notice_id)
        assert final_check is not None
        assert final_check.is_immutable is True
    finally:
        db.close()

