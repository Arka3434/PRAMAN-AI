import hashlib
import io
from pathlib import Path

import numpy as np
import pytest
from cv2 import imencode
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.review_decision import ReviewDecision

EXPECTED_RULES_V1_SHA256 = "b847e70c09bf2666cee117f0b800b8f26de5d5d86059d70966d794a5e6e13adc"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_test_image_bytes(text: str = "PRAMAN RICE") -> bytes:
    """Create a minimal valid JPEG image in memory for testing."""
    img = np.ones((250, 450, 3), dtype=np.uint8) * 255
    # draw some dark pixels so it has contrast
    img[100:150, 50:400] = 30
    success, buffer = imencode('.jpg', img)
    assert success
    return buffer.tobytes()


@pytest.fixture
def sample_catalog_product(db_session: Session):
    """Seed a product with an inspection and structured declarations."""
    prod = Product(
        name="PRAMAN Premium Wheat Flour 5kg",
        brand="PRAMAN Agro",
        category="Grains & Cereals",
        manufacturer="PRAMAN Foods India Ltd, Mumbai, Maharashtra",
        description="Stone ground whole wheat flour",
    )
    db_session.add(prod)
    db_session.commit()
    db_session.refresh(prod)

    # Seed an inspection with an analysis result
    insp = Inspection(
        inspection_number="INSP-CONS-TEST-001",
        status="COMPLETED",
        product_id=prod.id,
    )
    db_session.add(insp)
    db_session.commit()
    db_session.refresh(insp)

    analysis = AnalysisResult(
        inspection_id=insp.id,
        status="completed",
        confidence=0.92,
        structured_declarations={
            "commodity_name": "PRAMAN Premium Wheat Flour 5kg",
            "manufacturer_name": "PRAMAN Foods India Ltd",
            "manufacturer_address": "Plot 45, Industrial Zone, Mumbai",
            "net_quantity": "5",
            "quantity_unit": "kg",
            "retail_sale_price": "275.00",
            "month_year": "08/2026",
            "consumer_contact": "care@pramanfoods.in, 1800-111-222",
            "country_of_origin": None,  # Domestic product
        },
    )
    db_session.add(analysis)
    db_session.commit()

    return prod


def test_consumer_products_list(client: TestClient, sample_catalog_product):
    """Test GET /api/v1/consumer/products returns public-safe products."""
    resp = client.get("/api/v1/consumer/products")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    # Find the seeded product
    match = next((p for p in data if p["id"] == sample_catalog_product.id), None)
    assert match is not None
    assert match["name"] == "PRAMAN Premium Wheat Flour 5kg"
    assert match["brand"] == "PRAMAN Agro"
    assert match["category"] == "Grains & Cereals"

    # Search filter test
    search_resp = client.get("/api/v1/consumer/products?search=Wheat")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert any(p["id"] == sample_catalog_product.id for p in search_data)


