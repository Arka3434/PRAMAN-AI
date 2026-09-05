import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.analytics import _calculate_inspection_score
from app.db.session import SessionLocal
from app.main import app
from app.models.finding import Finding
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.review_decision import ReviewDecision


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


def test_calculate_inspection_score_pure_semantics():
    """Validates the core semantic rules for compliance score calculation:
    - Numerator = rule_status == 'PASS' only.
    - Denominator = PASS + POTENTIAL_VIOLATION + WARNING + MANUAL_REVIEW.
    - NOT_APPLICABLE is excluded from denominator.
    - Rejected inspector decisions do NOT convert violation to pass.
    """
    # 1. Mixed evaluations: 2 PASS, 1 VIOLATION, 1 WARNING, 1 MANUAL_REVIEW, 1 NOT_APPLICABLE
    f1 = Finding(rule_check_id='PCR-001', evidence_reference=json.dumps({'rule_status': 'PASS'}), severity='pass', status='resolved', title='P1', description='d')
    f2 = Finding(rule_check_id='PCR-003', evidence_reference=json.dumps({'rule_status': 'PASS'}), severity='pass', status='resolved', title='P2', description='d')
    f3 = Finding(rule_check_id='PCR-004', evidence_reference=json.dumps({'rule_status': 'POTENTIAL_VIOLATION'}), severity='critical', status='open', title='V1', description='d')
    f4 = Finding(rule_check_id='PCR-005', evidence_reference=json.dumps({'rule_status': 'WARNING'}), severity='warning', status='open', title='W1', description='d')
    f5 = Finding(rule_check_id='PCR-006', evidence_reference=json.dumps({'rule_status': 'MANUAL_REVIEW'}), severity='warning', status='open', title='M1', description='d')
    f6 = Finding(rule_check_id='PCR-002', evidence_reference=json.dumps({'rule_status': 'NOT_APPLICABLE'}), severity='pass', status='resolved', title='NA', description='d')

    # Denominator = 5 (f1, f2, f3, f4, f5), Numerator = 2 (f1, f2) -> 40.0%
    score = _calculate_inspection_score([f1, f2, f3, f4, f5, f6])
    assert score == 40.0

    # 2. Empty findings -> returns None
    assert _calculate_inspection_score([]) is None

    # 3. Only NOT_APPLICABLE -> returns None
    assert _calculate_inspection_score([f6]) is None

    # 4. All passing -> returns 100.0%
    assert _calculate_inspection_score([f1, f2]) == 100.0


def test_analytics_overview_contract_and_structure(client: TestClient):
    """Overview endpoint returns HTTP 200 with all required fields matching the contract."""
    res = client.get('/api/v1/analytics/overview')
    assert res.status_code == 200
    data = res.json()
    assert 'total_inspections' in data
    assert 'inspections_this_month' in data
    assert 'statutory_violations_count' in data
    assert 'review_queue_count' in data
    assert 'average_compliance_score' in data
    assert 'compliance_trend' in data
    assert 'violation_breakdown' in data
    assert 'recent_inspections' in data
    assert 'attention_items' in data
    assert isinstance(data['compliance_trend'], list)
    assert len(data['compliance_trend']) >= 6


def test_analytics_trends_contract_and_yield_rate(client: TestClient):
    """Trends endpoint returns HTTP 200 with adjudication yield rate and breakdown."""
    res = client.get('/api/v1/analytics/trends')
    assert res.status_code == 200
    data = res.json()
    assert 'total_inspections' in data
    assert 'total_completed' in data
    assert 'total_in_review' in data
    assert 'total_findings' in data
    assert 'reviewed_findings' in data
    assert 'adjudication_yield_rate' in data
    assert 'compliance_trend' in data
    assert 'rule_performance' in data


def test_rejected_inspector_decision_preserves_violation_semantics(client: TestClient, db: Session):
    """End-to-end API test:
    - Creates an inspection with a POTENTIAL_VIOLATION finding.
    - Records an inspector decision 'reject'.
    - Confirms that the finding's rule_status remains POTENTIAL_VIOLATION.
    - Confirms that /api/v1/analytics/violations reflects the rejection without changing rule_status.
    """
    tag = uuid4().hex[:8]
    p = Product(name=f'Analytics Test Product {tag}', category='food')
    db.add(p)
    db.flush()

    insp = Inspection(
        inspection_number=f'INSP-ANL-{tag}',
        status='REVIEW_REQUIRED',
        product_id=p.id,
    )
    db.add(insp)
    db.flush()

    finding = Finding(
        inspection_id=insp.id,
        severity='critical',
        status='open',
        title=f'PCR-004: Net quantity unit invalid {tag}',
        description='Testing rejection semantics',
        rule_check_id='PCR-004',
        evidence_reference=json.dumps({'rule_status': 'POTENTIAL_VIOLATION'}),
    )
    db.add(finding)
    db.commit()

    # Before review
    db.refresh(finding)
    assert finding.rule_status == 'POTENTIAL_VIOLATION'
    assert finding.inspector_decision is None

    # Record inspector rejection
    rd = ReviewDecision(
        inspection_id=insp.id,
        decision='reject',
        reviewer_name='Inspector Sharma',
        notes=json.dumps({'finding_id': finding.id, 'notes': 'Overruled in field: approved abbreviation'}),
    )
    db.add(rd)
    db.commit()

    # After review: rule_status is STILL POTENTIAL_VIOLATION, inspector_decision is 'reject'
    db.refresh(finding)
    assert finding.rule_status == 'POTENTIAL_VIOLATION'
    assert finding.inspector_decision == 'reject'

    # Verify score calculation function does NOT turn it into a pass
    assert _calculate_inspection_score([finding]) == 0.0

    # Query violations register specifically for this inspection
    res = client.get(f'/api/v1/analytics/violations?search={tag}')
    assert res.status_code == 200
    v_data = res.json()
    assert v_data['total'] >= 1
    matched = [item for item in v_data['items'] if tag in item['title']]
    assert len(matched) == 1
    assert matched[0]['rule_status'] == 'POTENTIAL_VIOLATION'
    assert matched[0]['inspector_decision'] == 'reject'


def test_violations_register_filtering_and_pagination(client: TestClient):
    """Validates filtering by severity, rule_status, search, and pagination."""
    res_all = client.get('/api/v1/analytics/violations')
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert 'summary' in all_data
    assert 'items' in all_data

    # Filter by severity
    res_crit = client.get('/api/v1/analytics/violations?severity=critical')
    assert res_crit.status_code == 200
    crit_data = res_crit.json()
    assert all(item['severity'] == 'critical' for item in crit_data['items'])

    # Pagination limits
    res_page = client.get('/api/v1/analytics/violations?limit=2&offset=0')
    assert res_page.status_code == 200
    page_data = res_page.json()
    assert len(page_data['items']) <= 2
    assert page_data['limit'] == 2
    assert page_data['offset'] == 0
