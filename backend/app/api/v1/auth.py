from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import (
    create_access_token,
    get_client_ip,
    redact_sensitive_keys,
    verify_password,
)
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutResponse, TokenResponse, UserProfileRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    email_clean = payload.email.strip().lower()
    client_ip = get_client_ip(request)

    user = db.scalars(select(User).where(User.email == email_clean)).first()
    now = datetime.now(timezone.utc)

    if not user:
        # Audit log failed attempt for unknown user
        audit = AuditLog(
            user_id=None,
            event_type="AUTH_LOGIN_FAILED",
            resource_type="auth",
            resource_id=None,
            ip_address=client_ip,
            details=redact_sensitive_keys({"email": email_clean, "reason": "User not found"}),
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        audit = AuditLog(
            user_id=user.id,
            event_type="AUTH_LOGIN_FAILED",
            resource_type="auth",
            resource_id=user.id,
            ip_address=client_ip,
            details=redact_sensitive_keys({"email": email_clean, "reason": "Account inactive"}),
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Check lockout
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until:
            remaining = int((locked_until - now).total_seconds() / 60) + 1
        audit = AuditLog(
            user_id=user.id,
            event_type="AUTH_LOGIN_FAILED",
            resource_type="auth",
            resource_id=user.id,
            ip_address=client_ip,
            details=redact_sensitive_keys({"email": email_clean, "reason": "Account locked"}),
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Account is temporarily locked due to excessive failed attempts. Try again in {remaining} minutes.",
        )

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)

        audit = AuditLog(
            user_id=user.id,
            event_type="AUTH_LOGIN_FAILED",
            resource_type="auth",
            resource_id=user.id,
            ip_address=client_ip,
            details=redact_sensitive_keys(
                {
                    "email": email_clean,
                    "failed_attempts": user.failed_login_attempts,
                    "locked": user.locked_until is not None,
                }
            ),
        )
        db.add(audit)
        db.commit()

        if user.failed_login_attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is temporarily locked due to 5 failed login attempts. Try again in 15 minutes.",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Login success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    audit = AuditLog(
        user_id=user.id,
        event_type="AUTH_LOGIN_SUCCESS",
        resource_type="auth",
        resource_id=user.id,
        ip_address=client_ip,
        details=redact_sensitive_keys({"email": email_clean, "role": user.role}),
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    expires_minutes = settings.access_token_expire_minutes
    token = create_access_token(
        subject=user.id,
        email=user.email,
        role=user.role,
        expires_delta=timedelta(minutes=expires_minutes),
    )

    user_perms = sorted([p.value for p in ROLE_PERMISSIONS.get(user.role, set())])

    profile = UserProfileRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        designation=user.designation,
        jurisdiction_office=user.jurisdiction_office,
        badge_number=user.badge_number,
        is_active=user.is_active,
        permissions=user_perms,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
        user=profile,
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    client_ip = get_client_ip(request)
    audit = AuditLog(
        user_id=current_user.id,
        event_type="AUTH_LOGOUT",
        resource_type="auth",
        resource_id=current_user.id,
        ip_address=client_ip,
        details=redact_sensitive_keys({"email": current_user.email, "role": current_user.role}),
    )
    db.add(audit)
    db.commit()

    return LogoutResponse(
        message="Session terminated successfully. Client token purged. (Note: Existing stateless token expires automatically per expiration timestamp)."
    )


@router.get("/me", response_model=UserProfileRead)
def get_me(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    user_perms = sorted([p.value for p in ROLE_PERMISSIONS.get(current_user.role, set())])
    return UserProfileRead(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        designation=current_user.designation,
        jurisdiction_office=current_user.jurisdiction_office,
        badge_number=current_user.badge_number,
        is_active=current_user.is_active,
        permissions=user_perms,
    )
