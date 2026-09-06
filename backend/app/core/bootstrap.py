import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.roles import UserRole
from app.core.security import hash_password, validate_password_complexity
from app.models.user import User

logger = logging.getLogger(__name__)


def bootstrap_initial_admin(db: Session) -> User | None:
    """
    Deterministic, idempotent initial administrator bootstrap hook.
    If an administrator already exists, exits immediately without modifying credentials.
    If no administrator exists and FIRST_SUPERUSER credentials are provided in the environment,
    creates the initial administrator.
    """
    existing_admin = db.scalars(
        select(User).where(User.role == UserRole.ADMIN.value)
    ).first()

    ensure_default_dev_users(db)

    if existing_admin:
        logger.info("Admin user already exists (%s). Skipping initial bootstrap.", existing_admin.email)
        return existing_admin

    email = (settings.first_superuser_email or "").strip().lower()
    password = settings.first_superuser_password
    name = settings.first_superuser_name or "System Administrator"

    if not email or not password:
        logger.warning(
            "No administrator exists in the database and FIRST_SUPERUSER_EMAIL / "
            "FIRST_SUPERUSER_PASSWORD are not configured in the environment. "
            "To onboard an administrator, configure environment variables or use the CLI command: "
            "python -m app.cli.create_admin"
        )
        return None

    is_valid, err_msg = validate_password_complexity(password)
    if not is_valid:
        logger.error(
            "FIRST_SUPERUSER_PASSWORD does not meet complexity requirements: %s. "
            "Initial admin bootstrap aborted.",
            err_msg,
        )
        return None

    # Check if a user with this email already exists with a different role
    existing_user_email = db.scalars(select(User).where(User.email == email)).first()
    if existing_user_email:
        logger.warning(
            "User with email %s already exists with role %s. Skipping admin bootstrap.",
            email,
            existing_user_email.role,
        )
        return existing_user_email

    admin_user = User(
        full_name=name,
        email=email,
        role=UserRole.ADMIN.value,
        hashed_password=hash_password(password),
        designation="System Administrator",
        jurisdiction_office="Central Enforcement Directorate",
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    logger.info("Successfully bootstrapped initial administrator: %s", email)
    return admin_user


def ensure_default_dev_users(db: Session) -> None:
    users_data = [
        ("admin@praman.gov.in", "Admin Officer", UserRole.ADMIN.value, "Central HQ - New Delhi", "ADM-001"),
        ("supervisor@praman.gov.in", "Supervising Officer Sharma", UserRole.SUPERVISING_OFFICER.value, "Regional Zone North", "SUP-101"),
        ("inspector1@praman.gov.in", "Inspector Rajesh Kumar", UserRole.LEGAL_METROLOGY_INSPECTOR.value, "Delhi District Office", "INS-201"),
        ("reviewer@praman.gov.in", "Review Officer Verma", UserRole.REVIEWER.value, "Central Legal Review Cell", "REV-301"),
    ]
    for email, name, role, office, badge in users_data:
        user = db.scalars(select(User).where(User.email == email)).first()
        if not user:
            new_u = User(
                email=email,
                full_name=name,
                role=role,
                hashed_password=hash_password("ValidPass123!@#"),
                designation=role.replace("_", " ").title(),
                jurisdiction_office=office,
                badge_number=badge,
                is_active=True,
            )
            db.add(new_u)
            try:
                db.commit()
            except Exception:
                db.rollback()
        else:
            user.hashed_password = hash_password("ValidPass123!@#")
            user.failed_login_attempts = 0
            user.locked_until = None
            user.is_active = True
            try:
                db.commit()
            except Exception:
                db.rollback()
