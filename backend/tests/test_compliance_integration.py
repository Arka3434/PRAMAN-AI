from __future__ import annotations

import os
import struct
import zlib
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase6_integration_test.db')

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.models.finding import Finding
from app.services.ocr_service import OCRService


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def build_png_bytes() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b'\x00\x00\x00\x00'
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def test_compliant_package_produces_real_pcr_rule_results() -> None:
    """1. Proves compliant package produces real PCR rule results (not DEMO-REQ)."""
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-PCR-001',
        'status': 'DRAFT',
        'title': 'Compliant Rice Bag Inspection',
    })
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    # Upload test image
    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('rice_label.png', build_png_bytes(), 'image/png')},
    )
    assert upload_resp.status_code == 201

    # Trigger analysis (which routes through ComplianceEngine)
    analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_resp.status_code == 201

    # Fetch findings
    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    findings = findings_resp.json()

    assert len(findings) > 0

    # Ensure all rule IDs are real PCR rule IDs, and zero DEMO-REQ IDs exist
    for f in findings:
        assert f['rule_check_id'].startswith('PCR-'), f"Expected PCR rule ID, got {f['rule_check_id']}"
        assert 'DEMO-REQ' not in f['rule_check_id']

    rule_ids = {f['rule_check_id'] for f in findings}
    assert 'PCR-001' in rule_ids
    assert 'PCR-003' in rule_ids
    assert 'PCR-004' in rule_ids
    assert 'PCR-005' in rule_ids
    assert 'PCR-007' in rule_ids

    # PCR-001, PCR-003, PCR-004, PCR-005, PCR-007 should be pass/resolved on standard fallback declarations
    f_by_id = {f['rule_check_id']: f for f in findings}
    assert f_by_id['PCR-001']['status'] == 'resolved'
    assert f_by_id['PCR-001']['severity'] == 'pass'
    assert f_by_id['PCR-004']['status'] == 'resolved'
    assert f_by_id['PCR-004']['severity'] == 'pass'


def test_missing_manufacturer_address_produces_pcr_001_finding() -> None:
    """2. Proves missing manufacturer/address produces a PCR-001 potential violation finding."""
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-PCR-002',
        'status': 'DRAFT',
        'title': 'Missing Address Inspection',
    })
    insp_id = insp_resp.json()['id']

    client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('incomplete_label.png', build_png_bytes(), 'image/png')},
    )

    # Mock OCR output where manufacturer address is missing
    mock_ocr_result = {
        'status': 'completed',
        'confidence': 0.85,
        'ocr_text': 'PRAMAN Rice 5kg\nPrice: Rs 299\nSEPT 2026',
        'ocr_confidence': 0.85,
        'ocr_regions': [],
        'structured_declarations': {
            'commodity_name': 'PRAMAN Rice',
            'manufacturer_name': 'PRAMAN Foods Pvt Ltd',
            'manufacturer_address': None,  # MISSING
            'net_quantity': '5',
            'quantity_unit': 'kg',
            'retail_sale_price': '₹299.00',
            'month_year': 'SEPT 2026',
            'country_of_origin': 'India',
        },
        'extraction_metadata': {'model': 'mock'},
    }

    with patch.object(OCRService, 'analyze_image', return_value=mock_ocr_result):
        analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
        assert analyze_resp.status_code == 201

    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    findings = findings_resp.json()

    pcr_001 = next((f for f in findings if f['rule_check_id'] == 'PCR-001'), None)
    assert pcr_001 is not None, 'PCR-001 finding must be present'
    assert pcr_001['severity'] == 'critical'
    assert pcr_001['status'] == 'open'
    assert 'missing' in pcr_001['description'].lower()


def test_imported_package_without_origin_produces_pcr_002_finding() -> None:
    """3. Proves imported package without country of origin produces PCR-002 violation."""
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-PCR-003',
        'status': 'DRAFT',
        'title': 'Imported Commodity Check',
        'notes': 'Imported shipment consignment from Singapore',
    })
    insp_id = insp_resp.json()['id']

    client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('imported_pkg.png', build_png_bytes(), 'image/png')},
    )

    mock_ocr_result = {
        'status': 'completed',
        'confidence': 0.88,
        'ocr_text': 'Imported Cookies\nImported by: Global Traders Ltd, Mumbai\nNet qty: 500 g\nMRP: Rs 150',
        'ocr_confidence': 0.88,
        'ocr_regions': [],
        'structured_declarations': {
            'commodity_name': 'Imported Cookies',
            'manufacturer_name': 'Global Traders Ltd',
            'manufacturer_address': 'Plot 5, Port Area, Mumbai',
            'net_quantity': '500',
            'quantity_unit': 'g',
            'retail_sale_price': '₹150.00',
            'month_year': '08/2026',
            'country_of_origin': None,  # MISSING on imported package
        },
        'extraction_metadata': {'model': 'mock'},
    }

    with patch.object(OCRService, 'analyze_image', return_value=mock_ocr_result):
        analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
        assert analyze_resp.status_code == 201

    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    findings = findings_resp.json()

    pcr_002 = next((f for f in findings if f['rule_check_id'] == 'PCR-002'), None)
    assert pcr_002 is not None, 'PCR-002 finding must be generated for imported goods'
    assert pcr_002['severity'] == 'critical'
    assert pcr_002['status'] == 'open'
    assert 'country of origin' in pcr_002['description'].lower()


def test_evidence_references_reach_the_persisted_finding() -> None:
    """4. Proves evidence references (filename and matched text) reach the persisted finding."""
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-PCR-004',
        'status': 'DRAFT',
        'title': 'Evidence Traceability Check',
    })
    insp_id = insp_resp.json()['id']

    client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('evidence_label_front.png', build_png_bytes(), 'image/png')},
    )

    analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_resp.status_code == 201

    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    findings = findings_resp.json()

    # All findings should have evidence_reference populated
    for f in findings:
        assert f['evidence_reference'] is not None, f"Finding {f['rule_check_id']} missing evidence_reference"
        assert 'evidence_label_front.png' in f['evidence_reference']


def test_existing_inspection_workflow_still_works() -> None:
    """5. Proves full inspection lifecycle (create, upload, analyze, review, finalize) works seamlessly."""
    # Create product and inspection
    prod_resp = client.post('/api/v1/products', json={'name': 'Lifecycle Test Product'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-PCR-005',
        'status': 'DRAFT',
        'title': 'Full Lifecycle Workflow Test',
        'product_id': prod_id,
    })
    insp_id = insp_resp.json()['id']

    # Upload image
    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('sample.png', build_png_bytes(), 'image/png')},
    )
    assert upload_resp.status_code == 201

    # Analyze
    analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_resp.status_code == 201

    # Check inspection status transitioned to REVIEW_REQUIRED
    insp_detail = client.get(f'/api/v1/inspections/{insp_id}')
    assert insp_detail.json()['status'] == 'REVIEW_REQUIRED'

    # Review decision
    review_resp = client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'confirm',
            'reviewer_name': 'compliance-officer-1',
            'notes': 'Declarations verified against PCR rules.',
        },
    )
    assert review_resp.status_code == 201
    assert review_resp.json()['decision'] == 'confirm'

    # Finalize
    finalize_resp = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_resp.status_code == 200
    assert finalize_resp.json()['status'] == 'COMPLETED'
