from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.user import User

client = TestClient(app)


def create_test_image_bytes(format: str = "JPEG", size: tuple[int, int] = (200, 200), color: str = "blue") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def seed_demo_users_helper(db):
    from app.core.security import hash_password
    from app.core.roles import UserRole
    pwd_hash = hash_password("ValidPass123!@#")
    demo_users = [
        ("admin@praman.gov.in", "Admin Officer", UserRole.ADMIN.value),
        ("supervisor@praman.gov.in", "Supervising Officer Sharma", UserRole.SUPERVISING_OFFICER.value),
        ("inspector1@praman.gov.in", "Inspector Rajesh Kumar", UserRole.LEGAL_METROLOGY_INSPECTOR.value),
        ("inspector2@praman.gov.in", "Inspector Priya Singh", UserRole.LEGAL_METROLOGY_INSPECTOR.value),
        ("reviewer@praman.gov.in", "Review Officer Verma", UserRole.REVIEWER.value),
    ]
    for email, name, role in demo_users:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name=name, role=role, hashed_password=pwd_hash, is_active=True, failed_login_attempts=0, locked_until=None)
            db.add(u)
    db.commit()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_users_helper(db)
    yield



import uuid


def test_image_upload_formats_and_token_query():
    """Verify JPEG (both image/jpeg and image/jpg), PNG, multi-upload, and query token file retrieval."""
    uid = uuid.uuid4().hex[:8]
    email = f"inspector.upload.{uid}@praman.gov.in"
    with SessionLocal() as db:
        user = User(
            email=email,
            hashed_password="fakehashedpassword",
            full_name="Upload Inspector",
            role="LEGAL_METROLOGY_INSPECTOR",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)

    token = create_access_token(user_id, role="LEGAL_METROLOGY_INSPECTOR", email=email)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create inspection
    insp_res = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-TEST-UP-{uid}", "status": "DRAFT", "title": "Image Upload Test"},
        headers=headers,
    )
    assert insp_res.status_code == 201
    insp_id = insp_res.json()["id"]

    # 2. Upload JPEG with image/jpeg
    jpeg_bytes = create_test_image_bytes("JPEG", color="green")
    up1 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("front.jpeg", jpeg_bytes, "image/jpeg"))],
        data={"image_type": "front"},
        headers=headers,
    )
    assert up1.status_code == 201
    img1 = up1.json()[0]
    img1_id = img1["id"]

    # 3. Upload JPEG with image/jpg (testing expanded MIME support)
    jpg_bytes = create_test_image_bytes("JPEG", color="yellow")
    up2 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("back.jpg", jpg_bytes, "image/jpg"))],
        data={"image_type": "back"},
        headers=headers,
    )
    assert up2.status_code == 201
    img2 = up2.json()[0]

    # 4. Upload PNG with image/png
    png_bytes = create_test_image_bytes("PNG", color="red")
    up3 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("side.png", png_bytes, "image/png"))],
        data={"image_type": "left_side"},
        headers=headers,
    )
    assert up3.status_code == 201
    img3 = up3.json()[0]

    # 5. Multiple files in a single upload
    multi_up = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[
            ("files", ("multi1.jpg", jpg_bytes, "image/jpeg")),
            ("files", ("multi2.png", png_bytes, "image/png")),
        ],
        data={"image_type": "other"},
        headers=headers,
    )
    assert multi_up.status_code == 201
    assert len(multi_up.json()) == 2

    # 6. Verify file retrieval with Authorization Header
    get_file_hdr = client.get(
        f"/api/v1/inspections/{insp_id}/images/{img1_id}/file",
        headers=headers,
    )
    assert get_file_hdr.status_code == 200
    assert len(get_file_hdr.content) == len(jpeg_bytes)

    # 7. Verify file retrieval with Query Parameter ?token= (used by browser <img> tags!)
    get_file_query = client.get(
        f"/api/v1/inspections/{insp_id}/images/{img1_id}/file?token={token}"
    )
    assert get_file_query.status_code == 200
    assert len(get_file_query.content) == len(jpeg_bytes)

    # 8. Verify unauthenticated retrieval fails with 401
    get_file_no_auth = client.get(f"/api/v1/inspections/{insp_id}/images/{img1_id}/file")
    assert get_file_no_auth.status_code == 401


