from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, require_permission
from app.core.permissions import Permission
from app.core.security import UNUSABLE_PASSWORD_PREFIX, get_password_hash, validate_password_complexity
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.users import UserCreate, UserRead

router = APIRouter(prefix='/api/v1/users', tags=['users'])


@router.get('', response_model=list[UserRead])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_READ)),
) -> list[User]:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return users


@router.post('', response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_MANAGE)),
) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{payload.email}' already exists",
        )

    if payload.password:
        try:
            validate_password_complexity(payload.password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        hashed_pwd = get_password_hash(payload.password)
    else:
        hashed_pwd = f"{UNUSABLE_PASSWORD_PREFIX}unusable_no_password_set"

    data = payload.model_dump(exclude={"password"})
    data["email"] = payload.email.lower().strip()
    data["hashed_password"] = hashed_pwd

    user = User(**data)
    db.add(user)
    db.commit()
    db.refresh(user)

    audit = AuditLog(
        event_type="USER_CREATED",
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email, "role": user.role.value if hasattr(user.role, 'value') else str(user.role)},
    )
    db.add(audit)
    db.commit()

    return user


@router.get('/{user_id}', response_model=UserRead)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.USERS_READ)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')
    return user

