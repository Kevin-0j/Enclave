"""Passwords (Argon2id), access tokens, stream tokens and refresh-token hashing."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

_hasher = PasswordHasher()  # argon2id, RFC 9106 low-memory profile defaults
# Verified against when the email is unknown, so response time does not reveal which emails exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def now() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    *, user_id: UUID, tenant_id: UUID | None, role: str | None, platform_admin: bool
) -> str:
    s = get_settings()
    issued = now()
    claims: dict[str, Any] = {
        "typ": "access",
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "role": role,
        "pa": platform_admin,
        "iat": issued,
        "exp": issued + timedelta(minutes=s.access_token_minutes),
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    claims: dict[str, Any] = jwt.decode(
        token,
        get_settings().jwt_secret.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "sub", "typ"]},
    )
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return claims


Variant = Literal["main", "sub"]


def create_stream_token(
    *, user_id: UUID, tenant_id: UUID, camera_id: UUID, variant: Variant
) -> tuple[str, datetime]:
    s = get_settings()
    issued = now()
    expires = issued + timedelta(seconds=s.stream_token_seconds)
    claims = {
        "typ": "stream",
        "sub": str(user_id),
        "tid": str(tenant_id),
        "cid": str(camera_id),
        "var": variant,
        "act": "read",
        "iat": issued,
        "exp": expires,
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, s.stream_token_secret.get_secret_value(), algorithm=ALGORITHM), expires


def decode_stream_token(token: str) -> dict[str, Any]:
    claims: dict[str, Any] = jwt.decode(
        token,
        get_settings().stream_token_secret.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "tid", "cid", "var", "act", "typ"]},
    )
    if claims.get("typ") != "stream":
        raise jwt.InvalidTokenError("wrong token type")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    pepper = get_settings().refresh_pepper.get_secret_value().encode()
    return hmac.new(pepper, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
