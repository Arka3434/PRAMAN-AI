import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
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


def test_list_products_returns_live_records_and_aggregates(client: TestClient, db_session: Session):
    # 1. Create a product
    product = Product(
        name="Basmati Rice 5kg",
        category="Food & Beverages",
        brand="Heritage",
        manufacturer="Heritage Foods Ltd",
        description="Premium long grain basmati rice.",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    # 2. Add two inspections with findings
    # Inspection 1: 2 PASS, 1 POTENTIAL_VIOLATION
    insp1 = Inspection(
        inspection_number="INSP-PROD-001",
        status="REVIEW_REQUIRED",
        title="Batch A inspection",
        product_id=product.id,
        created_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(insp1)
    db_session.commit()
    db_session.refresh(insp1)

    ar1 = AnalysisResult(
        inspection_id=insp1.id,
        status="completed",
        confidence=0.92,
        structured_declarations={"net_quantity": "5 kg"},
    )
    db_session.add(ar1)

    f1 = Finding(
        inspection_id=insp1.id,
        rule_check_id="LM-DEMO-001",
        severity="low",
        status="open",
        title="Commodity name check",
        description="Passed",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    f2 = Finding(
        inspection_id=insp1.id,
        rule_check_id="LM-DEMO-002",
        severity="low",
        status="open",
        title="Net quantity check",
        description="Passed",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    f3 = Finding(
        inspection_id=insp1.id,
        rule_check_id="LM-DEMO-003",
        severity="major",
        status="open",
        title="MRP check",
        description="MRP not declared",
        evidence_reference=json.dumps({"rule_status": "POTENTIAL_VIOLATION"}),
    )
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    # Inspection 2 (later): 3 PASS checks
    insp2 = Inspection(
        inspection_number="INSP-PROD-002",
        status="COMPLETED",
        title="Batch B inspection",
        product_id=product.id,
        created_at=datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(insp2)
    db_session.commit()
    db_session.refresh(insp2)

    ar2 = AnalysisResult(
        inspection_id=insp2.id,
        status="completed",
        confidence=0.95,
        structured_declarations={"net_quantity": "5 kg", "mrp": "Rs 350"},
    )
    db_session.add(ar2)

    f4 = Finding(
        inspection_id=insp2.id,
        rule_check_id="LM-DEMO-001",
        severity="low",
        status="open",
        title="Commodity name check",
        description="Passed",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    f5 = Finding(
        inspection_id=insp2.id,
        rule_check_id="LM-DEMO-002",
        severity="low",
        status="open",
        title="Net quantity check",
        description="Passed",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    f6 = Finding(
        inspection_id=insp2.id,
        rule_check_id="LM-DEMO-003",
        severity="low",
        status="open",
        title="MRP check",
        description="Passed",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    db_session.add_all([f4, f5, f6])
    db_session.commit()

    # GET /api/v1/products
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["name"] == "Basmati Rice 5kg"
    assert item["inspection_count"] == 2
    # Total evaluated = 3 (from insp1) + 3 (from insp2) = 6. Total PASS = 2 + 3 = 5.
    # Score = 5 / 6 * 100 = 83.3
    assert item["compliance_score"] == 83.3
    # Latest inspection (insp2) has 3 PASS checks, so latest_verdict is COMPLIANT
    assert item["latest_verdict"] == "COMPLIANT"


def test_two_inspections_selecting_same_product_reuses_one_record(client: TestClient, db_session: Session):
    """Clarification 6: Two inspections selecting the same product reuse one Product record."""
    # 1. Create a single product
    create_res = client.post(
        "/api/v1/products",
        json={
            "name": "Organic Almond Milk 1L",
            "category": "Food & Beverages",
            "brand": "NutriLife",
            "manufacturer": "NutriLife Organics",
            "description": "Plant-based beverage.",
        },
    )
    assert create_res.status_code == 201
    prod_data = create_res.json()
    product_id = prod_data["id"]

    # 2. Inspection 1 links to this product_id
    insp1_res = client.post(
        "/api/v1/inspections",
        json={
            "inspection_number": "INSP-REUSE-001",
            "title": "Shelf Check 1",
            "product_id": product_id,
        },
    )
    assert insp1_res.status_code == 201
    insp1_id = insp1_res.json()["id"]

    # 3. Inspection 2 links to the SAME product_id
    insp2_res = client.post(
        "/api/v1/inspections",
        json={
            "inspection_number": "INSP-REUSE-002",
            "title": "Shelf Check 2",
            "product_id": product_id,
        },
    )
    assert insp2_res.status_code == 201
    insp2_id = insp2_res.json()["id"]

    # 4. Verify total products in DB is strictly 1
    all_products_res = client.get("/api/v1/products")
    assert all_products_res.status_code == 200
    all_prods = all_products_res.json()
    assert len(all_prods) == 1
    assert all_prods[0]["id"] == product_id
    assert all_prods[0]["inspection_count"] == 2

    # 5. Verify product detail endpoint returns both inspections
    detail_res = client.get(f"/api/v1/products/{product_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["inspection_count"] == 2
    linked_ids = {insp["id"] for insp in detail["inspections"]}
    assert linked_ids == {insp1_id, insp2_id}


def test_editing_product_metadata_does_not_alter_historical_inspection_data(client: TestClient, db_session: Session):
    """Clarification 4 & 6: Product metadata edits must not alter historical inspection evidence, OCR/declarations, findings, or review decisions."""
    # 1. Setup Product, Inspection, AnalysisResult, Finding, and ReviewDecision
    product = Product(
        name="Original Product Name",
        brand="Original Brand",
        category="Electronics",
        manufacturer="Original Mfr",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    insp = Inspection(
        inspection_number="INSP-HIST-001",
        status="REVIEW_REQUIRED",
        title="Initial Inspection",
        product_id=product.id,
    )
    db_session.add(insp)
    db_session.commit()
    db_session.refresh(insp)

    raw_ocr = "RAW OCR TEXT CONFIDENTIAL EVIDENCE"
    structured_decl = {"mrp": "Rs 999", "net_quantity": "1 Unit"}
    ar = AnalysisResult(
        inspection_id=insp.id,
        status="completed",
        confidence=0.88,
        ocr_text=raw_ocr,
        structured_declarations=structured_decl,
        extraction_metadata={"raw_ocr_declarations": structured_decl},
    )
    db_session.add(ar)

    finding = Finding(
        inspection_id=insp.id,
        rule_check_id="LM-DEMO-001",
        severity="major",
        status="open",
        title="Statutory Finding",
        description="Initial finding description",
        evidence_reference=json.dumps({"rule_status": "POTENTIAL_VIOLATION"}),
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    decision = ReviewDecision(
        inspection_id=insp.id,
        decision="confirmed",
        notes=json.dumps({"finding_id": finding.id, "notes": "Inspector verified statutory non-compliance."}),
    )
    db_session.add(decision)
    db_session.commit()

    # 2. Update Product metadata via PATCH /api/v1/products/{id}
    patch_res = client.patch(
        f"/api/v1/products/{product.id}",
        json={
            "name": "Updated Product Name 2.0",
            "brand": "Updated Brand Group",
            "manufacturer": "New Manufacturer Entity",
        },
    )
    assert patch_res.status_code == 200
    updated_summary = patch_res.json()
    assert updated_summary["name"] == "Updated Product Name 2.0"
    assert updated_summary["brand"] == "Updated Brand Group"

    # 3. Re-query inspection and verify all historical evidence remains 100% untouched
    re_ar = db_session.get(AnalysisResult, ar.id)
    assert re_ar.ocr_text == raw_ocr
    assert re_ar.structured_declarations == structured_decl
    assert re_ar.extraction_metadata["raw_ocr_declarations"] == structured_decl

    re_finding = db_session.get(Finding, finding.id)
    assert re_finding.title == "Statutory Finding"
    assert re_finding.rule_status == "POTENTIAL_VIOLATION"
    assert re_finding.severity == "major"

    re_decision = db_session.get(ReviewDecision, decision.id)
    assert re_decision.decision == "confirmed"
    assert re_decision.comment == "Inspector verified statutory non-compliance."

    re_insp = db_session.get(Inspection, insp.id)
    assert re_insp.inspection_number == "INSP-HIST-001"
    assert re_insp.product_id == product.id


def test_latest_verdict_derives_strictly_from_statutory_state_and_inspector_decision_never_converts_violation(
    client: TestClient, db_session: Session
):
    """Clarification 2: latest_verdict must derive from the inspection's statutory evaluation state.
    Inspector decisions must never convert a statutory POTENTIAL_VIOLATION into PASS."""
    product = Product(name="Juice Box 200ml", category="Food & Beverages")
    db_session.add(product)
    db_session.commit()

    insp = Inspection(
        inspection_number="INSP-STAT-001",
        status="REVIEW_REQUIRED",
        product_id=product.id,
    )
    db_session.add(insp)
    db_session.commit()

    ar = AnalysisResult(
        inspection_id=insp.id,
        status="completed",
        confidence=0.91,
        structured_declarations={"net_quantity": "200 ml"},
    )
    db_session.add(ar)

    finding = Finding(
        inspection_id=insp.id,
        rule_check_id="LM-DEMO-002",
        severity="major",
        status="resolved",  # Even if status is marked resolved or rejected
        title="Missing Date of Manufacture",
        description="Date not found",
        evidence_reference=json.dumps({"rule_status": "POTENTIAL_VIOLATION"}),
    )
    db_session.add(finding)
    db_session.commit()

    # Inspector rejected the finding
    rd = ReviewDecision(
        inspection_id=insp.id,
        decision="rejected",
        notes=json.dumps({"finding_id": finding.id, "notes": "Inspector rejected finding"}),
    )
    db_session.add(rd)
    db_session.commit()

    # Verify latest_verdict is strictly POTENTIAL_VIOLATION
    res = client.get(f"/api/v1/products/{product.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["latest_verdict"] == "POTENTIAL_VIOLATION"


def test_product_deletion_safeguards(client: TestClient, db_session: Session):
    """Clarification 4: Do not expose hard deletion for products with linked inspections."""
    # Product WITH linked inspection
    product_with_insp = Product(name="Protected Product")
    db_session.add(product_with_insp)
    db_session.commit()

    insp = Inspection(
        inspection_number="INSP-DEL-001",
        product_id=product_with_insp.id,
    )
    db_session.add(insp)
    db_session.commit()

    # Deleting product with inspections must fail
    del_res = client.delete(f"/api/v1/products/{product_with_insp.id}")
    assert del_res.status_code == 400
    assert "Cannot delete product with existing inspection history" in del_res.json()["detail"]

    # Product WITHOUT linked inspection
    product_without_insp = Product(name="Orphan Product")
    db_session.add(product_without_insp)
    db_session.commit()

    del_orphan_res = client.delete(f"/api/v1/products/{product_without_insp.id}")
    assert del_orphan_res.status_code == 204


def test_product_search_and_category_filtering(client: TestClient, db_session: Session):
    p1 = Product(name="Sunflower Cooking Oil 1L", category="Food & Beverages", brand="SunGold", manufacturer="Agro Mills")
    p2 = Product(name="Herbal Shampoo 250ml", category="Cosmetics", brand="AyurCare", manufacturer="AyurCare Labs")
    p3 = Product(name="Wireless Earbuds", category="Electronics", brand="SoundWave", manufacturer="AudioTech Corp")
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    # Search by name
    res_name = client.get("/api/v1/products?search=Sunflower")
    assert res_name.status_code == 200
    items = res_name.json()
    assert len(items) == 1
    assert items[0]["name"] == "Sunflower Cooking Oil 1L"

    # Search by brand
    res_brand = client.get("/api/v1/products?search=AyurCare")
    assert res_brand.status_code == 200
    items = res_brand.json()
    assert len(items) == 1
    assert items[0]["name"] == "Herbal Shampoo 250ml"

    # Filter by category
    res_cat = client.get("/api/v1/products?category=Electronics")
    assert res_cat.status_code == 200
    items = res_cat.json()
    assert len(items) == 1
    assert items[0]["name"] == "Wireless Earbuds"


def test_compliance_score_excludes_not_applicable(client: TestClient, db_session: Session):
    """Preserve Phase 7 scoring: NOT_APPLICABLE excluded from denominator."""
    product = Product(name="Exclusion Test Product")
    db_session.add(product)
    db_session.commit()

    insp = Inspection(
        inspection_number="INSP-NA-001",
        product_id=product.id,
    )
    db_session.add(insp)
    db_session.commit()

    ar = AnalysisResult(
        inspection_id=insp.id,
        status="completed",
        confidence=0.9,
        structured_declarations={"net_quantity": "1 kg"},
    )
    db_session.add(ar)

    f1 = Finding(
        inspection_id=insp.id,
        rule_check_id="LM-DEMO-001",
        severity="low",
        status="open",
        title="Check 1",
        description="Check 1 desc",
        evidence_reference=json.dumps({"rule_status": "PASS"}),
    )
    f2 = Finding(
        inspection_id=insp.id,
        rule_check_id="LM-DEMO-002",
        severity="low",
        status="open",
        title="Check 2",
        description="Check 2 desc",
        evidence_reference=json.dumps({"rule_status": "NOT_APPLICABLE"}),
    )
    db_session.add_all([f1, f2])
    db_session.commit()

    res = client.get(f"/api/v1/products/{product.id}")
    assert res.status_code == 200
    data = res.json()
    # 1 PASS / 1 evaluated (NOT_APPLICABLE excluded) = 100.0%
    assert data["compliance_score"] == 100.0


def test_rules_catalog_hash_and_compliance_engine_unmodified():
    """Invariants: rules_v1.json SHA-256 and compliance_engine.py remain completely unmodified."""
    rules_path = Path(__file__).resolve().parent.parent.parent / "legal" / "rule_catalog" / "rules_v1.json"
    assert rules_path.exists(), f"rules_v1.json not found at {rules_path}"
    actual_hash = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    assert actual_hash == EXPECTED_RULES_V1_SHA256, (
        f"rules_v1.json has been modified! Expected {EXPECTED_RULES_V1_SHA256}, got {actual_hash}"
    )

    diff_output = subprocess.run(
        ["git", "diff", "backend/app/services/compliance_engine.py"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent.parent),
    )
    assert diff_output.stdout.strip() == "", "compliance_engine.py has uncommitted changes!"
