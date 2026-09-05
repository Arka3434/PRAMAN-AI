from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase6_explainability_test.db')

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.services.compliance_engine import ComplianceEngine, InspectionEvaluationContext
from app.services.ocr_service import OCRService

FIXTURE_PATH = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def test_compliance_engine_projection_contains_complete_explainability() -> None:
    """Verifies that ComplianceEngine projections include all 10 explainability fields."""
    assert FIXTURE_PATH.exists()

    ocr_result = OCRService.analyze_image(FIXTURE_PATH, 'explainability-projection-test')
    declarations = ocr_result['structured_declarations']

    eval_context = InspectionEvaluationContext(
        inspection_id='explainability-test-001',
        inspection_context={'is_imported': False, 'commodity_category': 'food'},
        structured_declarations=declarations,
        ocr_evidence={
            'ocr_text': ocr_result['ocr_text'],
            'ocr_confidence': ocr_result['ocr_confidence'],
            'ocr_regions': ocr_result['ocr_regions'],
            'source_file': FIXTURE_PATH.name,
        },
    )

    engine_instance = ComplianceEngine()
    report = engine_instance.evaluate(eval_context)
    findings = report.to_findings_projection()

    assert len(findings) >= 5

    f_by_rule = {f['rule_check_id']: f for f in findings}

    # 1. WHAT: plain-language issue/result
    for f in findings:
        assert 'what' in f
        assert isinstance(f['what'], str)
        assert len(f['what']) > 0

    # 2. WHY: legal reason
    for f in findings:
        assert 'why' in f
        assert isinstance(f['why'], str)
        assert 'rule' in f['why'].lower() or 'statutory' in f['why'].lower()

    # 3. RULE: PCR rule ID and legal citation
    for f in findings:
        assert f['rule_check_id'].startswith('PCR-')
        assert 'legal_citation' in f
        assert 'Legal Metrology' in f['legal_citation']

    # 4. DETECTED VALUE
    assert f_by_rule['PCR-001']['detected_value'] is not None
    assert 'PRAMAN Foods' in f_by_rule['PCR-001']['detected_value']
    assert f_by_rule['PCR-004']['detected_value'] is not None
    assert '5' in f_by_rule['PCR-004']['detected_value']

    # 5. EXPECTED CONDITION
    for f in findings:
        assert 'expected_condition' in f
        assert len(f['expected_condition']) > 10

    # 6. EVIDENCE: source image + OCR text snippet
    for f in findings:
        assert f['source_image'] == 'package_label_ocr.png'
    assert f_by_rule['PCR-001']['evidence_snippet'] is not None
    assert 'PRAMAN' in f_by_rule['PCR-001']['evidence_snippet']

    # 7. LOCATION: OCR bounding box when available
    assert f_by_rule['PCR-001']['evidence_location'] is not None
    assert isinstance(f_by_rule['PCR-001']['evidence_location'], list)
    assert len(f_by_rule['PCR-001']['evidence_location']) >= 4

    # 8. OCR confidence when available
    assert f_by_rule['PCR-001']['ocr_confidence'] is not None
    assert 0.0 < f_by_rule['PCR-001']['ocr_confidence'] <= 1.0

    # 9. STATUS
    for f in findings:
        assert f['status'] in ('open', 'resolved')

    # 10. SEVERITY
    for f in findings:
        assert f['severity'] in ('pass', 'critical', 'major', 'warning', 'info')


def test_api_findings_endpoint_exposes_complete_explainability() -> None:
    """Verifies that the /inspections/{id}/findings API exposes all 10 explainability fields."""
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-EXPLAIN-001',
        'status': 'DRAFT',
        'title': 'Explainability Full API Test',
    })
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label_ocr.png', img_bytes, 'image/png')},
    )
    assert upload_resp.status_code == 201

    analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_resp.status_code == 201

    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    api_findings = findings_resp.json()

    assert len(api_findings) >= 5

    f_map = {f['rule_check_id']: f for f in api_findings}

    # Verify all 10 fields are present in API output
    for f in api_findings:
        # WHAT
        assert f.get('what') is not None
        assert len(f['what']) > 0
        # WHY
        assert f.get('why') is not None
        assert len(f['why']) > 0
        # RULE and legal citation
        assert f['rule_check_id'].startswith('PCR-')
        assert f.get('legal_citation') is not None
        # DETECTED VALUE
        assert 'detected_value' in f
        # EXPECTED CONDITION
        assert f.get('expected_condition') is not None
        # EVIDENCE: source image + text snippet
        assert f.get('source_image') == 'package_label_ocr.png'
        # STATUS
        assert f['status'] in ('open', 'resolved')
        # SEVERITY
        assert f['severity'] in ('pass', 'critical', 'major', 'warning', 'info')

    # Specific evidence location and confidence checks on detected declarations
    pcr_001 = f_map['PCR-001']
    assert pcr_001['evidence_snippet'] is not None
    assert pcr_001['evidence_location'] is not None
    assert pcr_001['ocr_confidence'] is not None

    pcr_004 = f_map['PCR-004']
    assert pcr_004['evidence_snippet'] is not None
    assert pcr_004['evidence_location'] is not None
    assert pcr_004['ocr_confidence'] is not None
