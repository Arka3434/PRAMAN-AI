import time
import jwt
import pytest
from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    extract_client_ip,
    get_password_hash,
    is_password_usable,
    redact_sensitive_data,
    UNUSABLE_PASSWORD_PREFIX,
    validate_password_complexity,
    verify_password,
)


def test_password_hashing_and_verification():
    raw_pwd = "SecurePassword123!@#"
    hashed = get_password_hash(raw_pwd)
    assert hashed != raw_pwd
    assert hashed.startswith("$2b$12$")  # bcrypt work factor 12
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword123!@#", hashed) is False


def test_password_complexity():
    # Valid
    validate_password_complexity("ValidPass123!@#")

    # Too short
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password_complexity("Short1!Aa")

    # Missing uppercase
    with pytest.raises(ValueError, match="uppercase"):
        validate_password_complexity("lowercase123!@#")

    # Missing lowercase
    with pytest.raises(ValueError, match="lowercase"):
        validate_password_complexity("UPPERCASE123!@#")

    # Missing digit
    with pytest.raises(ValueError, match="digit"):
        validate_password_complexity("NoDigitsHere!@#")

    # Missing special character
    with pytest.raises(ValueError, match="special character"):
        validate_password_complexity("NoSpecialChars123")

    # Common/trivial passwords
    with pytest.raises(ValueError, match="common or trivial"):
        validate_password_complexity("Password123456!@#")


def test_unusable_password_sentinel():
    sentinel = f"{UNUSABLE_PASSWORD_PREFIX}legacy_import_unusable"
    assert is_password_usable(sentinel) is False
    assert verify_password("AnyPassword123!", sentinel) is False

    usable_hash = get_password_hash("ValidPass123!@#")
    assert is_password_usable(usable_hash) is True


def test_jwt_generation_and_decoding():
    token = create_access_token(
        subject="user-123",
        role="ADMIN",
        expires_delta=60,
    )
    assert token is not None
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "ADMIN"
    assert "exp" in payload


def test_expired_jwt_rejected():
    # Token expired 10 seconds ago
    token = create_access_token(
        subject="user-456",
        role="LEGAL_METROLOGY_INSPECTOR",
        expires_delta=-10,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_invalid_jwt_rejected():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("invalid.jwt.token")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("")



def test_production_missing_jwt_secret_fails():
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be explicitly configured"):
        Settings(
            app_env="production",
            jwt_secret_key=None,
        )

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be explicitly configured"):
        Settings(
            app_env="staging",
            jwt_secret_key=None,
        )


def test_audit_sensitive_data_redaction():
    unredacted = {
        "user": "officer@praman.gov.in",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "nested": {
            "token": "secret-token-abc",
            "safe_field": 42,
            "secret_key": "raw-key",
            "hashed_password": "$2b$12$...",
        },
        "items": [
            {"authorization": "Bearer token", "name": "item1"},
        ],
    }

    redacted = redact_sensitive_data(unredacted)
    assert redacted["password"] == "[REDACTED]"
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["nested"]["secret_key"] == "[REDACTED]"
    assert redacted["nested"]["hashed_password"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == 42
    assert redacted["items"][0]["authorization"] == "[REDACTED]"
    assert redacted["items"][0]["name"] == "item1"


def test_trusted_proxy_ip_extraction():
    # Direct connection from untrusted client
    ip = extract_client_ip(
        client_host="203.0.113.195",
        x_forwarded_for="198.51.100.10, 203.0.113.195",
        trusted_proxies=["127.0.0.1", "10.0.0.1"],
    )
    # Since client_host is not in trusted_proxies, X-Forwarded-For must NOT be trusted
    assert ip == "203.0.113.195"

    # Connection through trusted proxy
    ip = extract_client_ip(
        client_host="10.0.0.1",
        x_forwarded_for="198.51.100.10, 10.0.0.1",
        trusted_proxies=["127.0.0.1", "10.0.0.1"],
    )
    # Since client_host IS in trusted_proxies, X-Forwarded-For can be trusted
    assert ip == "198.51.100.10"
