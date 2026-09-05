from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_initial_admin
from app.core.permissions import Permission, ROLE_PERMISSIONS
from app.core.roles import UserRole
from app.core.security import create_access_token, get_password_hash, UNUSABLE_PASSWORD_PREFIX
from app.db.session import get_db, SessionLocal
from app.main import app
from app.models.inspection import Inspection
from app.models.notice import Notice
from app.models.user import User


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_users(db_session: Session):
    pwd_hash = get_password_hash("ValidPass123!@#")

    def get_or_create_user(email: str, **attrs) -> User:
        user = db_session.scalars(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, **attrs)
            db_session.add(user)
        else:
            for k, v in attrs.items():
                setattr(user, k, v)
        db_session.commit()
        db_session.refresh(user)
        return user

    admin = get_or_create_user(
        "admin@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Admin Officer",
        role=UserRole.ADMIN.value,
        designation="Chief Administrator",
        jurisdiction_office="Central HQ",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    supervisor = get_or_create_user(
        "supervisor@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Supervising Officer Sharma",
        role=UserRole.SUPERVISING_OFFICER.value,
        designation="Deputy Controller",
        jurisdiction_office="Delhi Central Zone",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    inspector1 = get_or_create_user(
        "inspector1@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Inspector Rajesh Kumar",
        role=UserRole.LEGAL_METROLOGY_INSPECTOR.value,
        designation="Senior Metrology Inspector",
        jurisdiction_office="Delhi North Ward",
        badge_number="DL-LM-101",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    inspector2 = get_or_create_user(
        "inspector2@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Inspector Priya Singh",
        role=UserRole.LEGAL_METROLOGY_INSPECTOR.value,
        designation="Senior Metrology Inspector",
        jurisdiction_office="Delhi South Ward",
        badge_number="DL-LM-102",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    reviewer = get_or_create_user(
        "reviewer@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Reviewer Verma",
        role=UserRole.REVIEWER.value,
        designation="Technical Reviewer",
        jurisdiction_office="HQ Review Cell",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    legacy_user = get_or_create_user(
        "legacy@praman.gov.in",
        hashed_password=f"{UNUSABLE_PASSWORD_PREFIX}legacy_import_unusable",
        full_name="Legacy Unusable",
        role=UserRole.LEGAL_METROLOGY_INSPECTOR.value,
        designation="Field Officer",
        jurisdiction_office="Legacy Zone",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )

    inactive_user = get_or_create_user(
        "inactive@praman.gov.in",
        hashed_password=pwd_hash,
        full_name="Inactive Officer",
        role=UserRole.LEGAL_METROLOGY_INSPECTOR.value,
        designation="Suspended Officer",
        jurisdiction_office="Delhi North Ward",
        is_active=False,
        failed_login_attempts=0,
        locked_until=None,
    )

    return {
        "admin": admin,
        "supervisor": supervisor,
        "inspector1": inspector1,
        "inspector2": inspector2,
        "reviewer": reviewer,
        "legacy": legacy_user,
        "inactive": inactive_user,
    }


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role, expires_delta=60)
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Canonical Role Normalization & Permissions
# =========================================================================

def test_canonical_role_normalization():
    assert UserRole.normalize("inspector") == UserRole.LEGAL_METROLOGY_INSPECTOR
    assert UserRole.normalize("supervisor") == UserRole.SUPERVISING_OFFICER
    assert UserRole.normalize("supervising_officer") == UserRole.SUPERVISING_OFFICER
    assert UserRole.normalize("admin") == UserRole.ADMIN
    assert UserRole.normalize("reviewer") == UserRole.REVIEWER
    assert UserRole.normalize("LEGAL_METROLOGY_INSPECTOR") == UserRole.LEGAL_METROLOGY_INSPECTOR


def test_rbac_permission_matrix():
    admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
    assert Permission.USERS_MANAGE in admin_perms
    assert Permission.NOTICE_ISSUE in admin_perms

    inspector_perms = ROLE_PERMISSIONS[UserRole.LEGAL_METROLOGY_INSPECTOR]
    assert Permission.INSPECTION_CREATE in inspector_perms
    assert Permission.INSPECTION_EDIT in inspector_perms
    assert Permission.NOTICE_DRAFT in inspector_perms
    assert Permission.NOTICE_ISSUE not in inspector_perms
    assert Permission.USERS_MANAGE not in inspector_perms

    supervisor_perms = ROLE_PERMISSIONS[UserRole.SUPERVISING_OFFICER]
    assert Permission.NOTICE_ISSUE in supervisor_perms
    assert Permission.INSPECTION_FINALIZE in supervisor_perms

    reviewer_perms = ROLE_PERMISSIONS[UserRole.REVIEWER]
    assert Permission.FINDING_REVIEW in reviewer_perms
    assert Permission.INSPECTION_CREATE not in reviewer_perms
    assert Permission.NOTICE_ISSUE not in reviewer_perms


# =========================================================================
# 2. Authentication: Login, Logout, Lockout
# =========================================================================

def test_login_success(client: TestClient, test_users: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector1@praman.gov.in", "password": "ValidPass123!@#"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "inspector1@praman.gov.in"
    assert data["user"]["role"] == "LEGAL_METROLOGY_INSPECTOR"
    assert "inspection:create" in data["user"]["permissions"]


def test_login_incorrect_password(client: TestClient, test_users: dict, db_session: Session):
    insp = test_users["inspector1"]
    initial_fails = insp.failed_login_attempts or 0

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector1@praman.gov.in", "password": "WrongPassword123!"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    db_session.refresh(insp)
    assert insp.failed_login_attempts == initial_fails + 1


def test_lockout_after_five_failed_attempts(client: TestClient, test_users: dict, db_session: Session):
    # Perform 5 failed attempts
    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "inspector2@praman.gov.in", "password": "WrongPassword123!"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    insp2 = test_users["inspector2"]
    db_session.refresh(insp2)
    assert insp2.locked_until is not None
    locked_until = insp2.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    assert locked_until > datetime.now(timezone.utc)

    # 6th attempt should return 401 account locked
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector2@praman.gov.in", "password": "ValidPass123!@#"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "locked" in resp.json()["detail"].lower()


def test_successful_login_resets_failed_counter(client: TestClient, test_users: dict, db_session: Session):
    insp = test_users["inspector1"]
    insp.failed_login_attempts = 3
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inspector1@praman.gov.in", "password": "ValidPass123!@#"},
    )
    assert resp.status_code == status.HTTP_200_OK

    db_session.refresh(insp)
    assert insp.failed_login_attempts == 0


def test_unusable_password_account_rejected(client: TestClient, test_users: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@praman.gov.in", "password": "AnyPassword123!"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "unusable" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()


def test_inactive_user_rejected(client: TestClient, test_users: dict):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@praman.gov.in", "password": "ValidPass123!@#"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "inactive" in resp.json()["detail"].lower()


def test_get_current_user_me(client: TestClient, test_users: dict):
    insp = test_users["inspector1"]
    resp = client.get("/api/v1/auth/me", headers=auth_headers(insp))
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["email"] == insp.email
    assert data["badge_number"] == "DL-LM-101"
    assert "inspection:create" in data["permissions"]


def test_logout_endpoint_semantics(client: TestClient, test_users: dict):
    insp = test_users["inspector1"]
    resp = client.post("/api/v1/auth/logout", headers=auth_headers(insp))
    assert resp.status_code == status.HTTP_200_OK
    assert "session" in resp.json()["message"].lower()


# =========================================================================
# 3. Resource Ownership & Multi-Tenancy Protection
# =========================================================================

def test_inspector_cannot_mutate_another_inspectors_inspection(
    client: TestClient, test_users: dict, db_session: Session
):
    insp1 = test_users["inspector1"]
    insp2 = test_users["inspector2"]

    # Create inspection owned by Inspector 1
    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="DRAFT",
        inspector_id=insp1.id,
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    # Inspector 2 tries to update barcode on Inspector 1's inspection -> 403 Forbidden
    resp = client.patch(
        f"/api/v1/inspections/{inspection.id}/barcode?barcode_or_qr=8901234567890",
        headers=auth_headers(insp2),
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "another officer" in resp.json()["detail"].lower()


def test_supervisor_can_mutate_any_inspectors_inspection(
    client: TestClient, test_users: dict, db_session: Session
):
    insp1 = test_users["inspector1"]
    supervisor = test_users["supervisor"]

    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="DRAFT",
        inspector_id=insp1.id,
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    # Supervisor updates barcode -> 200 OK
    resp = client.patch(
        f"/api/v1/inspections/{inspection.id}/barcode?barcode_or_qr=8901234567890",
        headers=auth_headers(supervisor),
    )
    assert resp.status_code == status.HTTP_200_OK


def test_inspector_can_claim_unassigned_inspection(
    client: TestClient, test_users: dict, db_session: Session
):
    insp1 = test_users["inspector1"]

    # Unassigned inspection
    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="DRAFT",
        inspector_id=None,
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    resp = client.patch(
        f"/api/v1/inspections/{inspection.id}/barcode?barcode_or_qr=8901234567890",
        headers=auth_headers(insp1),
    )
    assert resp.status_code == status.HTTP_200_OK

    db_session.refresh(inspection)
    assert inspection.inspector_id == insp1.id


# =========================================================================
# 4. Officer Identity & Notice Issuance Immutability
# =========================================================================

def test_notice_issuance_binds_authenticated_officer_and_locks(
    client: TestClient, test_users: dict, db_session: Session
):
    supervisor = test_users["supervisor"]

    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="COMPLETED",
        inspector_id=supervisor.id,
    )
    db_session.add(inspection)
    db_session.commit()
    db_session.refresh(inspection)

    notice = Notice(
        inspection_id=inspection.id,
        notice_reference=f"SCN-2026-{inspection.inspection_number[:8]}",
        status="REVIEWED",
        recipient_role="manufacturer",
        recipient_name="Acme Foods Pvt Ltd",
        recipient_address="Plot 12, Industrial Area, Delhi",
        statutory_charges=[{"rule_id": "PCR-001", "description": "Missing packer address"}],
        legal_version_context={"catalog_version": "1.0"},
        evidence_references=[],
        is_immutable=False,
    )
    db_session.add(notice)
    db_session.commit()
    db_session.refresh(notice)

    # Issue notice with supervisor credentials
    resp = client.post(
        f"/api/v1/notices/{notice.id}/issue",
        headers=auth_headers(supervisor),
        json={"officer_notes": "Issued after formal verification."},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["status"] == "ISSUED_BY_OFFICER"
    assert data["is_immutable"] is True
    assert data["issuing_officer_id"] == supervisor.id
    assert data["officer_name"] == supervisor.full_name
    assert data["officer_designation"] == supervisor.designation
    assert data["officer_office"] == supervisor.jurisdiction_office

    # INVARIANT: Updating supervisor user record later does NOT change historical snapshot
    supervisor.full_name = "Completely New Name"
    supervisor.designation = "Different Designation"
    db_session.commit()

    db_session.refresh(notice)
    assert notice.officer_name == "Supervising Officer Sharma"
    assert notice.officer_designation == "Deputy Controller"


def test_inspector_cannot_issue_notice(
    client: TestClient, test_users: dict, db_session: Session
):
    insp1 = test_users["inspector1"]

    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="COMPLETED",
        inspector_id=insp1.id,
    )
    db_session.add(inspection)
    db_session.commit()

    notice = Notice(
        inspection_id=inspection.id,
        notice_reference=f"SCN-2026-{inspection.inspection_number[:8]}",
        status="REVIEWED",
        recipient_role="manufacturer",
        recipient_name="Acme Foods Pvt Ltd",
        recipient_address="Delhi",
        statutory_charges=[],
        legal_version_context={},
        evidence_references=[],
    )
    db_session.add(notice)
    db_session.commit()

    # Inspector attempts to issue notice -> 403 Forbidden (requires NOTICE_ISSUE)
    resp = client.post(
        f"/api/v1/notices/{notice.id}/issue",
        headers=auth_headers(insp1),
        json={"officer_notes": "Attempt by inspector"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_notice_issue_rejects_client_officer_identity_spoofing(
    client: TestClient, test_users: dict, db_session: Session
):
    supervisor = test_users["supervisor"]

    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="COMPLETED",
        inspector_id=supervisor.id,
    )
    db_session.add(inspection)
    db_session.commit()

    notice = Notice(
        inspection_id=inspection.id,
        notice_reference=f"SCN-2026-{inspection.inspection_number[:8]}",
        status="REVIEWED",
        recipient_role="manufacturer",
        recipient_name="Acme Foods Pvt Ltd",
        recipient_address="Delhi",
        statutory_charges=[],
        legal_version_context={},
        evidence_references=[],
    )
    db_session.add(notice)
    db_session.commit()

    # Client attempts to spoof officer identity by sending forbidden fields in NoticeIssueRequest
    resp = client.post(
        f"/api/v1/notices/{notice.id}/issue",
        headers=auth_headers(supervisor),
        json={
            "officer_notes": "Attempting issuance with spoofed identity",
            "officer_name": "Spoofed False Officer",
            "officer_designation": "Imposter Director",
            "officer_office": "Fake Directorate",
        },
    )
    # Pydantic extra='forbid' must reject extra fields with 422 Unprocessable Entity
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Verify notice was NOT issued
    db_session.refresh(notice)
    assert notice.status == "REVIEWED"
    assert notice.is_immutable is False
    assert notice.officer_name is None


def test_notice_issue_admin_also_bound_authoritatively(
    client: TestClient, test_users: dict, db_session: Session
):
    admin = test_users["admin"]

    inspection = Inspection(
        inspection_number=f"INSP-{uuid4().hex[:8].upper()}",
        status="COMPLETED",
        inspector_id=admin.id,
    )
    db_session.add(inspection)
    db_session.commit()

    notice = Notice(
        inspection_id=inspection.id,
        notice_reference=f"SCN-2026-{inspection.inspection_number[:8]}",
        status="REVIEWED",
        recipient_role="manufacturer",
        recipient_name="Acme Foods Pvt Ltd",
        recipient_address="Delhi",
        statutory_charges=[],
        legal_version_context={},
        evidence_references=[],
    )
    db_session.add(notice)
    db_session.commit()

    # Admin issues notice - must bind admin's authenticated user identity
    resp = client.post(
        f"/api/v1/notices/{notice.id}/issue",
        headers=auth_headers(admin),
        json={"officer_notes": "Formal admin issuance"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["status"] == "ISSUED_BY_OFFICER"
    assert data["is_immutable"] is True
    assert data["issuing_officer_id"] == admin.id
    assert data["officer_name"] == admin.full_name
    assert data["officer_designation"] == admin.designation
    assert data["officer_office"] == admin.jurisdiction_office


# =========================================================================
# 5. Public Consumer Endpoints & Health (Anonymous Access)
# =========================================================================

def test_public_consumer_endpoints_without_auth(client: TestClient):
    # Consumer products
    resp = client.get("/api/v1/consumer/products")
    assert resp.status_code == status.HTTP_200_OK

    # Health
    resp = client.get("/api/v1/health")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "ok"


# =========================================================================
# 6. Admin User Management
# =========================================================================

def test_admin_create_user(client: TestClient, test_users: dict):
    admin = test_users["admin"]
    unique_suffix = uuid4().hex[:6]
    unique_email = f"new.officer.{unique_suffix}@praman.gov.in"
    unique_badge = f"DL-LM-{unique_suffix.upper()}"
    new_user_payload = {
        "email": unique_email,
        "password": "ValidOfficerPass123!@#",
        "full_name": "Officer Neha Gupta",
        "role": "LEGAL_METROLOGY_INSPECTOR",
        "designation": "Assistant Controller",
        "jurisdiction_office": "Delhi East",
        "badge_number": unique_badge,
    }

    resp = client.post("/api/v1/users", headers=auth_headers(admin), json=new_user_payload)
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["email"] == unique_email
    assert "password" not in data
    assert "hashed_password" not in data


def test_non_admin_cannot_create_user(client: TestClient, test_users: dict):
    insp1 = test_users["inspector1"]
    resp = client.post(
        "/api/v1/users",
        headers=auth_headers(insp1),
        json={"email": "bad@praman.gov.in", "password": "ValidPass123!@#", "role": "ADMIN"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_admin_bootstrap_idempotent(db_session: Session):
    # Run bootstrap
    admin1 = bootstrap_initial_admin(db_session)
    assert admin1 is not None

    # Run bootstrap again -> returns existing admin without modifying
    admin2 = bootstrap_initial_admin(db_session)
    assert admin2.id == admin1.id
