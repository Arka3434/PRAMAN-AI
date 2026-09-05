from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase6_visual_evidence_test.db')

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


def test_get_inspection_image_file_endpoint() -> None:
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': 'INSP-VIS-001',
            'status': 'DRAFT',
            'title': 'Visual Evidence Endpoint Test',
        },
    )
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    assert FIXTURE_PATH.exists()
    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    upload_res = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label_ocr.png', img_bytes, 'image/png')},
    )
    assert upload_res.status_code == 201
    image_data = upload_res.json()
    image_id = image_data['id']
    storage_path = image_data['storage_path']

    # Test file retrieval endpoint
    file_res = client.get(f'/api/v1/inspections/{insp_id}/images/{image_id}/file')
    assert file_res.status_code == 200
    assert file_res.headers['content-type'] == 'image/png'
    assert len(file_res.content) == len(img_bytes)

    # Test nonexistent image_id returns 404
    bad_res = client.get(f'/api/v1/inspections/{insp_id}/images/nonexistent-id/file')
    assert bad_res.status_code == 404

    # Test static storage route
    static_url = f'/{storage_path}'
    static_res = client.get(static_url)
    assert static_res.status_code == 200
    assert len(static_res.content) == len(img_bytes)


def test_visual_evidence_in_findings() -> None:
    insp_resp = client.post(
        '/api/v1/inspections',
        json={
            'inspection_number': 'INSP-VIS-002',
            'status': 'DRAFT',
            'title': 'Visual Evidence Findings Test',
        },
    )
    assert insp_resp.status_code == 201
    insp_id = insp_resp.json()['id']

    with open(FIXTURE_PATH, 'rb') as f:
        img_bytes = f.read()

    upload_res = client.post(
        f'/api/v1/inspections/{insp_id}/upload-image',
        files={'file': ('package_label_ocr.png', img_bytes, 'image/png')},
    )
    assert upload_res.status_code == 201
    uploaded_image = upload_res.json()

    # Run analysis
    analyze_res = client.post(f'/api/v1/inspections/{insp_id}/analyze')
    assert analyze_res.status_code == 201

    # Fetch findings
    findings_res = client.get(f'/api/v1/inspections/{insp_id}/findings')
    assert findings_res.status_code == 200
    findings = findings_res.json()
    assert len(findings) > 0

    # Verify visual evidence fields on findings
    for finding in findings:
        assert 'storage_path' in finding
        assert 'image_id' in finding
        assert finding['storage_path'] == uploaded_image['storage_path']
        assert finding['image_id'] == uploaded_image['id']
        assert finding['source_image'] is not None

        # When a finding has detected a declaration (e.g. MRP PCR-007, Net Qty PCR-003, etc.)
        # its evidence_location contains bounding coordinates
        if finding['rule_check_id'] == 'PCR-007':
            assert finding['evidence_location'] is not None
            assert len(finding['evidence_location']) >= 4
            assert finding['evidence_snippet'] is not None
            assert '299' in finding['evidence_snippet'] or 'Price' in finding['evidence_snippet']

    # Verify that missing declarations (e.g., domestic product with no imported country of origin) do not invent coordinates
    pcr_002 = next((f for f in findings if f['rule_check_id'] == 'PCR-002'), None)
    if pcr_002 and pcr_002['severity'] != 'pass':
        assert pcr_002['evidence_location'] is None
