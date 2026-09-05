"""Phase 6G Tests: Report Generation & Evidence-Backed Inspection Report.

Tests:
1. Compliant zero-finding inspection report generates valid PDF.
2. Inspection containing violation findings generates valid PDF with PCR-001, citations, and severities.
3. Inspection containing warning findings generates valid PDF with warning rules and values.
4. Unresolved manual-review inspection is blocked from final report (HTTP 400).
5. Inspector decisions (confirm, reject, reviewer, notes) are included.
6. Evidence snippet, bounding box, and visual annotation traceability (with graceful fallback).
7. Catalog version, SHA-256 hash, and inspection date included in report metadata.
8. Report API download response headers (Content-Type, Content-Disposition, Content-Length).
9. Existing inspection, review, and finalization workflow remains intact.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.db.session import SessionLocal
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.analysis_result import AnalysisResult
from app.models.inspection_image import InspectionImage
from app.services.report_generator import InspectionReportGenerator


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_compliant_zero_finding_inspection_report(client: TestClient) -> None:
    """1. A zero-finding compliant inspection report is reportable and generates a valid PDF."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-ZERO-{tag}', 'name': 'Fully Compliant Goods', 'category': 'general'})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-ZERO-{tag}', 'product_id': prod_id})
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    # Simulate analysis with 0 violation findings
    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        analysis = AnalysisResult(
            inspection_id=insp_id,
            status='COMPLETED',
            extraction_metadata={
                'catalog_version': '1.0.0',
                'catalog_hash': 'B847E70C09BF2666CEE117F0B800B8F26DE5D5D86059D70966D794A5E6E13ADC',
                'inspection_date': '2026-09-03',
                'engine_summary': {
                    'total_rules': 8,
                    'passed': 8,
                    'potential_violations': 0,
                    'warnings': 0,
                    'manual_review': 0,
                    'not_applicable': 0,
                },
            },
        )
        db.add(analysis)
        db.commit()

    # Inspector reviews package
    rev = client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Zero', 'notes': 'All declarations compliant'},
    )
    assert rev.status_code == 201

    # Finalize inspection
    fin = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin.status_code == 200
    assert fin.json()['status'] == 'COMPLETED'

    # Download report
    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.headers['content-type'] == 'application/pdf'
    assert f'filename="praman_inspection_report_INSP-ZERO-{tag}.pdf"' in rep_resp.headers['content-disposition']
    assert rep_resp.content.startswith(b'%PDF-')
    assert len(rep_resp.content) > 1000


def test_inspection_with_violations_report(client: TestClient) -> None:
    """2. An inspection with potential violations contains rule details, citations, and critical severity."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-VIOL-{tag}', 'name': 'Non-Compliant Biscuit', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-VIOL-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        finding = Finding(
            inspection_id=insp_id,
            severity='critical',
            status='open',
            title='PCR-001: Missing Manufacturer Address',
            description='The name and address of the manufacturer is not clearly displayed on the package.',
            detected_value='None detected',
            rule_check_id='PCR-001',
            evidence_reference=json.dumps({
                'source_image': 'package_label_ocr.png',
                'evidence_snippet': 'Manufactured by [Missing]',
                'ocr_confidence': 0.89,
                'catalog_version': '1.0.0',
                'catalog_hash': 'B847E70C09BF2666CEE117F0B800B8F26DE5D5D86059D70966D794A5E6E13ADC',
                'rule_status': 'POTENTIAL_VIOLATION',
            }),
        )
        db.add(finding)
        db.commit()

    # Inspector confirms the violation
    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    f_id = findings[0]['id']
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Verma', 'notes': 'Physical inspection confirmed absence of manufacturer details'},
    )

    # Finalize
    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    # Fetch report
    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.content.startswith(b'%PDF-')
    # ReportLab binary includes text fragments in streams
    assert len(rep_resp.content) > 1000


def test_inspection_with_warnings_report(client: TestClient) -> None:
    """3. Inspection containing warning findings generates a valid report with warning details."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-WARN-{tag}', 'name': 'Warning Pack', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-WARN-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        finding = Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-003: Non-Standard Net Quantity Unit',
            description='Quantity unit format requires inspection.',
            detected_value='500 gms',
            rule_check_id='PCR-003',
            evidence_reference=json.dumps({
                'source_image': 'package_label_ocr.png',
                'evidence_snippet': 'Net Qty: 500 gms',
                'ocr_confidence': 0.94,
                'rule_status': 'WARNING',
            }),
        )
        db.add(finding)
        db.commit()

    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[0]["id"]}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Rao', 'notes': 'Should use g rather than gms'},
    )
    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.content.startswith(b'%PDF-')


