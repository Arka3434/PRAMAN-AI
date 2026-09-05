import io
import json
import pytest
import numpy as np
import cv2
from PIL import Image

from app.schemas.quality import QualityVerdict, ImageQualityReport
from app.services.quality_service import (
    assess_image_quality,
    calculate_sharpness,
    calculate_glare_percentage,
    save_quality_metadata,
    load_quality_metadata,
    SHARPNESS_ACCEPTABLE_MIN,
    SHARPNESS_DEGRADED_MIN,
    GLARE_ACCEPTABLE_MAX,
    GLARE_DEGRADED_MAX,
    RESOLUTION_MIN_DIMENSION,
    RESOLUTION_CRITICAL_DIMENSION,
)
from app.services.compliance_engine import ComplianceEngine, InspectionEvaluationContext


def create_synthetic_image(
    width: int = 800,
    height: int = 600,
    pattern: str = "sharp",
    glare_ratio: float = 0.0,
    blur_kernel: int = 0,
) -> np.ndarray:
    """Creates a deterministic synthetic test image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)

    # Base background
    img[:] = (180, 180, 180)

    if pattern == "sharp":
        # Draw crisp high-contrast text and grid lines to generate high Laplacian variance
        for y in range(50, height - 50, 40):
            cv2.putText(
                img,
                f"NET QUANTITY: 500 g | MRP: Rs. 250 | BATCH: BX-2026-09",
                (30, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
        for x in range(20, width, 50):
            cv2.line(img, (x, 0), (x, height), (30, 30, 30), 1)

    # Add glare (pure white pixels > 250)
    if glare_ratio > 0:
        glare_pixels = int(width * height * glare_ratio)
        # Add a concentrated circular glare highlight in center
        radius = int(np.sqrt(glare_pixels / np.pi))
        cv2.circle(img, (width // 2, height // 2), radius, (255, 255, 255), -1)

    # Apply Gaussian blur if specified
    if blur_kernel > 0:
        k = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1
        img = cv2.GaussianBlur(img, (k, k), 0)

    return img


def test_crisp_image_acceptable():
    """A sharp, glare-free, high-res image should evaluate as ACCEPTABLE."""
    img = create_synthetic_image(width=800, height=600, pattern="sharp")
    report = assess_image_quality(img)

    assert report.width == 800
    assert report.height == 600
    assert report.resolution_adequate is True
    assert report.sharpness_score >= SHARPNESS_ACCEPTABLE_MIN
    assert report.glare_percentage <= GLARE_ACCEPTABLE_MAX
    assert report.quality_verdict == QualityVerdict.ACCEPTABLE
    assert len(report.issues) == 0


def test_blurred_image_degraded_or_unreadable():
    """Heavy Gaussian blur should cause sharpness to drop below thresholds."""
    # Extreme blur
    blurry_img = create_synthetic_image(width=800, height=600, pattern="sharp", blur_kernel=45)
    report = assess_image_quality(blurry_img)

    assert report.sharpness_score < SHARPNESS_DEGRADED_MIN
    assert report.quality_verdict == QualityVerdict.UNREADABLE
    assert any("blur" in issue.lower() for issue in report.issues)
    assert any("focus" in rec.lower() for rec in report.recommendations)

    # Moderate blur
    mod_blurry = create_synthetic_image(width=800, height=600, pattern="sharp", blur_kernel=17)
    report_mod = assess_image_quality(mod_blurry)
    assert report_mod.quality_verdict in (QualityVerdict.WARNING_DEGRADED, QualityVerdict.UNREADABLE)


def test_glare_overexposed_image():
    """Severe glare highlight covering >15% of pixels triggers UNREADABLE."""
    glare_img = create_synthetic_image(width=800, height=600, pattern="sharp", glare_ratio=0.20)
    report = assess_image_quality(glare_img)

    assert report.glare_percentage > GLARE_DEGRADED_MAX
    assert report.quality_verdict == QualityVerdict.UNREADABLE
    assert any("glare" in issue.lower() or "flash" in issue.lower() for issue in report.issues)
    assert any("flash" in rec.lower() or "angle" in rec.lower() for rec in report.recommendations)


def test_low_resolution_image():
    """Image with dimensions below heuristic minimum is flagged as low resolution."""
    # Critically small image (< 200px)
    tiny_img = create_synthetic_image(width=150, height=150, pattern="sharp")
    report = assess_image_quality(tiny_img)

    assert report.resolution_adequate is False
    assert report.quality_verdict == QualityVerdict.UNREADABLE
    assert any("resolution" in issue.lower() for issue in report.issues)

    # Suboptimal image (< 400px but >= 200px)
    subopt_img = create_synthetic_image(width=350, height=350, pattern="sharp")
    report_subopt = assess_image_quality(subopt_img)

    assert report_subopt.resolution_adequate is False
    assert report_subopt.quality_verdict in (QualityVerdict.WARNING_DEGRADED, QualityVerdict.UNREADABLE)


def test_deterministic_repeated_results():
    """Assessing the exact same image multiple times produces bit-exact deterministic results."""
    img = create_synthetic_image(width=600, height=600, pattern="sharp", blur_kernel=9, glare_ratio=0.08)
    report_1 = assess_image_quality(img)
    report_2 = assess_image_quality(img)

    assert report_1.sharpness_score == report_2.sharpness_score
    assert report_1.glare_percentage == report_2.glare_percentage
    assert report_1.width == report_2.width
    assert report_1.height == report_2.height
    assert report_1.quality_verdict == report_2.quality_verdict
    assert report_1.issues == report_2.issues
    assert report_1.recommendations == report_2.recommendations


def test_per_image_result_isolation():
    """Two different images must have independent quality results."""
    img_crisp = create_synthetic_image(width=800, height=800, pattern="sharp")
    img_blurry = create_synthetic_image(width=800, height=800, pattern="sharp", blur_kernel=51)

    report_crisp = assess_image_quality(img_crisp)
    report_blurry = assess_image_quality(img_blurry)

    assert report_crisp.quality_verdict == QualityVerdict.ACCEPTABLE
    assert report_blurry.quality_verdict == QualityVerdict.UNREADABLE
    assert report_crisp.sharpness_score > report_blurry.sharpness_score


from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_no_legal_finding_generated_from_quality_failure():
    """
    CRITICAL GUARDRAIL TEST:
    Image quality is evidence-quality diagnostics only.
    It MUST NEVER be treated as a legal compliance result or directly create a statutory violation.
    ComplianceEngine evaluation report must contain zero rules referencing image quality.
    """
    engine = ComplianceEngine()
    catalog_rules = engine.rules.values()

    # Verify no rule in catalog pertains to photographic image quality
    for rule in catalog_rules:
        rule_id = rule.rule_id
        title = rule.title
        assert "image_quality" not in rule_id.lower()
        assert "glare" not in rule_id.lower()
        assert "sharpness" not in rule_id.lower()

    # Evaluate context with dummy declarations
    context = InspectionEvaluationContext(
        inspection_id="test-quality-isolation",
        inspection_date="2026-09-04",
        inspection_context={"is_imported": False, "commodity_category": "food"},
        structured_declarations={
            "mrp": {"value": 100.0, "raw_text": "Rs. 100"},
            "net_quantity": {"value": 500, "unit": "g", "raw_text": "500g"},
            "manufacturer_name": {"value": "Acme Foods", "raw_text": "Acme Foods Ltd"},
            "country_of_origin": {"value": "India", "raw_text": "Made in India"},
            "date_of_manufacture": {"month": 5, "year": 2026, "raw_text": "05/2026"},
        },
        ocr_evidence={"source_file": "blurry_unreadable.jpg"},
    )
    evaluation = engine.evaluate(context)

    # Verify all evaluated rules are statutory legal rules only
    rule_ids = [ev.rule_id for ev in evaluation.evaluations]
    for rid in rule_ids:
        assert not rid.startswith("CV_")
        assert not rid.startswith("IMG_")
        assert not rid.startswith("QUALITY_")


def test_api_upload_returns_quality_assessment(client, db):
    """Uploading an image returns quality_assessment in the JSON response."""
    import uuid
    # Create an inspection
    create_resp = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-QUAL-{uuid.uuid4().hex[:6]}", "title": "Quality API Test"}
    )
    assert create_resp.status_code == 201
    inspection_id = create_resp.json()["id"]

    # Generate a PNG image in-memory
    pil_img = Image.new("RGB", (600, 600), color=(200, 200, 200))
    img_byte_arr = io.BytesIO()
    pil_img.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    upload_resp = client.post(
        f"/api/v1/inspections/{inspection_id}/upload-image",
        files={"file": ("test_packaging.png", img_bytes, "image/png")},
    )
    assert upload_resp.status_code == 201
    data = upload_resp.json()
    assert "quality_assessment" in data
    qa = data["quality_assessment"]
    assert qa is not None
    assert "sharpness_score" in qa
    assert "glare_percentage" in qa
    assert "width" in qa
    assert "height" in qa
    assert "resolution_adequate" in qa
    assert "quality_verdict" in qa
    assert qa["quality_verdict"] in ["ACCEPTABLE", "WARNING_DEGRADED", "UNREADABLE"]

    # Also check GET /images returns quality_assessment
    list_resp = client.get(f"/api/v1/inspections/{inspection_id}/images")
    assert list_resp.status_code == 200
    images_data = list_resp.json()
    assert len(images_data) >= 1
    assert images_data[0]["quality_assessment"] is not None
    assert images_data[0]["quality_assessment"]["quality_verdict"] in ["ACCEPTABLE", "WARNING_DEGRADED", "UNREADABLE"]

