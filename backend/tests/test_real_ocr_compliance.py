from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase6_real_ocr_test.db')

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


def test_real_data_pipeline_paddleocr_to_compliance_engine() -> None:
    """Validates complete pipeline: package image -> PaddleOCR -> structured declarations -> ComplianceEngine -> statutory findings."""
    assert FIXTURE_PATH.exists(), f'Realistic OCR fixture image missing at {FIXTURE_PATH}'

    # 1. PaddleOCR extracts expected declarations from the realistic fixture
    ocr_result = OCRService.analyze_image(FIXTURE_PATH, 'real-ocr-pipeline-check')

    assert ocr_result['status'] == 'completed'
    assert ocr_result['extraction_metadata']['model'] == 'PaddleOCR'
    assert ocr_result['extraction_metadata']['real_ocr_used'] is True
    assert ocr_result['ocr_text'].strip() != ''
    assert ocr_result['ocr_confidence'] > 0.0

    declarations = ocr_result['structured_declarations']
    assert declarations is not None
    assert 'commodity_name' in declarations
    assert 'Rice' in declarations['commodity_name'] or 'PRAMAN' in declarations['commodity_name']
    assert 'manufacturer_name' in declarations
    assert 'PRAMAN Foods' in declarations['manufacturer_name']
    assert declarations['net_quantity'] == '5'
    assert declarations['quantity_unit'] == 'kg'
    assert '299' in (declarations['retail_sale_price'] or '')
    assert '2026' in (declarations['month_year'] or '')

    # 2. Declarations are actually passed to ComplianceEngine via InspectionEvaluationContext
    eval_context = InspectionEvaluationContext(
        inspection_id='real-ocr-pipeline-check',
        inspection_context={
            'is_imported': False,
            'commodity_category': 'food',
            'consumer_type': 'retail',
        },
        structured_declarations=declarations,
        ocr_evidence={
            'ocr_text': ocr_result.get('ocr_text', ''),
            'ocr_confidence': ocr_result.get('ocr_confidence', 0.0),
            'ocr_regions': ocr_result.get('ocr_regions', []),
            'source_file': FIXTURE_PATH.name,
        },
    )

    assert eval_context.structured_declarations == declarations
    assert eval_context.ocr_evidence['source_file'] == 'package_label_ocr.png'

    engine = ComplianceEngine()
    report = engine.evaluate(eval_context)

    # 3. Real PCR rule evaluations are produced
    rule_ids = [ev.rule_id for ev in report.evaluations]
    assert 'PCR-001' in rule_ids
    assert 'PCR-003' in rule_ids
    assert 'PCR-004' in rule_ids
    assert 'PCR-005' in rule_ids
    assert 'PCR-006' in rule_ids
    assert 'PCR-007' in rule_ids
    assert 'PCR-008' in rule_ids

    # PCR-001, PCR-003, PCR-004, PCR-005 evaluate to PASS on this compliant label
    eval_by_id = {ev.rule_id: ev for ev in report.evaluations}
    assert eval_by_id['PCR-001'].status == 'PASS'
    assert eval_by_id['PCR-003'].status == 'PASS'
    assert eval_by_id['PCR-004'].status == 'PASS'
    assert eval_by_id['PCR-005'].status == 'PASS'

    # 4. Evidence references contain OCR/source-image information
    findings = report.to_findings_projection()
    assert len(findings) > 0
    for finding in findings:
        assert finding['evidence_reference'] is not None
        assert 'package_label_ocr.png' in finding['evidence_reference']

    # 5. No DEMO-REQ findings are produced
    for finding in findings:
        assert not finding['rule_check_id'].startswith('DEMO-')
        assert 'DEMO' not in finding['rule_check_id']
        assert finding['rule_check_id'].startswith('PCR-')

    # 6. PCR-006 and PCR-008 never produce automated POTENTIAL_VIOLATION
    assert eval_by_id['PCR-006'].status == 'MANUAL_REVIEW'
    assert eval_by_id['PCR-006'].severity != 'critical'
    assert eval_by_id['PCR-008'].status == 'MANUAL_REVIEW'
    assert eval_by_id['PCR-008'].severity != 'critical'

    for finding in findings:
        if finding['rule_check_id'] in ('PCR-006', 'PCR-008'):
            assert finding['severity'] != 'critical'
            assert finding['status'] == 'open'
            assert 'manual verification' in finding['title'].lower()


def test_real_data_pipeline_determinism() -> None:
    """7. Verifies that evaluations of the real fixture produce deterministic output across repeated runs."""
    assert FIXTURE_PATH.exists()

    ocr_result = OCRService.analyze_image(FIXTURE_PATH, 'determinism-check')
    declarations = ocr_result['structured_declarations']

    engine = ComplianceEngine()
    results = []

    for run_idx in range(3):
        ctx = InspectionEvaluationContext(
            inspection_id=f'determinism-run-{run_idx}',
            inspection_context={'is_imported': False, 'commodity_category': 'food'},
            structured_declarations=declarations,
            ocr_evidence={'ocr_text': ocr_result['ocr_text'], 'source_file': FIXTURE_PATH.name},
        )
        report = engine.evaluate(ctx)
        findings = report.to_findings_projection()
        results.append((
            [(ev.rule_id, ev.status, ev.severity, ev.detected_value) for ev in report.evaluations],
            [(f['rule_check_id'], f['severity'], f['status'], f['title']) for f in findings],
        ))

    # All runs must be identical
    assert results[0] == results[1] == results[2], 'Compliance evaluation must be strictly deterministic across repeated runs'


def test_end_to_end_api_with_real_fixture_image() -> None:
    """Validates the complete HTTP workflow with real image upload, real OCR execution, and persisted PCR findings."""
    # 1. Create inspection
    insp_resp = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-REAL-001',
        'status': 'DRAFT',
        'title': 'Real Image Pipeline Inspection',
    })
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    # 2. Upload the real fixture image bytes
    with open(FIXTURE_PATH, 'rb') as f:
        image_bytes = f.read()

    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label_ocr.png', image_bytes, 'image/png')},
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()['file_name'] == 'package_label_ocr.png'

    # 3. Trigger analysis endpoint (executes PaddleOCR -> context -> ComplianceEngine -> DB)
    analyze_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_resp.status_code == 201
    analysis_data = analyze_resp.json()
    assert analysis_data['status'] == 'completed'
    assert analysis_data['extraction_metadata']['model'] == 'PaddleOCR'

    # 4. Verify persisted findings
    findings_resp = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_resp.status_code == 200
    persisted_findings = findings_resp.json()

    assert len(persisted_findings) >= 5

    # Check rule IDs and absence of DEMO-REQ
    rule_ids = {f['rule_check_id'] for f in persisted_findings}
    assert 'PCR-001' in rule_ids
    assert 'PCR-003' in rule_ids
    assert 'PCR-004' in rule_ids
    assert 'PCR-005' in rule_ids
    assert not any(f['rule_check_id'].startswith('DEMO-') for f in persisted_findings)

    # Check evidence traceability
    for f in persisted_findings:
        assert f['evidence_reference'] is not None
        assert 'package_label_ocr.png' in f['evidence_reference']

    # Check guardrails for non-executable rules
    for f in persisted_findings:
        if f['rule_check_id'] in ('PCR-006', 'PCR-008'):
            assert f['severity'] != 'critical'
            assert f['status'] == 'open'