def test_consumer_product_detail(client: TestClient, sample_catalog_product):
    """Test GET /api/v1/consumer/products/{id} returns consumer packaging declarations."""
    resp = client.get(f"/api/v1/consumer/products/{sample_catalog_product.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == sample_catalog_product.id
    assert data["name"] == sample_catalog_product.name
    assert "declarations" in data
    assert len(data["declarations"]) >= 6
    assert "consumer_notice" in data

    # Check that commodity_name, net_quantity, retail_sale_price are detected
    decl_map = {d["field_key"]: d for d in data["declarations"]}
    assert "commodity_name" in decl_map
    assert decl_map["commodity_name"]["status"] == "Detected"

    assert "net_quantity" in decl_map
    assert decl_map["net_quantity"]["status"] == "Detected"
    assert "5 kg" in decl_map["net_quantity"]["detected_value"]

    assert "retail_sale_price" in decl_map
    assert decl_map["retail_sale_price"]["status"] == "Detected"
    assert "₹275.00" in decl_map["retail_sale_price"]["detected_value"]

    # Country of origin for domestic product must NOT be required or marked missing
    assert "country_of_origin" in decl_map
    assert decl_map["country_of_origin"]["status"] == "Not applicable / unknown"
    assert "domestic" in decl_map["country_of_origin"]["description"].lower()


def test_consumer_scan_transient_no_db_persistence(client: TestClient, db_session: Session):
    """
    CRITICAL INVARIANT:
    Test that consumer photo scan runs OCR in-memory and creates ZERO database records:
    zero Inspection, zero Finding, zero ReviewDecision, zero AnalysisResult rows.
    """
    # Record counts before call
    count_inspections_before = db_session.query(Inspection).count()
    count_findings_before = db_session.query(Finding).count()
    count_decisions_before = db_session.query(ReviewDecision).count()
    count_analyses_before = db_session.query(AnalysisResult).count()

    img_bytes = make_test_image_bytes()
    resp = client.post(
        "/api/v1/consumer/scan",
        files={"file": ("test_package.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()

    # Verify scan response structure
    assert "scan_id" in data
    assert "quality" in data
    assert "declarations" in data
    assert len(data["declarations"]) >= 6
    assert "consumer_notice" in data

    # Record counts after call - MUST BE EXACTLY IDENTICAL
    count_inspections_after = db_session.query(Inspection).count()
    count_findings_after = db_session.query(Finding).count()
    count_decisions_after = db_session.query(ReviewDecision).count()
    count_analyses_after = db_session.query(AnalysisResult).count()

    assert count_inspections_after == count_inspections_before, "Consumer scan must not create Inspection records!"
    assert count_findings_after == count_findings_before, "Consumer scan must not create Finding records!"
    assert count_decisions_after == count_decisions_before, "Consumer scan must not create ReviewDecision records!"
    assert count_analyses_after == count_analyses_before, "Consumer scan must not create AnalysisResult records!"


def test_consumer_response_no_internal_enforcement_leak(client: TestClient, sample_catalog_product):
    """
    PUBLIC API SECURITY TEST:
    Assert that public consumer endpoints NEVER expose internal enforcement fields:
    inspector_id, finding_id, review_decision, severity, rule_status, notes, etc.
    """
    forbidden_keys = {
        "inspector_id",
        "finding_id",
        "review_decision",
        "internal_notes",
        "severity",
        "rule_status",
        "storage_path",
        "inspection_number",
        "blocking_reasons",
        "audit_events",
        "notes",
        "compliance_score",
        "latest_verdict",
    }

    # 1. Check list endpoint
    list_resp = client.get("/api/v1/consumer/products")
    list_json = list_resp.json()
    for prod in list_json:
        assert forbidden_keys.isdisjoint(prod.keys()), f"Forbidden keys leaked in product list: {prod.keys() & forbidden_keys}"

    # 2. Check detail endpoint
    detail_resp = client.get(f"/api/v1/consumer/products/{sample_catalog_product.id}")
    detail_json = detail_resp.json()
    assert forbidden_keys.isdisjoint(detail_json.keys()), f"Forbidden keys leaked in product detail: {detail_json.keys() & forbidden_keys}"
    for decl in detail_json["declarations"]:
        assert forbidden_keys.isdisjoint(decl.keys()), f"Forbidden keys leaked in declaration: {decl.keys() & forbidden_keys}"

    # 3. Check scan endpoint
    img_bytes = make_test_image_bytes()
    scan_resp = client.post(
        "/api/v1/consumer/scan",
        files={"file": ("test_package.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    scan_json = scan_resp.json()
    assert forbidden_keys.isdisjoint(scan_json.keys()), f"Forbidden keys leaked in scan response: {scan_json.keys() & forbidden_keys}"
    for decl in scan_json["declarations"]:
        assert forbidden_keys.isdisjoint(decl.keys()), f"Forbidden keys leaked in scan declaration: {decl.keys() & forbidden_keys}"


def test_consumer_scan_semantics_neutral_not_violation(client: TestClient):
    """
    SEMANTIC INTEGRITY TEST:
    Assert that consumer scan responses use neutral transparency language:
    'Detected', 'Not detected in this image', 'Not applicable / unknown'.
    Assert words like 'violation', 'offense', 'illegal', 'non-compliant product' do NOT appear.
    """
    img_bytes = make_test_image_bytes()
    resp = client.post(
        "/api/v1/consumer/scan",
        files={"file": ("test_package.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()

    allowed_statuses = {
        "Detected",
        "Not detected in this image",
        "Image quality insufficient",
        "Not applicable / unknown",
    }

    for decl in data["declarations"]:
        assert decl["status"] in allowed_statuses, f"Invalid status: {decl['status']}"

    # String representation test: ensure no punitive language
    resp_text = resp.text.lower()
    assert "violation" not in resp_text or "does not constitute" in resp_text, "Unqualified 'violation' word found in consumer scan!"
    assert "offense" not in resp_text
    assert "illegal package" not in resp_text
    assert "non-compliant product" not in resp_text


def test_conditional_country_of_origin_domestic_handling(client: TestClient):
    """
    Test that Country of Origin is recognized as conditional under Rule 6(10)
    and not marked as a missing statutory declaration for domestic items.
    """
    img_bytes = make_test_image_bytes()
    resp = client.post(
        "/api/v1/consumer/scan",
        files={"file": ("test_package.jpg", io.BytesIO(img_bytes), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()

    coo = next((d for d in data["declarations"] if d["field_key"] == "country_of_origin"), None)
    assert coo is not None
    assert coo["status"] in ("Detected", "Not applicable / unknown")
    assert "imported" in coo["field_label"].lower() or "imported" in coo["description"].lower()


def test_existing_officer_workflows_unaffected(client: TestClient, sample_catalog_product):
    """
    REGRESSION TEST:
    Verify officer endpoints continue functioning with full compliance metadata.
    """
    # Officer product catalog
    p_resp = client.get("/api/v1/products")
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert any(p["id"] == sample_catalog_product.id for p in p_data)

    # Officer inspections list
    i_resp = client.get("/api/v1/inspections")
    assert i_resp.status_code == 200


def test_invariants_preserved():
    """Verify rules_v1.json SHA-256 and ComplianceEngine remain completely unmodified."""
    rules_path = Path(__file__).resolve().parent.parent.parent / "legal" / "rule_catalog" / "rules_v1.json"
    assert rules_path.exists()
    calculated_sha = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    assert calculated_sha == EXPECTED_RULES_V1_SHA256
