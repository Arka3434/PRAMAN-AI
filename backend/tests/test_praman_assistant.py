"""Tests for Phase 14: Evidence-Grounded PRAMAN Inspection Assistant

Verifies:
- Explain finding with administrative inspector decision framing.
- Strict statutory mapping guardrail: does NOT independently invent Act sections.
- Authoritative statutory mapping explained only when recorded in Notice.
- Inspection deterministic summary with raw image quality metrics (no invented score).
- Evidence trace for optical and declaration provenance.
- Manual review guidance for physical verification (net quantity, MPE, tare).
- Read-only behavior (no database mutations).
- Appropriate 404 responses for missing resources.
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage
from app.models.product import Product
from app.models.review_decision import ReviewDecision
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def assistant_test_env():
    """Sets up an inspection with findings, analysis result, and images for assistant tests."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter_by(email="sharma@lm.gov.in").first()
        if not user:
            user = User(
                email="sharma@lm.gov.in",
                full_name="A. Sharma",
                role="inspector",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        product = db.query(Product).first()
        if not product:
            product = Product(
                name="Test Packaged Atta 5kg",
                category="FOOD",
                brand="TestBrand",
            )
            db.add(product)
            db.commit()
            db.refresh(product)

        from uuid import uuid4
        uid = uuid4().hex[:8]
        insp = Inspection(
            inspection_number=f"INSP-ASST-{uid}",
            inspector_id=user.id,
            product_id=product.id,
            status="in_progress",
            title="Assistant Test Inspection",
        )
        db.add(insp)
        db.commit()
        db.refresh(insp)

        # Images
        img1 = InspectionImage(
            inspection_id=insp.id,
            image_type="primary",
            file_name="front.jpg",
            storage_path="uploads/test_front.jpg",
            width=1920,
            height=1080,
        )
        img2 = InspectionImage(
            inspection_id=insp.id,
            image_type="secondary",
            file_name="back.jpg",
            storage_path="uploads/test_back.jpg",
            width=1920,
            height=1080,
        )
        db.add_all([img1, img2])
        db.commit()
        db.refresh(img1)
        db.refresh(img2)

        # Analysis Result with structured declarations
        ar = AnalysisResult(
            inspection_id=insp.id,
            status="completed",
            confidence=0.92,
            structured_declarations={
                "PCR-006": {"raw_text": "MRP Rs. 250.00 (incl. of all taxes)", "normalized_value": 250.0},
                "PCR-003": {"raw_text": "Net Qty: 5 kg", "normalized_value": "5 kg"},
            },
        )
        db.add(ar)
        db.commit()

        # Findings
        f_mrp = Finding(
            inspection_id=insp.id,
            rule_check_id="PCR-006",
            title="Maximum Retail Price Declaration",
            severity="high",
            status="open",
            description="Unit sale price not declared alongside retail sale price.",
            detected_value="250.0",
            evidence_reference=json.dumps({
                "source_image": "front.jpg",
                "image_id": img1.id,
                "panel_type": "FRONT",
                "evidence_snippet": "MRP Rs. 250.00 (incl. of all taxes)",
                "evidence_location": [[10, 10], [100, 10], [100, 40], [10, 40]],
                "ocr_confidence": 0.92,
                "rule_status": "FAIL",
            }),
        )
        f_net_qty = Finding(
            inspection_id=insp.id,
            rule_check_id="PCR-003",
            title="Net Quantity Physical Verification",
            severity="medium",
            status="open",
            description="Net quantity declared as 5 kg; physical weight measurement required to verify actual contents.",
            detected_value="5 kg",
            evidence_reference=json.dumps({
                "source_image": "back.jpg",
                "image_id": img2.id,
                "panel_type": "BACK",
                "evidence_snippet": "Net Qty: 5 kg",
                "evidence_location": [[20, 20], [150, 20], [150, 50], [20, 50]],
                "ocr_confidence": 0.88,
                "rule_status": "MANUAL_REVIEW",
            }),
        )
        db.add_all([f_mrp, f_net_qty])
        db.commit()
        db.refresh(f_mrp)
        db.refresh(f_net_qty)

        # Record inspector decision for f_mrp
        rd = ReviewDecision(
            inspection_id=insp.id,
            decision="CONFIRMED",
            reviewer_name="Inspector A. Sharma",
            notes=json.dumps({"finding_id": f_mrp.id, "notes": "Officer verified missing unit sale price."}),
        )
        db.add(rd)
        db.commit()

        yield {
            "inspection_id": insp.id,
            "mrp_finding_id": f_mrp.id,
            "net_qty_finding_id": f_net_qty.id,
            "img1_id": img1.id,
            "img2_id": img2.id,
        }
    finally:
        db.close()


def test_explain_finding_unrecorded_statutory_mapping(assistant_test_env):
    """Verifies that the assistant does not invent statutory mappings when no Notice exists."""
    insp_id = assistant_test_env["inspection_id"]
    finding_id = assistant_test_env["mrp_finding_id"]

    res = client.get(f"/api/v1/inspections/{insp_id}/assistant/explain-finding?finding_id={finding_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["finding_id"] == finding_id
    assert data["rule_check_id"] == "PCR-006"
    assert data["rule_status"] == "FAIL"
    assert data["inspector_decision"] == "CONFIRMED"
    # Framing: administrative confirmation, not judicial guilt
    assert "Administrative inspector review: Confirmed finding" in data["inspector_decision_framing"]
    assert "does not constitute judicial determination" in data["inspector_decision_framing"]

    # Strict statutory mapping guardrail: does not invent Act section
    assert data["statutory_mapping_status"] == "MANUAL_LEGAL_REVIEW_REQUIRED"
    assert data["statutory_reference"] is None
    assert "The assistant does not independently infer statutory mappings" in data["statutory_mapping_explanation"]

    # Evidence grounding
    assert data["evidence_snippet"] == "MRP Rs. 250.00 (incl. of all taxes)"
    assert data["evidence_panel"] == "FRONT"
    assert data["ocr_confidence"] == 0.92

    # Mandatory disclaimer present
    assert "PRAMAN Assistant provides evidence-grounded informational assistance only" in data["disclaimer"]


def test_explain_finding_with_recorded_statutory_mapping(assistant_test_env):
    """Verifies explanation explains an existing statutory charge when recorded in a Notice."""
    insp_id = assistant_test_env["inspection_id"]
    finding_id = assistant_test_env["mrp_finding_id"]

    db = SessionLocal()
    try:
        insp = db.get(Inspection, insp_id)
        insp.status = "COMPLETED"
        db.commit()
    finally:
        db.close()

    # Draft a notice first (Phase 13 endpoint)
    draft_res = client.post(f"/api/v1/inspections/{insp_id}/notice/draft")
    assert draft_res.status_code in (200, 201)

    res = client.get(f"/api/v1/inspections/{insp_id}/assistant/explain-finding?finding_id={finding_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["statutory_mapping_status"] == "RECORDED_IN_NOTICE"
    assert data["statutory_reference"] is not None
    assert "Authoritative statutory charge recorded in Notice" in data["statutory_mapping_explanation"]


def test_summarize_inspection(assistant_test_env):
    """Verifies deterministic inspection summary with raw quality metrics and review status."""
    insp_id = assistant_test_env["inspection_id"]

    res = client.get(f"/api/v1/inspections/{insp_id}/assistant/summarize")
    assert res.status_code == 200
    data = res.json()

    assert data["inspection_id"] == insp_id
    assert data["panel_count"] == 2
    assert "image_quality_assessments" in data
    # Quality metrics are raw diagnostic metrics (no aggregate normalized 0-100 score)
    assert len(data["image_quality_assessments"]) == 2
    for qa in data["image_quality_assessments"]:
        assert "assessment" in qa
        assert "sharpness" in qa
        assert "glare_score" in qa

    assert data["engine_evaluation_summary"]["FAIL"] == 1
    assert data["engine_evaluation_summary"]["MANUAL_REVIEW"] == 1
    assert data["inspector_review_summary"]["CONFIRMED"] == 1
    assert data["inspector_review_summary"]["PENDING"] == 1

    assert any("pending inspector review" in item.lower() for item in data["unresolved_items"])
    assert "PRAMAN Assistant provides evidence-grounded" in data["disclaimer"]


def test_evidence_trace(assistant_test_env):
    """Verifies evidence tracing to optical declaration, panel, and bounding box."""
    insp_id = assistant_test_env["inspection_id"]
    finding_id = assistant_test_env["mrp_finding_id"]

    res = client.get(f"/api/v1/inspections/{insp_id}/assistant/evidence-trace?finding_id={finding_id}")
    assert res.status_code == 200
    data = res.json()

    assert data["finding_id"] == finding_id
    assert data["rule_check_id"] == "PCR-006"
    assert data["source_panel"] == "FRONT"
    assert data["ocr_snippet"] == "MRP Rs. 250.00 (incl. of all taxes)"
    assert data["bounding_box"] == [[10, 10], [100, 10], [100, 40], [10, 40]]
    assert data["ocr_confidence"] == 0.92
    assert data["applicable_legal_version"] is not None


def test_manual_review_guide(assistant_test_env):
    """Verifies guidance for physical verification items such as Section 36(2) net quantity."""
    insp_id = assistant_test_env["inspection_id"]

    res = client.get(f"/api/v1/inspections/{insp_id}/assistant/manual-review-guide")
    assert res.status_code == 200
    data = res.json()

    assert data["inspection_id"] == insp_id
    assert data["unresolved_discrepancies_count"] >= 1
    net_qty_items = [m for m in data["manual_review_items"] if m["identifier"] == "PCR-003"]
    assert len(net_qty_items) == 1
    item = net_qty_items[0]
    assert "Section 36(2)" in item["reason"]
    assert "calibrated" in item["reason"].lower()
    assert any("tare weight" in step.lower() for step in item["verification_checklist"])
    assert "Camera and OCR data cannot measure actual container contents" in item["why_assistant_cannot_resolve"]


def test_assistant_read_only_invariant(assistant_test_env):
    """Proves that calling assistant endpoints does NOT modify any inspection or finding state."""
    db = SessionLocal()
    try:
        insp_id = assistant_test_env["inspection_id"]
        finding_id = assistant_test_env["mrp_finding_id"]

        f_before = db.get(Finding, finding_id)
        status_before = f_before.status
        decision_before = f_before.inspector_decision

        # Query all assistant endpoints
        client.get(f"/api/v1/inspections/{insp_id}/assistant/explain-finding?finding_id={finding_id}")
        client.get(f"/api/v1/inspections/{insp_id}/assistant/summarize")
        client.get(f"/api/v1/inspections/{insp_id}/assistant/evidence-trace?finding_id={finding_id}")
        client.get(f"/api/v1/inspections/{insp_id}/assistant/manual-review-guide")

        db.expire_all()
        f_after = db.get(Finding, finding_id)
        assert f_after.status == status_before
        assert f_after.inspector_decision == decision_before
    finally:
        db.close()


def test_assistant_404_handling(assistant_test_env):
    """Verifies clean 404 responses for non-existent inspections or mismatched findings."""
    insp_id = assistant_test_env["inspection_id"]

    res = client.get("/api/v1/inspections/non-existent-id/assistant/summarize")
    assert res.status_code == 404
    assert "Inspection not found" in res.json()["detail"]

    res2 = client.get(f"/api/v1/inspections/{insp_id}/assistant/explain-finding?finding_id=non-existent-finding")
    assert res2.status_code == 404
    assert "Finding not found" in res2.json()["detail"]
