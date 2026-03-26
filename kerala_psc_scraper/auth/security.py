import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from kerala_psc_scraper.config.auth_settings import (
    JWT_ACCESS_SECRET,
    JWT_ACCESS_TTL_SECONDS,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_REFRESH_SECRET,
    JWT_REFRESH_TTL_SECONDS,
)

_password_hasher = PasswordHasher()


def validate_password_strength(password: str) -> bool:
    if len(password) < 12 or len(password) > 128:
        return False
    checks = [r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"]
    return all(re.search(pattern, password) for pattern in checks)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _encode(payload: dict[str, Any], secret: str) -> str:
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str, email: str, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=JWT_ACCESS_TTL_SECONDS)).timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return _encode(payload, JWT_ACCESS_SECRET)


def create_refresh_token(user_id: str, jti: str | None = None) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    token_jti = jti or str(uuid.uuid4())
    expires_at = now + timedelta(seconds=JWT_REFRESH_TTL_SECONDS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": token_jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return _encode(payload, JWT_REFRESH_SECRET), token_jti, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, JWT_ACCESS_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER, audience=JWT_AUDIENCE)
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM], issuer=JWT_ISSUER, audience=JWT_AUDIENCE)
    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


def generate_secure_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