def test_cross_inspector_ownership_enforcement():
    """Verify that Inspector 2 cannot upload an image to Inspector 1's inspection."""
    uid1 = uuid.uuid4().hex[:8]
    uid2 = uuid.uuid4().hex[:8]
    email1 = f"inspector.alpha.{uid1}@praman.gov.in"
    email2 = f"inspector.beta.{uid2}@praman.gov.in"
    with SessionLocal() as db:
        u1 = User(email=email1, hashed_password="pw", full_name="Alpha", role="LEGAL_METROLOGY_INSPECTOR", is_active=True)
        u2 = User(email=email2, hashed_password="pw", full_name="Beta", role="LEGAL_METROLOGY_INSPECTOR", is_active=True)
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)
        id1, id2 = str(u1.id), str(u2.id)

    token1 = create_access_token(id1, role="LEGAL_METROLOGY_INSPECTOR", email=email1)
    token2 = create_access_token(id2, role="LEGAL_METROLOGY_INSPECTOR", email=email2)

    # Inspector 1 creates inspection
    insp_res = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-ALPHA-{uid1}", "status": "DRAFT", "title": "Alpha Inspection"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert insp_res.status_code == 201
    insp_id = insp_res.json()["id"]

    # Inspector 1 claims it
    jpeg_bytes = create_test_image_bytes("JPEG")
    up1 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("alpha.jpg", jpeg_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert up1.status_code == 201

    # Inspector 2 attempts to upload to Inspector 1's inspection -> MUST return 403 Forbidden
    up2 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("beta.jpg", jpeg_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert up2.status_code == 403
    assert "You do not have permission to modify an inspection assigned to another officer" in up2.text


def test_corrupt_file_magic_bytes_rejection():
    """Verify that corrupt or non-image files with spoofed Content-Type are rejected."""
    uid = uuid.uuid4().hex[:8]
    email = f"inspector.val.{uid}@praman.gov.in"
    with SessionLocal() as db:
        user = User(email=email, hashed_password="pw", full_name="Val", role="ADMIN", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)

    token = create_access_token(user_id, role="ADMIN", email=email)
    headers = {"Authorization": f"Bearer {token}"}

    insp_res = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-VAL-{uid}", "status": "DRAFT", "title": "Validation Test"},
        headers=headers,
    )
    insp_id = insp_res.json()["id"]

    # Fake JPEG with text content
    fake_jpeg = b"This is plain text pretending to be a jpeg"
    res = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("fake.jpg", fake_jpeg, "image/jpeg"))],
        headers=headers,
    )
    assert res.status_code == 400
    assert "Uploaded file is not a valid JPEG image" in res.text

    # Fake PNG with text content
    fake_png = b"This is plain text pretending to be a png"
    res2 = client.post(
        f"/api/v1/inspections/{insp_id}/upload-images",
        files=[("files", ("fake.png", fake_png, "image/png"))],
        headers=headers,
    )
    assert res2.status_code == 400
    assert "Uploaded file is not a valid PNG image" in res2.text


def test_authorized_roles_and_reviewer_upload():
    """Verify ADMIN and SUPERVISING_OFFICER can upload, while REVIEWER cannot (403)."""
    uid = uuid.uuid4().hex[:8]
    email_admin = f"admin.up.{uid}@praman.gov.in"
    email_super = f"super.up.{uid}@praman.gov.in"
    email_review = f"review.up.{uid}@praman.gov.in"
    with SessionLocal() as db:
        admin = User(email=email_admin, hashed_password="pw", full_name="Admin Up", role="ADMIN", is_active=True)
        superv = User(email=email_super, hashed_password="pw", full_name="Super Up", role="SUPERVISING_OFFICER", is_active=True)
        review = User(email=email_review, hashed_password="pw", full_name="Review Up", role="REVIEWER", is_active=True)
        db.add_all([admin, superv, review])
        db.commit()
        db.refresh(admin)
        db.refresh(superv)
        db.refresh(review)
        admin_id, super_id, review_id = str(admin.id), str(superv.id), str(review.id)

    token_admin = create_access_token(admin_id, role="ADMIN", email=email_admin)
    token_super = create_access_token(super_id, role="SUPERVISING_OFFICER", email=email_super)
    token_review = create_access_token(review_id, role="REVIEWER", email=email_review)

    # 1. Admin creates and uploads
    insp_admin = client.post(
        "/api/v1/inspections",
        json={"inspection_number": f"INSP-ROLE-{uid}", "status": "DRAFT", "title": "Admin Inspection"},
        headers={"Authorization": f"Bearer {token_admin}"},
    ).json()["id"]

    jpeg_bytes = create_test_image_bytes("JPEG")
    up_admin = client.post(
        f"/api/v1/inspections/{insp_admin}/upload-images",
        files=[("files", ("admin_img.jpg", jpeg_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert up_admin.status_code == 201

    # 2. Supervisor uploads to inspection
    up_super = client.post(
        f"/api/v1/inspections/{insp_admin}/upload-images",
        files=[("files", ("super_img.jpg", jpeg_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token_super}"},
    )
    assert up_super.status_code == 201

    # 3. Reviewer attempts to upload -> MUST be 403 Forbidden
    up_review = client.post(
        f"/api/v1/inspections/{insp_admin}/upload-images",
        files=[("files", ("review_img.jpg", jpeg_bytes, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token_review}"},
    )
    assert up_review.status_code == 403
    assert "inspection:edit" in up_review.text


