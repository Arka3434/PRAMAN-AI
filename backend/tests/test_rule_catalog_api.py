from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_rule_catalog_metadata_and_hash(client: TestClient) -> None:
    """Verify catalog metadata, regulatory framework, and SHA-256 cryptographic digest."""
    resp = client.get('/api/v1/rules')
    assert resp.status_code == 200
    data = resp.json()

    assert data['catalog_version'] == '1.0.0'
    assert data['jurisdiction'] == 'India'
    assert 'Legal Metrology' in data['regulatory_framework']
    assert 'statutory' in data['coverage_notice'].lower()

    # Verify SHA-256 matches actual rules_v1.json file
    catalog_path = Path(__file__).resolve().parents[2] / 'legal' / 'rule_catalog' / 'rules_v1.json'
    expected_hash = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    assert data['catalog_hash'] == expected_hash
    assert data['catalog_hash'] == 'b847e70c09bf2666cee117f0b800b8f26de5d5d86059d70966d794a5e6e13adc'


def test_rule_catalog_rule_counts_and_safety(client: TestClient) -> None:
    """Verify exactly 8 rules: 6 SAFE, 2 NEEDS_VERIFICATION."""
    resp = client.get('/api/v1/rules')
    assert resp.status_code == 200
    data = resp.json()

    assert data['total_rules'] == 8
    assert data['safe_rules_count'] == 6
    assert data['needs_verification_count'] == 2

    rules = data['rules']
    assert len(rules) == 8

    # Ensure rule IDs PCR-001 through PCR-008 are present
    rule_ids = {r['rule_id'] for r in rules}
    assert rule_ids == {f'PCR-00{i}' for i in range(1, 9)}

    # Ensure PCR-006 and PCR-008 are NEEDS_VERIFICATION
    pcr_006 = next(r for r in rules if r['rule_id'] == 'PCR-006')
    assert pcr_006['executable_status'] == 'NEEDS_VERIFICATION'

    pcr_008 = next(r for r in rules if r['rule_id'] == 'PCR-008')
    assert pcr_008['executable_status'] == 'NEEDS_VERIFICATION'

    # Ensure PCR-007 is SAFE and is the only MRP rule
    pcr_007 = next(r for r in rules if r['rule_id'] == 'PCR-007')
    assert pcr_007['executable_status'] == 'SAFE'
    assert 'Maximum Retail Price' in pcr_007['title']


def test_rule_catalog_filtering_by_status(client: TestClient) -> None:
    """Verify filtering by status=SAFE and status=NEEDS_VERIFICATION."""
    # Filter SAFE
    safe_resp = client.get('/api/v1/rules?status=SAFE')
    assert safe_resp.status_code == 200
    safe_data = safe_resp.json()
    assert len(safe_data['rules']) == 6
    for r in safe_data['rules']:
        assert r['executable_status'] == 'SAFE'

    # Filter NEEDS_VERIFICATION
    nv_resp = client.get('/api/v1/rules?status=NEEDS_VERIFICATION')
    assert nv_resp.status_code == 200
    nv_data = nv_resp.json()
    assert len(nv_data['rules']) == 2
    for r in nv_data['rules']:
        assert r['executable_status'] == 'NEEDS_VERIFICATION'
    assert {r['rule_id'] for r in nv_data['rules']} == {'PCR-006', 'PCR-008'}


def test_rule_catalog_search(client: TestClient) -> None:
    """Verify search filter by rule ID and keyword."""
    # Search by rule ID
    resp_id = client.get('/api/v1/rules?search=PCR-007')
    assert resp_id.status_code == 200
    data_id = resp_id.json()
    assert len(data_id['rules']) == 1
    assert data_id['rules'][0]['rule_id'] == 'PCR-007'

    # Search by keyword
    resp_kw = client.get('/api/v1/rules?search=perishable')
    assert resp_kw.status_code == 200
    data_kw = resp_kw.json()
    assert len(data_kw['rules']) >= 1
    assert any(r['rule_id'] == 'PCR-006' for r in data_kw['rules'])


def test_get_single_rule_detail(client: TestClient) -> None:
    """Verify retrieval of a single rule by ID."""
    resp = client.get('/api/v1/rules/PCR-007')
    assert resp.status_code == 200
    rule = resp.json()

    assert rule['rule_id'] == 'PCR-007'
    assert 'Maximum Retail Price' in rule['title']
    assert 'Rule 6(1)(e)' in rule['legal_citation']
    assert rule['source_document'] is not None
    assert rule['effective_from'] == '2011-04-01'
    assert rule['is_currently_effective'] is True
    assert len(rule['exemptions']) > 0
    assert rule['severity'] == 'critical'
    assert rule['executable_status'] == 'SAFE'

    # Non-existent rule returns 404
    resp_404 = client.get('/api/v1/rules/PCR-999')
    assert resp_404.status_code == 404


def test_catalog_api_is_read_only(client: TestClient) -> None:
    """Verify that mutating HTTP methods are disallowed."""
    resp_post = client.post('/api/v1/rules', json={'title': 'Unauthorized Rule'})
    assert resp_post.status_code == 405

    resp_put = client.put('/api/v1/rules/PCR-001', json={'title': 'Tampered Rule'})
    assert resp_put.status_code == 405

    resp_del = client.delete('/api/v1/rules/PCR-001')
    assert resp_del.status_code == 405