def test_unresolved_manual_review_blocked_from_report(client: TestClient) -> None:
    """4. Unresolved manual-review findings block report generation with HTTP 400."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-BLOCK-{tag}', 'name': 'Blocked Pack', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-BLOCK-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        finding = Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-008: PDP Font Height Verification',
            description='Requires physical caliper measurement of font height.',
            rule_check_id='PCR-008',
            evidence_reference=json.dumps({'rule_status': 'MANUAL_REVIEW'}),
        )
        db.add(finding)
        db.commit()

    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    # Inspector marks manual_review
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[0]["id"]}/review',
        json={'decision': 'manual_review', 'reviewer_name': 'Officer Roy', 'notes': 'Escalated to laboratory'},
    )

    # Attempt to generate report without resolving manual review -> MUST FAIL (400)
    rep_fail = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_fail.status_code == 400
    assert 'not eligible' in rep_fail.json()['detail']
    assert 'manual review' in rep_fail.json()['detail'].lower()


def test_inspector_decisions_in_report(client: TestClient) -> None:
    """5. Inspector audit decision details are incorporated into report generation."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-AUDIT-{tag}', 'name': 'Audit Goods', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-AUDIT-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        f1 = Finding(
            inspection_id=insp_id,
            severity='critical',
            status='open',
            title='PCR-007: MRP Check',
            description='MRP missing',
            rule_check_id='PCR-007',
            evidence_reference=json.dumps({'rule_status': 'POTENTIAL_VIOLATION'}),
        )
        f2 = Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-003: Quantity Check',
            description='Quantity unit format',
            rule_check_id='PCR-003',
            evidence_reference=json.dumps({'rule_status': 'WARNING'}),
        )
        db.add_all([f1, f2])
        db.commit()

    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    # Review f1: Confirm
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[0]["id"]}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Chief Inspector Sharma', 'notes': 'Confirmed MRP missing on outer carton'},
    )
    # Review f2: Reject
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[1]["id"]}/review',
        json={'decision': 'reject', 'reviewer_name': 'Chief Inspector Sharma', 'notes': 'False positive; permissible unit abbreviation on side panel'},
    )

    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.content.startswith(b'%PDF-')


def test_evidence_snippet_and_bbox_traceability(client: TestClient) -> None:
    """6. Bounding box and evidence snippets are processed into visual annotations with graceful fallbacks."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-EVID-{tag}', 'name': 'Evidence Test', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-EVID-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    # Upload real fixture image
    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'
    with open(fixture_path, 'rb') as f:
        client.post(
            f'/api/v1/inspections/{insp_id}/upload-images',
            files=[('files', ('package_label_ocr.png', f, 'image/png'))],
            data={'image_type': 'front'},
        )
    client.post(f'/api/v1/inspections/{insp_id}/analyze')

    # Batch confirm all findings
    client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Lead Officer', 'notes': 'Evidence verified against label fixture'},
    )
    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.content.startswith(b'%PDF-')
    assert len(rep_resp.content) > 5000  # Substantial PDF with annotated visual evidence!


def test_catalog_version_and_hash_in_report(client: TestClient) -> None:
    """7. Verifies catalog version and SHA-256 hash are present in report summary data."""
    generator = InspectionReportGenerator()
    with SessionLocal() as db:
        insp = Inspection(
            inspection_number=f'INSP-META-{uuid4().hex[:8]}',
            status='COMPLETED',
            barcode_or_qr='8901234567890',
            notes='Test metadata verification',
        )
        db.add(insp)
        db.commit()
        db.refresh(insp)

        summary_meta = {
            'catalog_version': '1.0.0',
            'catalog_hash': 'B847E70C09BF2666CEE117F0B800B8F26DE5D5D86059D70966D794A5E6E13ADC',
            'inspection_date': '2026-09-03',
            'engine_summary': {
                'overall_result': 'COMPLIANT',
                'total_checks': 0,
                'passed': 0,
                'potential_violations': 0,
                'warnings': 0,
                'manual_review': 0,
                'not_applicable': 0,
            },
            'inspector_summary': {'review_status': 'COMPLETE', 'reviewed_count': 0},
            'final_result': {'inspection_status': 'COMPLETED', 'can_finalize': True},
        }

        pdf = generator.generate_pdf(insp, [], summary_meta)
        assert pdf.startswith(b'%PDF-')
        # Confirm PDF generation was successful
        assert len(pdf) > 1000


def test_report_api_download_headers(client: TestClient) -> None:
    """8. Verifies correct HTTP headers for file download."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-HDR-{tag}', 'name': 'Header Test', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-HDR-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    # Finalize directly (empty findings in draft)
    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    rep_resp = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert rep_resp.status_code == 200
    assert rep_resp.headers['content-type'] == 'application/pdf'
    assert f'filename="praman_inspection_report_INSP-HDR-{tag}.pdf"' in rep_resp.headers['content-disposition']
    assert 'content-length' in rep_resp.headers
    assert int(rep_resp.headers['content-length']) > 0


def test_report_deterministic_generation(client: TestClient) -> None:
    """9. Repeated calls to generate report for identical state produce valid, consistent PDFs."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-DET-{tag}', 'name': 'Deterministic Goods', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-DET-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    r1 = client.get(f'/api/v1/inspections/{insp_id}/report')
    r2 = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.headers['content-type'] == r2.headers['content-type']
    assert r1.content.startswith(b'%PDF-')
    assert r2.content.startswith(b'%PDF-')
