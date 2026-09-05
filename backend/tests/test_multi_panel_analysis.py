from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage
from app.models.analysis_result import AnalysisResult
from app.models.finding import Finding
from app.services.panel_fusion import (
    PanelDeclarationCandidate,
    FusedFieldResult,
    fuse_panel_declarations,
    normalize_field_value,
    values_are_materially_conflicting,
)
from app.services.image_rotation_service import (
    compute_file_sha256,
    create_rotated_derivative,
    get_active_image_file_path,
    load_rotation_metadata,
)

client = TestClient(app)


def _create_sample_image_bytes(text: str = "SAMPLE", size: tuple[int, int] = (600, 600), color: str = "white") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_values_are_materially_conflicting():
    # Price
    assert values_are_materially_conflicting("retail_sale_price", "250", "299") is True
    assert values_are_materially_conflicting("retail_sale_price", "299", "299") is False

    # Net quantity
    assert values_are_materially_conflicting("net_quantity", "500g", "1kg") is True
    assert values_are_materially_conflicting("net_quantity", "5kg", "5kg") is False

    # Date
    assert values_are_materially_conflicting("month_year", "08/2026", "09/2026") is True
    assert values_are_materially_conflicting("month_year", "09/2026", "09/2026") is False

    # Address / Commodity / Name: elaboration/substring is non-conflicting
    assert values_are_materially_conflicting("manufacturer_name", "praman foods", "praman foods pvt ltd") is False
    assert values_are_materially_conflicting("manufacturer_name", "praman foods", "nestle india ltd") is True


def test_fuse_panel_declarations_conflict_routes_to_manual_review():
    """
    CRITICAL STATUTORY INVARIANT:
    When materially different values for the same declaration are detected across panels,
    OCR confidence must NEVER establish legal truth.
    Both candidates must be preserved, and the check routed to MANUAL_REVIEW.
    """
    per_image_results = [
        {
            "image_id": "img-front",
            "image_type": "front",
            "file_name": "front_pdp.jpg",
            "storage_path": "uploads/front_pdp.jpg",
            "ocr_confidence": 0.99,  # High confidence
            "structured_declarations": {
                "commodity_name": "PRAMAN Premium Rice",
                "net_quantity": "5 kg",
                "retail_sale_price": "₹250.00",  # Front price
            },
        },
        {
            "image_id": "img-back",
            "image_type": "back",
            "file_name": "back_info.jpg",
            "storage_path": "uploads/back_info.jpg",
            "ocr_confidence": 0.72,  # Lower confidence
            "structured_declarations": {
                "manufacturer_name": "PRAMAN Foods Pvt Ltd",
                "manufacturer_address": "Plot 12, Industrial Area, Hyderabad",
                "retail_sale_price": "₹299.00",  # Back price: CONFLICT!
                "month_year": "09/2026",
                "consumer_contact": "care@praman.in",
                "country_of_origin": "India",
            },
        },
    ]

    fused_decls, fused_results = fuse_panel_declarations(per_image_results)

    # Verify retail_sale_price detected conflict
    price_result = fused_results["retail_sale_price"]
    assert price_result.has_conflict is True
    assert price_result.routing == "MANUAL_REVIEW"
    assert "Conflicting declarations detected across panels" in price_result.conflict_description
    assert len(price_result.candidates) == 2

    # Verify both candidates preserved with provenance
    cand_sources = {c.image_type: c.raw_value for c in price_result.candidates}
    assert cand_sources["front"] == "₹250.00"
    assert cand_sources["back"] == "₹299.00"

    # Non-conflicting fields adopted cleanly
    assert fused_decls["commodity_name"] == "PRAMAN Premium Rice"
    assert fused_results["commodity_name"].has_conflict is False
    assert fused_results["commodity_name"].routing == "SAFE"
    assert fused_results["commodity_name"].primary_image_id == "img-front"

    assert fused_decls["consumer_contact"] == "care@praman.in"
    assert fused_results["consumer_contact"].primary_image_id == "img-back"


