"""Phase 6H Tests: Inspection History & Report Management.

Tests:
1. Inspection history retrieval returns all required fields (product_name, finding_count, overall_result, review_status, report_available).
2. Status filtering filters correctly for completed, draft, and review_required inspections.
3. Search parameter filters across inspection_number, title, and product_name.
4. Final result derived from existing structured data without hardcoded string matching.
5. Report availability flag is strictly True only for completed/eligible inspections and False for draft/unreviewed/manual review inspections.
6. Existing inspection workflow, creation, and detail retrieval remain intact.
"""

from __future__ import annotations

import json
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.db.session import SessionLocal
from app.models.analysis_result import AnalysisResult
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.product import Product


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_inspection_history_retrieval(client: TestClient) -> None:
    """1. Retrieval of inspection history returns enriched structured fields."""
    tag = uuid4().hex[:8]
    p_resp = client.post('/api/v1/products', json={'name': f'History Product {tag}', 'category': 'packaged_food'})
    assert p_resp.status_code == 201
    prod_id = p_resp.json()['id']

    i_resp = client.post('/api/v1/inspections', json={
        'inspection_number': f'INSP-HIST-{tag}',
        'title': f'History Test Inspection {tag}',
        'product_id': prod_id,
        'status': 'draft',
    })
    assert i_resp.status_code == 201
    insp_id = i_resp.json()['id']

    # Retrieve history
    history_resp = client.get('/api/v1/inspections')
    assert history_resp.status_code == 200
    items = history_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    target = next((item for item in items if item['id'] == insp_id), None)
    assert target is not None
    assert target['inspection_number'] == f'INSP-HIST-{tag}'
    assert target['product_name'] == f'History Product {tag}'
    assert target['finding_count'] == 0
    assert target['overall_result'] == 'PENDING_ANALYSIS'
    assert target['review_status'] == 'NOT_REQUIRED'
    assert target['report_available'] is False


def test_inspection_history_status_filtering(client: TestClient) -> None:
    """2. History endpoint filters accurately by status."""
    tag = uuid4().hex[:8]
    p_resp = client.post('/api/v1/products', json={'name': f'Filter Goods {tag}', 'category': 'general'})
    prod_id = p_resp.json()['id']

    i1 = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-FILT-DRAFT-{tag}', 'product_id': prod_id}).json()
    i2 = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-FILT-COMP-{tag}', 'product_id': prod_id}).json()

    with SessionLocal() as db:
        insp2 = db.get(Inspection, i2['id'])
        insp2.status = 'COMPLETED'
        db.commit()

    # Filter for completed
    comp_resp = client.get('/api/v1/inspections?status=completed')
    assert comp_resp.status_code == 200
    comp_items = comp_resp.json()
    assert all(item['status'].upper() == 'COMPLETED' for item in comp_items)
    assert any(item['id'] == i2['id'] for item in comp_items)
    assert not any(item['id'] == i1['id'] for item in comp_items)

    # Filter for draft
    draft_resp = client.get('/api/v1/inspections?status=draft')
    assert draft_resp.status_code == 200
    draft_items = draft_resp.json()
    assert all(item['status'].lower() == 'draft' for item in draft_items)
    assert any(item['id'] == i1['id'] for item in draft_items)
    assert not any(item['id'] == i2['id'] for item in draft_items)


def test_inspection_history_search(client: TestClient) -> None:
    """3. History endpoint searches across inspection number, title, and product name."""
    tag = uuid4().hex[:8]
    p1 = client.post('/api/v1/products', json={'name': f'UniqueSpiceMix {tag}', 'category': 'food'}).json()
    p2 = client.post('/api/v1/products', json={'name': f'RegularItem {tag}', 'category': 'general'}).json()

    i1 = client.post('/api/v1/inspections', json={
        'inspection_number': f'INSP-SRCH-A-{tag}',
        'title': 'Targeted Quality Audit',
        'product_id': p1['id'],
    }).json()

    i2 = client.post('/api/v1/inspections', json={
        'inspection_number': f'INSP-SRCH-B-{tag}',
        'title': 'Standard Intake',
        'product_id': p2['id'],
    }).json()

    # Search by unique product name
    search_prod = client.get(f'/api/v1/inspections?search=UniqueSpiceMix%20{tag}')
    assert search_prod.status_code == 200
    res_prod = search_prod.json()
    assert any(item['id'] == i1['id'] for item in res_prod)
    assert not any(item['id'] == i2['id'] for item in res_prod)

    # Search by inspection number
    search_num = client.get(f'/api/v1/inspections?search=INSP-SRCH-B-{tag}')
    assert search_num.status_code == 200
    res_num = search_num.json()
    assert any(item['id'] == i2['id'] for item in res_num)
    assert not any(item['id'] == i1['id'] for item in res_num)

    # Search by title keyword
    search_title = client.get(f'/api/v1/inspections?search=Targeted%20Quality')
    assert search_title.status_code == 200
    res_title = search_title.json()
    assert any(item['id'] == i1['id'] for item in res_title)


