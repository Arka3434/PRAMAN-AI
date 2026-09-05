from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase9_declaration_review_test.db')

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app

client = TestClient(app)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "package_label_ocr.png"
RULES_CATALOG_PATH = Path(__file__).resolve().parents[2] / 'legal' / 'rule_catalog' / 'rules_v1.json'
EXPECTED_RULES_HASH = "b847e70c09bf2666cee117f0b800b8f26de5d5d86059d70966d794a5e6e13adc"


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _setup_analyzed_inspection(inspection_number: str = 'INSP-DEC-001') -> str:
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': inspection_number,
            'status': 'DRAFT',
            'title': 'Declaration Review Test',
        },
    )
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    upload_resp = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('label.png', img_bytes, 'image/png')},
    )
    assert upload_resp.status_code == 201

    analysis_resp = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analysis_resp.status_code == 201
    return insp_id


def test_field_correction_persists_and_ocr_evidence_is_immutable() -> None:
    insp_id = _setup_analyzed_inspection('INSP-DEC-002')

    # Get baseline analysis
    analysis_resp = client.get(f'/api/v1/inspections/{insp_id}/analysis')
    assert analysis_resp.status_code == 200
    baseline = analysis_resp.json()

    baseline_ocr_text = baseline['ocr_text']
    baseline_ocr_confidence = baseline['ocr_confidence']
    baseline_ocr_regions = baseline['ocr_regions']
    original_declarations = baseline['structured_declarations']

    # Patch declarations with inspector-verified corrections
    patch_payload = {
        'declarations': {
            'commodity_name': 'Pure Basmati Rice Premium Export Grade',
            'retail_sale_price': '₹ 320.00',
            'net_quantity': '1 kg',
        },
        'notes': 'Inspector verified label under magnifying viewer; corrected faded MRP and full commodity name.',
    }
    patch_resp = client.patch(f'/api/v1/inspections/{insp_id}/declarations', json=patch_payload)
    assert patch_resp.status_code == 200
    resp_data = patch_resp.json()

    # 1. Corrected values persist in structured_declarations
    assert resp_data['structured_declarations']['commodity_name'] == 'Pure Basmati Rice Premium Export Grade'
    assert resp_data['structured_declarations']['retail_sale_price'] == '₹ 320.00'
    assert resp_data['structured_declarations']['net_quantity'] == '1 kg'

    # 2. Raw OCR declarations baseline is stored separately and preserved
    raw_ocr = resp_data['raw_ocr_declarations']
    assert raw_ocr != resp_data['structured_declarations']
    # Raw OCR maintains original extraction
    for k in original_declarations:
        assert raw_ocr.get(k) == original_declarations.get(k)

    # 3. Inspector correction audit metadata is recorded
    corrections = resp_data['inspector_corrections']
    assert len(corrections) >= 1
    field_names = [c['field_name'] for c in corrections]
    assert 'commodity_name' in field_names
    assert 'retail_sale_price' in field_names

    for c in corrections:
        assert c['status'] == 'Inspector Verified'
        assert 'timestamp' in c
        assert 'original_value' in c
        assert 'corrected_value' in c
        assert c['notes'] == patch_payload['notes']

    # 4. Raw OCR evidence fields remain strictly immutable
    analysis_after = client.get(f'/api/v1/inspections/{insp_id}/analysis').json()
    assert analysis_after['ocr_text'] == baseline_ocr_text
    assert analysis_after['ocr_confidence'] == baseline_ocr_confidence
    assert analysis_after['ocr_regions'] == baseline_ocr_regions


def test_reevaluation_uses_corrected_values_to_change_engine_verdict() -> None:
    insp_id = _setup_analyzed_inspection('INSP-DEC-003')

    # Force retail_sale_price to be missing/empty to cause POTENTIAL_VIOLATION on PCR-007
    patch_invalid = {
        'declarations': {
            'retail_sale_price': '',
        },
        'notes': 'Simulate unreadable/missing price',
    }
    client.patch(f'/api/v1/inspections/{insp_id}/declarations', json=patch_invalid)

    findings_1 = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    pcr_007_finding = next((f for f in findings_1 if f['rule_check_id'] == 'PCR-007'), None)
    assert pcr_007_finding is not None
    assert pcr_007_finding['rule_status'] in {'POTENTIAL_VIOLATION', 'WARNING', 'MANUAL_REVIEW'}

    summary_resp = client.get(f'/api/v1/inspections/{insp_id}/summary')
    assert summary_resp.status_code == 200
    summary_1 = summary_resp.json()
    assert summary_1['engine_summary']['overall_result'] in {'POTENTIAL_VIOLATIONS_DETECTED', 'WARNINGS_OR_MANUAL_REVIEW'}

    # Now provide compliant, inspector-verified retail sale price
    patch_valid = {
        'declarations': {
            'retail_sale_price': '₹ 199.00 (Incl. of all taxes)',
        },
        'notes': 'Inspector verified valid MRP statement on lower seal',
    }
    patch_resp = client.patch(f'/api/v1/inspections/{insp_id}/declarations', json=patch_valid)
    assert patch_resp.status_code == 200

    findings_2 = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    pcr_007_finding_2 = next((f for f in findings_2 if f['rule_check_id'] == 'PCR-007'), None)
    assert pcr_007_finding_2 is not None
    # Corrected declaration caused engine finding to become PASS
    assert pcr_007_finding_2['rule_status'] == 'PASS'