def test_image_rotation_preserves_original_evidence(tmp_path):
    """
    CRITICAL EVIDENCE INTEGRITY INVARIANT:
    Rotating an image must NEVER overwrite or destroy the pristine original file.
    Original file's SHA-256 hash must remain byte-for-byte identical.
    """
    orig_file = tmp_path / "evidence_label.jpg"
    orig_bytes = _create_sample_image_bytes(text="EVIDENCE", size=(400, 600))
    orig_file.write_bytes(orig_bytes)

    initial_sha256 = compute_file_sha256(orig_file)

    # 1. Rotate 90 degrees
    deriv_path, meta = create_rotated_derivative(orig_file, 90)

    # Verify derivative created
    assert deriv_path.exists()
    assert deriv_path != orig_file
    assert deriv_path.name.endswith(".rot_90.jpg")

    # Verify original file untouched and SHA-256 unchanged
    post_rot_sha256 = compute_file_sha256(orig_file)
    assert post_rot_sha256 == initial_sha256

    # Verify metadata sidecar
    assert meta["original_sha256"] == initial_sha256
    assert meta["rotation_angle"] == 90
    assert meta["is_derivative"] is True
    assert meta["original_preserved"] is True

    # 2. Verify active path resolves to derivative
    active_path, angle = get_active_image_file_path(orig_file)
    assert active_path == deriv_path
    assert angle == 90

    # 3. Rotate back to 0 degrees
    reset_path, reset_meta = create_rotated_derivative(orig_file, 0)
    assert reset_path == orig_file
    assert reset_meta["rotation_angle"] == 0
    assert compute_file_sha256(orig_file) == initial_sha256


