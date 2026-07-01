"""Security primitives: password hashing (passlib/bcrypt) and JWT (python-jose).

Kept stateless — no I/O, no DB — so it can be imported safely anywhere
(schemas, deps, services) without circular import risk.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import Config

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str | int, *, extra_claims: dict[str, Any] | None = None
) -> str:
    """Issue a signed JWT for the given subject (user id/email).

    `extra_claims` lets callers embed e.g. roles/permissions for stateless
    authorization decisions. Expiry is taken from Config (default 24h).
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    """Verify + decode a JWT. Raises jose.JWTError on bad/expired tokens."""
    return jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALG])


# Re-export so callers don't need a separate import.
__all__ = ["JWTError", "hash_password", "verify_password", "create_access_token", "decode_token"]
