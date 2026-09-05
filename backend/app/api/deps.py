from datetime import datetime, timezone
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import Permission, ROLE_PERMISSIONS
from app.core.roles import UserRole
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.inspection import Inspection
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Bearer token missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is temporarily locked due to excessive failed attempts. Try again in {remaining} minutes.",
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_permission(permission: Permission) -> Callable[[User], User]:
    def _checker(current_user: User = Depends(get_current_active_user)) -> User:
        allowed_perms = ROLE_PERMISSIONS.get(current_user.role, set())
        if permission not in allowed_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: permission '{permission.value}' required for role '{current_user.role}'",
            )
        return current_user

    return _checker


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed_values = {r.value for r in roles}

    def _checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role must be one of {sorted(allowed_values)}",
            )
        return current_user

    return _checker


def check_inspection_ownership(
    inspection_id: str,
    current_user: User,
    db: Session,
    require_write: bool = False,
) -> Inspection:
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection not found: {inspection_id}",
        )

    if require_write:
        if current_user.role == UserRole.SUPERVISING_OFFICER.value:
            return inspection

        if current_user.role == UserRole.LEGAL_METROLOGY_INSPECTOR.value:
            if inspection.inspector_id == current_user.id:
                return inspection
            if inspection.inspector_id is None:
                # Auto-claim unassigned inspection
                inspection.inspector_id = current_user.id
                db.flush()
                return inspection
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify an inspection assigned to another officer",
            )

        if current_user.role == UserRole.ADMIN.value:
            return inspection

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to modify this inspection",
        )

    return inspection