def test_multi_panel_api_end_to_end_flow(tmp_path, monkeypatch):
    """
    Tests complete multi-panel inspection intake, rotation, fusion,
    panel-attributed findings, and conflict handling via API.
    """
    import uuid
    # 1. Create draft inspection
    insp_num = f"INSP-MP-{uuid.uuid4().hex[:8]}"
    create_resp = client.post(
        "/api/v1/inspections",
        json={
            "inspection_number": insp_num,
            "title": "Multi-Panel Basmati Rice Test",
            "notes": "Domestic packaged rice",
        },
    )
    assert create_resp.status_code == 201
    insp_id = create_resp.json()["id"]

    # 2. Upload Front Panel
    front_bytes = _create_sample_image_bytes(text="FRONT PDP", color="lightblue")
    front_upload = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("pdp_front.jpg", front_bytes, "image/jpeg"))],
        data={"image_type": "front"},
    )
    assert front_upload.status_code == 201
    front_img_id = front_upload.json()[0]["id"]

    # 3. Upload Back Panel
    back_bytes = _create_sample_image_bytes(text="BACK INFO", color="lightyellow")
    back_upload = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("info_back.jpg", back_bytes, "image/jpeg"))],
        data={"image_type": "back"},
    )
    assert back_upload.status_code == 201
    back_img_id = back_upload.json()[0]["id"]

    # 4. Rotate Front Panel by 90 degrees
    rotate_resp = client.patch(
        f"/api/v1/inspections/{insp_id}/images/{front_img_id}/rotate",
        json={"angle": 90},
    )
    assert rotate_resp.status_code == 200
    rot_data = rotate_resp.json()
    assert rot_data["rotation_metadata"]["rotation_angle"] == 90
    assert rot_data["rotation_metadata"]["original_preserved"] is True

    # 5. Fetch image file (derivative vs original)
    deriv_file_resp = client.get(f"/api/v1/inspections/{insp_id}/images/{front_img_id}/file")
    assert deriv_file_resp.status_code == 200

    orig_file_resp = client.get(f"/api/v1/inspections/{insp_id}/images/{front_img_id}/file?original=true")
    assert orig_file_resp.status_code == 200

    # 6. Mock OCRService to simulate real multi-panel extracted declarations
    from app.services.ocr_service import OCRService

    def mock_analyze_image(file_path, inspection_id):
        fname = str(file_path).lower()
        if "pdp_front" in fname:
            return {
                "inspection_id": inspection_id,
                "status": "completed",
                "confidence": 0.95,
                "ocr_text": "PRAMAN Basmati Rice\nNet Qty: 5 kg\nMRP: Rs 250.00",
                "ocr_confidence": 0.95,
                "ocr_regions": [],
                "extraction_metadata": {"model": "PaddleOCR", "real_ocr_used": True},
                "structured_declarations": {
                    "commodity_name": "PRAMAN Basmati Rice",
                    "net_quantity": "5 kg",
                    "retail_sale_price": "250.00",  # Conflicting with back!
                },
            }
        else:
            return {
                "inspection_id": inspection_id,
                "status": "completed",
                "confidence": 0.88,
                "ocr_text": "PRAMAN Foods Pvt Ltd\nHyderabad\nMRP Rs 299.00\n09/2026\ncare@praman.in\nIndia",
                "ocr_confidence": 0.88,
                "ocr_regions": [],
                "extraction_metadata": {"model": "PaddleOCR", "real_ocr_used": True},
                "structured_declarations": {
                    "manufacturer_name": "PRAMAN Foods Pvt Ltd",
                    "manufacturer_address": "Plot 12, Industrial Area, Hyderabad",
                    "retail_sale_price": "299.00",  # Conflicting with front!
                    "month_year": "09/2026",
                    "consumer_contact": "care@praman.in",
                    "country_of_origin": "India",
                },
            }

    monkeypatch.setattr(OCRService, "analyze_image", mock_analyze_image)

    # 7. Run Multi-Panel Analysis
    analyze_resp = client.post(f"/api/v1/inspections/{insp_id}/analyze")
    assert analyze_resp.status_code == 201
    analysis_result = analyze_resp.json()

    assert analysis_result["status"] == "completed"
    meta = analysis_result["extraction_metadata"]
    assert "panel_conflicts" in meta
    assert "retail_sale_price" in meta["panel_conflicts"]
    assert meta["panel_conflicts"]["retail_sale_price"]["has_conflict"] is True
    assert meta["panel_conflicts"]["retail_sale_price"]["routing"] == "MANUAL_REVIEW"

    # 8. Verify Findings Attribution and Conflict Handling
    findings_resp = client.get(f"/api/v1/inspections/{insp_id}/findings")
    assert findings_resp.status_code == 200
    findings = findings_resp.json()

    # Find the MRP check (PCR-2011-R06-06 or PCR-006)
    mrp_finding = next((f for f in findings if "R06-06" in f["rule_check_id"] or "006" in f["rule_check_id"]), None)
    assert mrp_finding is not None
    assert mrp_finding["severity"] == "warning"
    assert "Conflicting declarations" in mrp_finding["title"]
    assert mrp_finding["rule_status"] == "MANUAL_REVIEW"
    assert mrp_finding["has_conflict"] is True

    # Find commodity name finding (PCR-003): must link to Front panel image
    commodity_finding = next((f for f in findings if "003" in f["rule_check_id"]), None)
    assert commodity_finding is not None
    assert commodity_finding["image_id"] == front_img_id

    # Find manufacturer finding (PCR-001): must link to Back panel image
    mfg_finding = next((f for f in findings if "001" in f["rule_check_id"]), None)
    assert mfg_finding is not None
    assert mfg_finding["image_id"] == back_img_id

    # 9. Verify Inspector Review Resolves Conflict
    update_resp = client.patch(
        f"/api/v1/inspections/{insp_id}/declarations",
        json={"declarations": {"retail_sale_price": "299.00"}, "notes": "Verified against shelf and back label MRP"},
    )
    assert update_resp.status_code == 200

    # After human correction, finding should be updated
    post_findings = client.get(f"/api/v1/inspections/{insp_id}/findings").json()
    post_mrp = next((f for f in post_findings if "R06-06" in f["rule_check_id"] or "006" in f["rule_check_id"]), None)
    assert post_mrp is not None
    assert "Conflicting declarations" not in post_mrp["title"]