def test_inspection_history_structured_results(client: TestClient) -> None:
    """4. Results reflect structured compliance engine evaluations and inspector reviews."""
    tag = uuid4().hex[:8]
    prod = client.post('/api/v1/products', json={'name': f'Defect Goods {tag}', 'category': 'general'}).json()
    insp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-STRUCT-{tag}', 'product_id': prod['id']}).json()
    insp_id = insp['id']

    with SessionLocal() as db:
        insp_obj = db.get(Inspection, insp_id)
        insp_obj.status = 'REVIEW_REQUIRED'
        analysis = AnalysisResult(
            inspection_id=insp_id,
            status='COMPLETED',
            extraction_metadata={'engine_summary': {'passed': 7, 'potential_violations': 1}},
        )
        finding = Finding(
            inspection_id=insp_id,
            severity='critical',
            status='open',
            title='Random Title Without Hardcoded Keywords',
            description='Manufacturer details absent on package',
            rule_check_id='PCR-001',
            evidence_reference=json.dumps({'rule_status': 'POTENTIAL_VIOLATION'}),
        )
        db.add_all([analysis, finding])
        db.commit()
        f_id = finding.id

    hist_resp = client.get(f'/api/v1/inspections?search=INSP-STRUCT-{tag}')
    assert hist_resp.status_code == 200
    items = hist_resp.json()
    assert len(items) == 1
    record = items[0]
    assert record['finding_count'] == 1
    assert record['overall_result'] == 'POTENTIAL_VIOLATIONS_DETECTED'
    assert record['review_status'] == 'PENDING'
    assert record['report_available'] is False

    # Review and finalize
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{f_id}/review',
        json={'decision': 'confirm', 'reviewer_name': 'Inspector Roy', 'notes': 'Confirmed violation'},
    )
    client.post(f'/api/v1/inspections/{insp_id}/finalize')

    hist_after = client.get(f'/api/v1/inspections?search=INSP-STRUCT-{tag}').json()[0]
    assert hist_after['status'] == 'COMPLETED'
    assert hist_after['review_status'] == 'COMPLETE'
    assert hist_after['report_available'] is True


def test_inspection_history_report_availability_guardrails(client: TestClient) -> None:
    """5. Report availability is strictly guarded and matches finalization rules."""
    tag = uuid4().hex[:8]
    prod = client.post('/api/v1/products', json={'name': f'Guard Goods {tag}'}).json()
    insp = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-GUARD-{tag}', 'product_id': prod['id']}).json()
    insp_id = insp['id']

    # 1. Draft with no review -> report_available is False
    r1 = client.get(f'/api/v1/inspections?search=INSP-GUARD-{tag}').json()[0]
    assert r1['report_available'] is False

    # 2. Add manual-review item -> report_available MUST remain False
    with SessionLocal() as db:
        insp_obj = db.get(Inspection, insp_id)
        insp_obj.status = 'REVIEW_REQUIRED'
        analysis = AnalysisResult(inspection_id=insp_id, status='COMPLETED')
        f_manual = Finding(
            inspection_id=insp_id,
            severity='warning',
            status='open',
            title='PCR-008: Font Height Check',
            description='Physical verification of PDP font height required',
            rule_check_id='PCR-008',
            evidence_reference=json.dumps({'rule_status': 'MANUAL_REVIEW'}),
        )
        db.add_all([analysis, f_manual])
        db.commit()

    r2 = client.get(f'/api/v1/inspections?search=INSP-GUARD-{tag}').json()[0]
    assert r2['report_available'] is False
    assert r2['overall_result'] == 'WARNINGS_OR_MANUAL_REVIEW'

    # Attempting to fetch report returns 400
    pdf_fail = client.get(f'/api/v1/inspections/{insp_id}/report')
    assert pdf_fail.status_code == 400


def test_existing_inspection_workflow_unaffected(client: TestClient) -> None:
    """6. Single inspection endpoint and existing detail views continue to function without alteration."""
    tag = uuid4().hex[:8]
    p = client.post('/api/v1/products', json={'name': f'Workflow Prod {tag}'}).json()
    i = client.post('/api/v1/inspections', json={'inspection_number': f'INSP-WORK-{tag}', 'product_id': p['id']}).json()

    # Detail view
    detail = client.get(f'/api/v1/inspections/{i["id"]}')
    assert detail.status_code == 200
    data = detail.json()
    assert data['id'] == i['id']
    assert data['inspection_number'] == f'INSP-WORK-{tag}'
    assert data['product_id'] == p['id']
