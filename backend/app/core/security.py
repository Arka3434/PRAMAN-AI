import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import Request

from app.core.config import settings

UNUSABLE_PASSWORD_PREFIX = "!unusable$"

COMMON_WEAK_PASSWORDS = {
    "password1234",
    "admin12345678",
    "password@123",
    "welcome12345",
    "administrator",
    "qwerty123456",
    "letmein12345",
}

REDACTED_KEYS = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "authorization",
    "secret",
    "secret_key",
}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


get_password_hash = hash_password


def is_password_usable(hashed_password: str | None) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith(UNUSABLE_PASSWORD_PREFIX) or hashed_password.startswith("!"):
        return False
    return True


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not is_password_usable(hashed_password):
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def validate_password_complexity(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit or number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\/`~]", password):
        raise ValueError("Password must contain at least one special character.")
    if password.lower() in COMMON_WEAK_PASSWORDS or any(p in password.lower() for p in ("password", "admin", "123456")):
        raise ValueError("Password is too common or trivial.")


def create_access_token(
    subject: str,
    *args: Any,
    role: str | None = None,
    email: str | None = None,
    expires_delta: timedelta | int | float | None = None,
    **kwargs: Any,
) -> str:
    for a in args:
        if isinstance(a, str):
            if "@" in a:
                email = a
            else:
                role = a
        elif isinstance(a, (timedelta, int, float)):
            expires_delta = a

    if "role" in kwargs and kwargs["role"]:
        role = kwargs["role"]
    if "email" in kwargs and kwargs["email"]:
        email = kwargs["email"]
    if "expires_delta" in kwargs:
        expires_delta = kwargs["expires_delta"]

    role = role or "LEGAL_METROLOGY_INSPECTOR"
    now = datetime.now(timezone.utc)
    if isinstance(expires_delta, (int, float)):
        expire = now + timedelta(minutes=float(expires_delta))
    elif isinstance(expires_delta, timedelta):
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, settings.effective_jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not token or not isinstance(token, str):
        raise jwt.InvalidTokenError("Token is empty or invalid")
    return jwt.decode(
        token,
        settings.effective_jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


def extract_client_ip(
    client_host: str,
    x_forwarded_for: str | None = None,
    trusted_proxies: list[str] | None = None,
) -> str:
    proxies = trusted_proxies if trusted_proxies is not None else settings.trusted_proxies
    if client_host in proxies and x_forwarded_for:
        first_ip = x_forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    return client_host


def get_client_ip(request: Request, trusted_proxies: list[str] | None = None) -> str:
    client_host = request.client.host if request.client else "unknown"
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    return extract_client_ip(client_host, x_forwarded_for, trusted_proxies)


def redact_sensitive_keys(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in REDACTED_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_sensitive_keys(v)
        return sanitized
    if isinstance(data, list):
        return [redact_sensitive_keys(item) for item in data]
    return data


redact_sensitive_data = redact_sensitive_keys
