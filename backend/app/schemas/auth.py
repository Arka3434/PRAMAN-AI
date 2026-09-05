from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfileRead(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    designation: str | None = None
    jurisdiction_office: str | None = None
    badge_number: str | None = None
    is_active: bool = True
    permissions: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileRead


class LogoutResponse(BaseModel):
    message: str = "Session terminated successfully. Client token purged."
