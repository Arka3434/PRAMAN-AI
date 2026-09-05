from __future__ import annotations

import pytest
from sqlalchemy import select
from app.main import app
from app.api.deps import get_current_user, get_current_active_user
from app.core.roles import UserRole
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


@pytest.fixture(autouse=True)
def auto_auth_for_legacy_tests(request):
    """
    Autouse fixture that provides authentication for legacy test suites (Phases 0-14).
    For Phase 15 auth tests (test_auth_*.py), this fixture does nothing, ensuring
    real token and security logic is strictly validated.
    """
    if "test_auth" in request.module.__name__:
        yield
        return

    # For legacy tests, provide a valid default supervising officer
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "test.officer@praman.gov.in")).first()
        if not user:
            user = User(
                email="test.officer@praman.gov.in",
                hashed_password=get_password_hash("ValidOfficerPass123!@#"),
                full_name="Default Test Officer",
                role=UserRole.ADMIN.value,
                designation="Chief Administrator",
                jurisdiction_office="Central HQ",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    def _mock_authenticated_user():
        with SessionLocal() as session:
            u = session.scalars(select(User).where(User.email == "test.officer@praman.gov.in")).first()
            if not u:
                user = User(
                    email="test.officer@praman.gov.in",
                    hashed_password=get_password_hash("ValidOfficerPass123!@#"),
                    full_name="Default Test Officer",
                    role=UserRole.ADMIN.value,
                    designation="Chief Administrator",
                    jurisdiction_office="Central HQ",
                    is_active=True,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                u = user
            return u

    app.dependency_overrides[get_current_user] = _mock_authenticated_user
    app.dependency_overrides[get_current_active_user] = _mock_authenticated_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_active_user, None)
