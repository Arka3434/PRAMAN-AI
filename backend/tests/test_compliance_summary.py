"""Phase 6F Tests: Compliance Summary & Inspection Result.

Tests:
1. Zero findings / all checks pass scenario (can finalize without requiring > 0 findings).
2. Potential violation scenario derived from structured fields (not title matching).
3. Warning / manual review scenario derived from structured fields (not title matching).
4. Existing finalization guardrails (unreviewed findings or unresolved manual reviews block finalization).
5. Real OCR label fixture aggregation and severity distribution.
6. Read-only idempotency (summary does not modify findings or rule catalog).
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_empty_inspection_summary(client: TestClient) -> None:
    """1. An inspection before analysis has PENDING_ANALYSIS engine result, zero checks, and cannot finalize without analysis/review."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Summary Test Product', 'category': 'general'})
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-{tag}', 'product_id': prod_id})
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    summary_resp = client.get(f'/api/v1/inspections/{insp_id}/summary')
    assert summary_resp.status_code == 200
    data = summary_resp.json()

    assert data['inspection_id'] == insp_id
    assert data['engine_summary']['overall_result'] == 'PENDING_ANALYSIS'
    assert data['engine_summary']['total_checks'] == 0
    assert data['inspector_summary']['review_status'] == 'NOT_STARTED'
    assert data['final_result']['can_finalize'] is False
    assert any('must be analyzed or reviewed' in reason for reason in data['final_result']['blocking_reasons'])


def test_zero_findings_all_checks_pass_scenario(client: TestClient) -> None:
    """2. Validates zero violation/warning findings scenario:
    - All evaluated checks pass or are not applicable.
    - Package has zero violation/warning findings.
    - overall_result is COMPLIANT.
    - Can finalize once inspector review is performed, without requiring total_findings > 0.
    """
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Fully Compliant Goods', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-COMPLIANT-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    # Simulate analysis where all checks passed and no violation findings were generated
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
                    'passed': 6,
                    'potential_violations': 0,
                    'warnings': 0,
                    'manual_review': 0,
                    'not_applicable': 2,
                },
            },
        )
        db.add(analysis)
        db.commit()

    # Pre-review summary: COMPLIANT engine result, 0 violation findings
    s1 = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    assert s1['engine_summary']['overall_result'] == 'COMPLIANT'
    assert s1['engine_summary']['total_checks'] == 0
    assert s1['engine_summary']['potential_violations'] == 0
    assert s1['engine_summary']['warnings'] == 0
    assert s1['engine_summary']['manual_review'] == 0
    assert s1['engine_summary']['not_applicable'] == 2

    # Guardrail: REVIEW_REQUIRED with 0 findings still requires inspector review decision
    assert s1['final_result']['can_finalize'] is False
    assert any('Inspector review must be completed' in r for r in s1['final_result']['blocking_reasons'])

    # Inspector reviews and approves the inspection
    rev_resp = client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Mehta', 'notes': 'All statutory checks passed.'},
    )
    assert rev_resp.status_code == 201

    # Post-review summary: can_finalize is now True despite total_findings == 0!
    s2 = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    assert s2['inspector_summary']['review_status'] == 'COMPLETE'
    assert s2['final_result']['can_finalize'] is True
    assert len(s2['final_result']['blocking_reasons']) == 0

    # Finalization succeeds with 0 findings!
    fin_resp = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin_resp.status_code == 200
    assert fin_resp.json()['status'] == 'COMPLETED'


def test_potential_violation_scenario_structured(client: TestClient) -> None:
    """3. Validates potential violation scenario derived from structured fields, NOT by title text matching."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Violation Test', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-VIOL-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    # Create finding with severity='critical' and NO word 'violation' in the title
    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        db.add(Finding(
            inspection_id=insp_id,
            severity='critical',
            status='open',
            title='PCR-001: Statutory Item Check',  # No "violation" in title!
            description='Missing mandatory declaration',
            rule_check_id='PCR-001',
            evidence_reference=json.dumps({'rule_status': 'POTENTIAL_VIOLATION'}),
        ))
        db.commit()

    summary = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    eng = summary['engine_summary']
    # Must be POTENTIAL_VIOLATIONS_DETECTED from structured severity / rule_status
    assert eng['overall_result'] == 'POTENTIAL_VIOLATIONS_DETECTED'
    assert eng['potential_violations'] == 1
    assert eng['severity_distribution']['critical'] == 1

    # Guardrail: unreviewed violation finding blocks finalization
    assert summary['final_result']['can_finalize'] is False
    assert any('have not been reviewed' in r for r in summary['final_result']['blocking_reasons'])

    # Attempting to finalize via API must be rejected with HTTP 400
    fin_fail = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin_fail.status_code == 400
    assert 'have not been reviewed' in fin_fail.json()['detail']


def test_warning_and_manual_review_scenario_structured(client: TestClient) -> None:
    """4. Validates warning and manual review scenario derived from structured fields without title string matching."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Warn Test', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-WARN-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    with SessionLocal() as db:
        insp = db.get(Inspection, insp_id)
        insp.status = 'REVIEW_REQUIRED'
        # Finding 1: Manual Review rule (PCR-008) without "manual" or "verification" in title
        db.add(Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-008: PDP Font Standard',  # No "manual" or "verification" in title!
            description='PDP metrics need verification',
            rule_check_id='PCR-008',
            evidence_reference=json.dumps({'rule_status': 'MANUAL_REVIEW'}),
        ))
        # Finding 2: Warning rule without "warning" in title
        db.add(Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-003: Net Quantity Specification',  # No "warning" in title!
            description='Non-standard quantity formatting',
            rule_check_id='PCR-003',
            evidence_reference=json.dumps({'rule_status': 'WARNING'}),
        ))
        db.commit()

    summary = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    eng = summary['engine_summary']
    assert eng['overall_result'] == 'WARNINGS_OR_MANUAL_REVIEW'
    assert eng['manual_review'] == 1
    assert eng['warnings'] == 1
    assert eng['severity_distribution']['warning'] == 2

    # Review finding 1 with decision='manual_review'
    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    f1 = findings[0]
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f1["id"]}/review',
        json={'decision': 'manual_review', 'reviewer_name': 'Inspector Verma', 'notes': 'Escalating for physical PDP test'},
    )
    # Review finding 2 with decision='confirm'
    f2 = findings[1]
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f2["id"]}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Verma', 'notes': 'Confirmed quantity unit issue'},
    )

    s_mid = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    assert s_mid['inspector_summary']['manual_review_count'] == 1
    # Unresolved manual review must block finalization
    assert s_mid['final_result']['can_finalize'] is False
    assert any('require manual review resolution' in r for r in s_mid['final_result']['blocking_reasons'])

    fin_blocked = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin_blocked.status_code == 400
    assert 'require manual review resolution' in fin_blocked.json()['detail']

    # Now resolve the manual review item to 'confirm'
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f1["id"]}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Senior Inspector', 'notes': 'Physical measurement complete'},
    )

    s_res = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    assert s_res['inspector_summary']['manual_review_count'] == 0
    assert s_res['inspector_summary']['review_status'] == 'COMPLETE'
    assert s_res['final_result']['can_finalize'] is True

    fin_ok = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin_ok.status_code == 200
    assert fin_ok.json()['status'] == 'COMPLETED'


