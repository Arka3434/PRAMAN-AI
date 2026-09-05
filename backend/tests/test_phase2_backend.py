import os

os.environ.setdefault('DATABASE_URL', 'sqlite:///./phase2_test.db')

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.inspection import Inspection
from app.models.product import Product
from app.models.user import User


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def test_health_endpoints() -> None:
    root_response = client.get('/health')
    assert root_response.status_code == 200
    assert root_response.json()['status'] == 'ok'

    api_response = client.get('/api/v1/health')
    assert api_response.status_code == 200
    assert api_response.json()['api_version'] == 'v1'


def test_products_api_crud_and_listing() -> None:
    payload = {'name': 'Piston Assembly', 'category': 'Engine', 'brand': 'PRAMAN', 'manufacturer': 'ACME'}

    created = client.post('/api/v1/products', json=payload)
    assert created.status_code == 201, created.text
    created_payload = created.json()
    assert created_payload['name'] == payload['name']
    assert created_payload['category'] == payload['category']

    listed = client.get('/api/v1/products')
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]['id'] == created_payload['id']

    detail = client.get(f"/api/v1/products/{created_payload['id']}")
    assert detail.status_code == 200
    assert detail.json()['brand'] == 'PRAMAN'


def test_users_and_inspections_api_with_relationships() -> None:
    user_payload = {'full_name': 'Riya Mehta', 'email': 'riya.mehta@example.com', 'role': 'inspector'}
    product_payload = {'name': 'Valve Kit', 'category': 'Hydraulic', 'brand': 'PRAMAN'}

    user_response = client.post('/api/v1/users', json=user_payload)
    assert user_response.status_code == 201, user_response.text
    user_data = user_response.json()

    product_response = client.post('/api/v1/products', json=product_payload)
    assert product_response.status_code == 201, product_response.text
    product_data = product_response.json()

    inspection_payload = {
        'inspection_number': 'INSP-2026-001',
        'status': 'draft',
        'title': 'Initial valve inspection',
        'notes': 'Evidence collection pending',
        'product_id': product_data['id'],
        'inspector_id': user_data['id'],
    }

    created = client.post('/api/v1/inspections', json=inspection_payload)
    assert created.status_code == 201, created.text
    inspection_data = created.json()
    assert inspection_data['inspection_number'] == inspection_payload['inspection_number']
    assert inspection_data['product_id'] == product_data['id']
    assert inspection_data['inspector_id'] == user_data['id']

    listed = client.get('/api/v1/inspections')
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = client.get(f"/api/v1/inspections/{inspection_data['id']}")
    assert detail.status_code == 200
    assert detail.json()['title'] == 'Initial valve inspection'

    with SessionLocal() as db:
        saved_user = db.scalar(select(User).where(User.id == user_data['id']))
        saved_product = db.scalar(select(Product).where(Product.id == product_data['id']))
        saved_inspection = db.scalar(select(Inspection).where(Inspection.id == inspection_data['id']))

        assert saved_user is not None
        assert saved_product is not None
        assert saved_inspection is not None
        assert saved_inspection.product_id == saved_product.id
        assert saved_inspection.inspector_id == saved_user.id
        assert saved_product.inspections[0].id == saved_inspection.id
        assert saved_user.inspections[0].id == saved_inspection.id
