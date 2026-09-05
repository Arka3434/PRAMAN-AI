from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase6_inspector_review_test.db')

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app

client = TestClient(app)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "package_label_ocr.png"


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_individual_finding_review_actions_and_distinction() -> None:
    # 1. Create inspection and run analysis
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': 'INSP-REV-001',
            'status': 'DRAFT',
            'title': 'Inspector Review Granular Test',
        },
    )
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label.png', img_bytes, 'image/png')},
    )
    assert upload_resp.status_code == 201

    analysis_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analysis_resp.status_code == 201

    # 2. Get initial findings - all inspector decisions must be None
    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    findings = findings_resp.json()
    assert len(findings) >= 3

    for f in findings:
        assert f['inspector_decision'] is None
        assert f['reviewer_name'] is None

    finding_1 = findings[0]
    finding_2 = findings[1]
    finding_3 = findings[2]

    # Save initial automated engine status to verify it remains unchanged
    engine_status_1 = finding_1['status']
    engine_status_2 = finding_2['status']
    engine_status_3 = finding_3['status']

    # 3. Submit individual reviews
    # Review finding 1: CONFIRM
    rev1_resp = client.post(
        f'/api/v1/inspections/{insp_id}/findings/{finding_1["id"]}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'confirm',
            'reviewer_name': 'senior-inspector-sharma',
            'notes': 'Confirmed declaration presence and OCR accuracy.',
        },
    )
    assert rev1_resp.status_code == 201
    assert rev1_resp.json()['decision'] == 'confirm'
    assert rev1_resp.json()['finding_id'] == finding_1['id']

    # Review finding 2: REJECT
    rev2_resp = client.post(
        f'/api/v1/inspections/{insp_id}/findings/{finding_2["id"]}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'reject',
            'reviewer_name': 'senior-inspector-sharma',
            'notes': 'False positive; statutory text located on adjacent panel.',
        },
    )
    assert rev2_resp.status_code == 201
    assert rev2_resp.json()['decision'] == 'reject'
    assert rev2_resp.json()['finding_id'] == finding_2['id']

    # Review finding 3: MANUAL_REVIEW
    rev3_resp = client.post(
        f'/api/v1/inspections/{insp_id}/findings/{finding_3["id"]}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'manual_review',
            'reviewer_name': 'senior-inspector-sharma',
            'notes': 'Escalated to laboratory for physical weight verification.',
        },
    )
    assert rev3_resp.status_code == 201
    assert rev3_resp.json()['decision'] == 'manual_review'
    assert rev3_resp.json()['finding_id'] == finding_3['id']

    # 4. Verify findings retrieval reflects decisions without altering engine evaluations
    updated_findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    updated_map = {f['id']: f for f in updated_findings_resp.json()}

    # Finding 1
    assert updated_map[finding_1['id']]['inspector_decision'] == 'confirm'
    assert updated_map[finding_1['id']]['reviewer_name'] == 'senior-inspector-sharma'
    assert updated_map[finding_1['id']]['inspector_notes'] == 'Confirmed declaration presence and OCR accuracy.'
    assert updated_map[finding_1['id']]['status'] == engine_status_1  # Engine evaluation preserved!

    # Finding 2
    assert updated_map[finding_2['id']]['inspector_decision'] == 'reject'
    assert updated_map[finding_2['id']]['reviewer_name'] == 'senior-inspector-sharma'
    assert updated_map[finding_2['id']]['inspector_notes'] == 'False positive; statutory text located on adjacent panel.'
    assert updated_map[finding_2['id']]['status'] == engine_status_2  # Engine evaluation preserved!

    # Finding 3
    assert updated_map[finding_3['id']]['inspector_decision'] == 'manual_review'
    assert updated_map[finding_3['id']]['reviewer_name'] == 'senior-inspector-sharma'
    assert updated_map[finding_3['id']]['status'] == engine_status_3  # Engine evaluation preserved!

    # 5. Verify review audit trail endpoint
    reviews_resp = client.get(f'/api/v1/inspections/{insp_id}/reviews')
    assert reviews_resp.status_code == 200
    reviews = reviews_resp.json()
    assert len(reviews) == 3
    assert {r['finding_id'] for r in reviews} == {finding_1['id'], finding_2['id'], finding_3['id']}


def test_finalization_guardrails_prevent_incomplete_review() -> None:
    # 1. Setup inspection with findings
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': 'INSP-REV-002',
            'status': 'DRAFT',
            'title': 'Finalization Integrity Test',
        },
    )
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label.png', img_bytes, 'image/png')},
    )
    client.post(f'/api/v1/inspections/{insp_id}/analyze')

    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    findings = findings_resp.json()
    assert len(findings) >= 2

    # 2. Attempt finalization with ZERO reviews -> MUST FAIL (400)
    finalize_unreviewed = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_unreviewed.status_code == 400
    assert 'have not been reviewed by an inspector' in finalize_unreviewed.json()['detail']

    # 3. Review all except the last finding
    for finding in findings[:-1]:
        client.post(
            f'/api/v1/inspections/{insp_id}/findings/{finding["id"]}/review',
            json={
                'inspection_id': insp_id,
                'decision': 'confirm',
                'reviewer_name': 'inspector-verma',
                'notes': 'Verified declaration.',
            },
        )

    # Attempt finalization with 1 unreviewed finding -> MUST FAIL (400)
    finalize_partial = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_partial.status_code == 400
    assert '1 finding(s) have not been reviewed' in finalize_partial.json()['detail']

    # 4. Review the last finding with 'manual_review'
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[-1]["id"]}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'manual_review',
            'reviewer_name': 'inspector-verma',
            'notes': 'Requires further verification.',
        },
    )

    # Attempt finalization with manual_review pending -> MUST FAIL (400)
    finalize_manual = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_manual.status_code == 400
    assert 'require manual review resolution' in finalize_manual.json()['detail']

    # 5. Resolve the manual review finding to 'confirm'
    client.post(
        f'/api/v1/inspections/{insp_id}/findings/{findings[-1]["id"]}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'confirm',
            'reviewer_name': 'inspector-verma',
            'notes': 'Manual verification complete. All clear.',
        },
    )

    # 6. Now finalization MUST SUCCEED (200)
    finalize_success = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_success.status_code == 200
    assert finalize_success.json()['status'] == 'COMPLETED'


def test_inspection_level_review_fallback_and_finalization() -> None:
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': 'INSP-REV-003',
            'status': 'DRAFT',
            'title': 'Overall Review Fallback Test',
        },
    )
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label.png', img_bytes, 'image/png')},
    )
    client.post(f'/api/v1/inspections/{insp_id}/analyze')

    # Submit overall inspection review
    rev_resp = client.post(
        f'/api/v1/inspections/{insp_id}/review',
        json={
            'inspection_id': insp_id,
            'decision': 'confirm',
            'reviewer_name': 'lead-inspector',
            'notes': 'Batch confirmed all statutory findings.',
        },
    )
    assert rev_resp.status_code == 201

    # Findings should inherit the overall confirm decision
    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    findings = findings_resp.json()
    assert len(findings) >= 1
    for f in findings:
        assert f['inspector_decision'] == 'confirm'
        assert f['reviewer_name'] == 'lead-inspector'

    # Finalize succeeds
    finalize_resp = client.post(f'/api/v1/inspections/{insp_id}/finalize')
    assert finalize_resp.status_code == 200
    assert finalize_resp.json()['status'] == 'COMPLETED'
