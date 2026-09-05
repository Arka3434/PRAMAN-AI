from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.roles import UserRole


class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    role: str = UserRole.LEGAL_METROLOGY_INSPECTOR.value
    designation: str | None = None
    jurisdiction_office: str | None = None
    badge_number: str | None = None
    is_active: bool = True

    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v: str) -> str:
        if isinstance(v, str):
            mapping = {
                'inspector': UserRole.LEGAL_METROLOGY_INSPECTOR.value,
                'supervisor': UserRole.SUPERVISING_OFFICER.value,
                'supervising_officer': UserRole.SUPERVISING_OFFICER.value,
                'admin': UserRole.ADMIN.value,
                'reviewer': UserRole.REVIEWER.value,
            }
            norm = mapping.get(v.strip().lower())
            if norm:
                return norm
            upper_val = v.strip().upper()
            if upper_val in [r.value for r in UserRole]:
                return upper_val
        return v


class UserCreate(UserBase):
    password: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