def test_compliance_summary_aggregation_and_severities(client: TestClient) -> None:
    """5. Validates correct aggregation of finding statuses and severity counts from real label fixture."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Packaged Tea', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'
    with open(fixture_path, 'rb') as f:
        upload_resp = client.post(
            f'/api/v1/inspections/{insp_id}/upload-images',
            files=[('files', ('package_label_ocr.png', f, 'image/png'))],
            data={'image_type': 'front'},
        )
    assert upload_resp.status_code == 201

    analysis_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analysis_resp.status_code == 201

    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    assert len(findings) == 8

    summary = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    eng = summary['engine_summary']
    assert eng['total_checks'] == 8
    assert eng['passed'] + eng['potential_violations'] + eng['warnings'] + eng['manual_review'] == 8

    sev = eng['severity_distribution']
    assert sev['critical'] + sev['major'] + sev['warning'] + sev['pass_count'] == 8

    assert eng['overall_result'] in {
        'POTENTIAL_VIOLATIONS_DETECTED',
        'WARNINGS_OR_MANUAL_REVIEW',
        'COMPLIANT',
    }

    insp = summary['inspector_summary']
    assert insp['total_findings'] == 8
    assert insp['reviewed_count'] == 0
    assert insp['pending_count'] == 8
    assert insp['review_status'] == 'PENDING'
    assert summary['final_result']['can_finalize'] is False


def test_inspector_decisions_progress_and_final_result(client: TestClient) -> None:
    """6. Validates inspector decision tracking, batch review, and finalization."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Biscuits', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'
    with open(fixture_path, 'rb') as f:
        client.post(
            f'/api/v1/inspections/{insp_id}/upload-images',
            files=[('files', ('package_label_ocr.png', f, 'image/png'))],
            data={'image_type': 'front'},
        )
    client.post(f'/api/v1/inspections/{insp_id}/analyze')

    findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    f1_id = findings[0]['id']
    f2_id = findings[1]['id']

    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f1_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Alice', 'notes': 'Verified'},
    )
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f2_id}/review',
        json={'decision': 'reject', 'reviewer_name': 'Inspector Alice', 'notes': 'Rejected'},
    )

    s1 = client.get(f'/api/v1/inspections/{insp_id}/summary').json()['inspector_summary']
    assert s1['reviewed_count'] == 2
    assert s1['pending_count'] == 6
    assert s1['review_status'] == 'IN_PROGRESS'

    # Batch confirm all remaining findings
    client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Chief Inspector', 'notes': 'Batch approval'},
    )

    s2 = client.get(f'/api/v1/inspections/{insp_id}/summary').json()
    assert s2['inspector_summary']['reviewed_count'] == 8
    assert s2['inspector_summary']['pending_count'] == 0
    assert s2['inspector_summary']['review_status'] == 'COMPLETE'
    assert s2['final_result']['can_finalize'] is True

    fin_resp = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert fin_resp.status_code == 200
    assert fin_resp.json()['status'] == 'COMPLETED'


def test_summary_does_not_modify_findings_or_rules(client: TestClient) -> None:
    """7. Summary endpoint is read-only and leaves findings and catalog unchanged."""
    tag = uuid4().hex[:8]
    prod_resp = client.post('/api/v1/products', json={'sku': f'SKU-{tag}', 'name': 'Read Only Test', 'category': 'general'})
    prod_id = prod_resp.json()['id']

    insp_resp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-{tag}', 'product_id': prod_id})
    insp_id = insp_resp.json()['id']

    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'
    with open(fixture_path, 'rb') as f:
        client.post(
            f'/api/v1/inspections/{insp_id}/upload-images',
            files=[('files', ('package_label_ocr.png', f, 'image/png'))],
            data={'image_type': 'front'},
        )
    client.post(f'/api/v1/inspections/{insp_id}/analyze')

    findings_before = client.get(f'/api/v1/inspections/{insp_id}/findings').json()

    for _ in range(3):
        res = client.get(f'/api/v1/inspections/{insp_id}/summary')
        assert res.status_code == 200

    findings_after = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    assert findings_before == findings_after
