import os
import struct
import zlib
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase3_mvp_test.db')

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app
from app.services.ocr_service import OCRService


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def build_png_bytes() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b'\x00\x00\x00\x00'
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def test_create_inspection_and_product_flow() -> None:
    product_response = client.post('/api/v1/products', json={
        'name': 'PRAMAN Premium Rice 5kg',
        'category': 'food',
        'brand': 'PRAMAN',
        'manufacturer': 'PRAMAN Foods Pvt Ltd',
        'description': 'Demo packaged rice product',
    })
    assert product_response.status_code == 201, product_response.text
    product_payload = product_response.json()

    inspection_response = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-9001',
        'status': 'DRAFT',
        'title': 'Demo packaged goods inspection',
        'notes': 'Workflow validation',
        'product_id': product_payload['id'],
        'inspector_id': None,
    })
    assert inspection_response.status_code == 201, inspection_response.text
    inspection_payload = inspection_response.json()
    assert inspection_payload['status'] == 'DRAFT'

    detail = client.get(f"/api/v1/inspections/{inspection_payload['id']}")
    assert detail.status_code == 200
    assert detail.json()['title'] == 'Demo packaged goods inspection'


def test_image_upload_analysis_findings_review_and_finalize() -> None:
    product_response = client.post('/api/v1/products', json={
        'name': 'PRAMAN Premium Rice 5kg',
        'category': 'food',
        'brand': 'PRAMAN',
        'manufacturer': 'PRAMAN Foods Pvt Ltd',
    })
    product_payload = product_response.json()

    inspection_response = client.post('/api/v1/inspections', json={
        'inspection_number': 'INSP-9002',
        'status': 'DRAFT',
        'title': 'Product image review',
        'notes': 'Upload and validate demo evidence',
        'product_id': product_payload['id'],
        'inspector_id': None,
    })
    inspection_payload = inspection_response.json()

    upload_response = client.post(
        f"/api/v1/inspections/{inspection_payload['id']}/upload-image",
        files={'file': ('demo.png', build_png_bytes(), 'image/png')},
    )
    assert upload_response.status_code == 201, upload_response.text
    image_payload = upload_response.json()
    assert image_payload['file_name'] == 'demo.png'

    analysis_response = client.post(f"/api/v1/inspections/{inspection_payload['id']}/analyze")
    assert analysis_response.status_code == 201, analysis_response.text
    analysis_payload = analysis_response.json()
    assert analysis_payload['status'] == 'completed'
    assert 'commodity_name' in analysis_payload['structured_declarations']

    findings_response = client.get(f"/api/v1/inspections/{inspection_payload['id']}/findings")
    assert findings_response.status_code == 200
    findings = findings_response.json()
    assert len(findings) >= 1
    assert any(('DEMO' in item['title'] or 'PCR' in item['title']) for item in findings)

    review_response = client.post(
        f"/api/v1/inspections/{inspection_payload['id']}/review",
        json={'inspection_id': inspection_payload['id'], 'decision': 'confirm', 'reviewer_name': 'demo-inspector', 'notes': 'Looks valid enough for MVP flow'},
    )
    assert review_response.status_code == 201, review_response.text
    review_payload = review_response.json()
    assert review_payload['decision'] == 'confirm'

    finalize_response = client.post(f"/api/v1/inspections/{inspection_payload['id']}/finalize")
    assert finalize_response.status_code == 200, finalize_response.text
    finalized = finalize_response.json()
    assert finalized['status'] == 'COMPLETED'


def test_ocr_analysis_returns_structured_project_data() -> None:
    product_response = client.post('/api/v1/products', json={'name': 'PRAMAN Premium Rice 5kg', 'category': 'food', 'brand': 'PRAMAN'})
    inspection_response = client.post('/api/v1/inspections', json={'inspection_number': 'INSP-9003', 'status': 'DRAFT', 'title': 'OCR extraction check', 'product_id': product_response.json()['id']})
    inspection_id = inspection_response.json()['id']

    upload_response = client.post(
        f"/api/v1/inspections/{inspection_id}/upload-image",
        files={'file': ('demo.png', build_png_bytes(), 'image/png')},
    )
    assert upload_response.status_code == 201, upload_response.text

    analysis_response = client.post(f"/api/v1/inspections/{inspection_id}/analyze")
    assert analysis_response.status_code == 201, analysis_response.text
    analysis_payload = analysis_response.json()
    assert analysis_payload['ocr_text']
    assert analysis_payload['structured_declarations']['commodity_name']
    assert analysis_payload['ocr_confidence'] >= 0


def test_image_validation_rejects_non_image_upload() -> None:
    product_response = client.post('/api/v1/products', json={'name': 'Test product', 'category': 'food', 'brand': 'PRAMAN'})
    inspection_response = client.post('/api/v1/inspections', json={'inspection_number': 'INSP-9004', 'status': 'DRAFT', 'title': 'Invalid upload check', 'product_id': product_response.json()['id']})
    inspection_id = inspection_response.json()['id']

    invalid_response = client.post(
        f"/api/v1/inspections/{inspection_id}/upload-image",
        files={'file': ('example.txt', b'not an image', 'text/plain')},
    )
    assert invalid_response.status_code == 400


def test_real_paddleocr_fixture_produces_regions() -> None:
    fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'package_label_ocr.png'
    assert fixture_path.exists(), 'OCR fixture image missing'

    result = OCRService.analyze_image(fixture_path, 'ocr-fixture-check')

    assert result['extraction_metadata']['model'] == 'PaddleOCR', 'OCRService must use real PaddleOCR when available'
    assert result['extraction_metadata']['real_ocr_used'] is True, 'real OCR must be marked as used'
    assert result['ocr_regions'], 'PaddleOCR must return at least one detected region'
    assert result['ocr_text'].strip(), 'OCR text must be non-empty'
    assert result['ocr_confidence'] > 0.0, 'OCR confidence should be positive'
    assert any('PRAMAN' in region['text'] for region in result['ocr_regions']), 'OCR must detect package-style text from the fixture'