def test_historical_inspector_decisions_preserved_and_obsolete_findings_unattached() -> None:
    insp_id = _setup_analyzed_inspection('INSP-DEC-004')

    initial_findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    assert len(initial_findings) > 0
    first_finding_id = initial_findings[0]['id']

    # Inspector submits a decision on the initial finding
    review_resp = client.post(
        f'/api/v1/inspections/{insp_id}/findings/{first_finding_id}/review',
        json={
            'decision': 'confirm',
            'reviewer_name': 'Officer Sharma',
            'notes': 'Confirmed non-compliance on first pass',
        },
    )
    assert review_resp.status_code == 201

    # Verify decision is attached to initial finding
    f_check = client.get(f'/api/v1/inspections/{insp_id}/findings').json()[0]
    assert f_check['inspector_decision'] == 'confirm'

    # Inspector updates declarations, triggering deterministic re-evaluation
    patch_resp = client.patch(
        f'/api/v1/inspections/{insp_id}/declarations',
        json={
            'declarations': {
                'commodity_name': 'Verified Wheat Flour',
            },
            'notes': 'Correction submitted',
        },
    )
    assert patch_resp.status_code == 200

    # Fresh findings generated after re-evaluation
    new_findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    assert len(new_findings) > 0

    # Invariant 6 & 9: Obsolete finding IDs are replaced, new evaluations are unreviewed
    for nf in new_findings:
        assert nf['id'] != first_finding_id
        assert nf['inspector_decision'] is None, "New engine finding must not inherit obsolete finding decision"

    # Historical decision remains preserved in the audit log
    reviews = client.get(f'/api/v1/inspections/{insp_id}/reviews').json()
    assert len(reviews) >= 1
    hist_decision = next((r for r in reviews if r['decision'] == 'confirm' and r['reviewer_name'] == 'Officer Sharma'), None)
    assert hist_decision is not None
    assert 'first pass' in str(hist_decision['notes'])


def test_repeated_correction_does_not_duplicate_findings() -> None:
    insp_id = _setup_analyzed_inspection('INSP-DEC-005')

    initial_findings = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    initial_count = len(initial_findings)

    # Perform 3 consecutive declaration patches
    for i in range(3):
        client.patch(
            f'/api/v1/inspections/{insp_id}/declarations',
            json={
                'declarations': {
                    'retail_sale_price': f'₹ {100 + i * 10}.00',
                },
                'notes': f'Iterative correction #{i + 1}',
            },
        )

    findings_after = client.get(f'/api/v1/inspections/{insp_id}/findings').json()
    # Number of findings must match engine rule projections, no uncontrolled duplication
    assert len(findings_after) == initial_count


def test_missing_and_unnanalyzed_inspection_error_responses() -> None:
    # 404 on missing inspection
    resp_404 = client.patch(
        '/api/v1/inspections/00000000-0000-0000-0000-000000000000/declarations',
        json={'declarations': {'commodity_name': 'Test'}},
    )
    assert resp_404.status_code == 404

    # 400 when analysis has not yet been performed
    insp_resp = client.post(
        '/api/v1/inspections',
        json={'inspection_number': 'INSP-UNANALYZED', 'title': 'No analysis yet'},
    )
    un_id = insp_resp.json()['id']
    resp_400 = client.patch(
        f'/api/v1/inspections/{un_id}/declarations',
        json={'declarations': {'commodity_name': 'Test'}},
    )
    assert resp_400.status_code == 400
    assert 'analysis has not been performed' in resp_400.json()['detail'].lower()


def test_scalar_and_structured_declaration_handling() -> None:
    insp_id = _setup_analyzed_inspection('INSP-DEC-006')

    # Complex structured payload (e.g. consumer contact dict, manufacturer address dict)
    structured_payload = {
        'declarations': {
            'commodity_name': 'Organic Rolled Oats',
            'net_quantity': '500',
            'quantity_unit': 'g',
            'consumer_contact': {
                'email': 'support@oatsbrand.in',
                'phone': '1800-200-3000',
                'person': 'Consumer Grievance Officer',
            },
            'country_of_origin': 'India',
        },
        'notes': 'Structured dictionary contact details preserved without string truncation',
    }

    resp = client.patch(f'/api/v1/inspections/{insp_id}/declarations', json=structured_payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data['structured_declarations']['consumer_contact']['email'] == 'support@oatsbrand.in'
    assert data['structured_declarations']['consumer_contact']['phone'] == '1800-200-3000'
    assert data['structured_declarations']['country_of_origin'] == 'India'


def test_rules_catalog_hash_and_compliance_engine_unmodified() -> None:
    # Invariant 4: rules_v1.json MUST NOT be modified
    assert RULES_CATALOG_PATH.exists()
    content = RULES_CATALOG_PATH.read_bytes()
    current_hash = hashlib.sha256(content).hexdigest()
    assert current_hash == EXPECTED_RULES_HASH, f"Catalog SHA modified! Expected {EXPECTED_RULES_HASH}, got {current_hash}"
