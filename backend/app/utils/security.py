"""
Security helpers for API authentication and safe error responses.
"""

import re
from typing import Any

import httpx
from cachetools import TTLCache
from flask import jsonify

from ..config import Config


# Bounded cache for validated PocketBase Bearer tokens.
# The previous implementation was an unbounded dict — an attacker (or a
# buggy client) could grow it indefinitely by hitting /api/* with many
# distinct tokens, eventually exhausting the container memory.
# 10k slots × 300 s TTL absorbs realistic load while capping worst-case
# footprint to a few MB. Evictions happen automatically on access.
_PB_TOKEN_CACHE: "TTLCache[str, bool]" = TTLCache(maxsize=10000, ttl=300)
_STORAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def error_response(message: str, status_code: int = 500, **extra: Any):
    """Return a public error response without leaking tracebacks in production."""
    payload = {
        "success": False,
        "error": message,
    }
    payload.update(extra)
    return jsonify(payload), status_code


def _validate_static_token(token: str) -> bool:
    expected = Config.API_AUTH_TOKEN
    return bool(expected) and token == expected


def _validate_pocketbase_token(token: str) -> bool:
    if token in _PB_TOKEN_CACHE:
        return True

    pb_url = (Config.POCKETBASE_URL or "").rstrip("/")
    if not pb_url:
        return False

    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(
                f"{pb_url}/api/collections/users/auth-refresh",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code == 200:
            _PB_TOKEN_CACHE[token] = True
            return True
    except httpx.HTTPError:
        return False

    return False


def validate_bearer_token(auth_header: str) -> bool:
    if not auth_header or not auth_header.startswith("Bearer "):
        return False

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return False

    return _validate_static_token(token) or _validate_pocketbase_token(token)


def validate_storage_id(value: str, *allowed_prefixes: str) -> str:
    """Reject path traversal and unexpected storage identifiers."""
    if not isinstance(value, str) or not _STORAGE_ID_RE.fullmatch(value):
        raise ValueError("Identificador no válido")
    if allowed_prefixes and not any(value.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError("Identificador no válido")
    return value


def validate_platform(value: str, allowed=("reddit", "twitter", "parallel")) -> str:
    if value not in allowed:
        raise ValueError("Plataforma no válida")
    return value
