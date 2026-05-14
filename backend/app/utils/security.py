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


# Cap user-supplied text fields that ultimately reach the LLM (or our
# storage layer). The values are forwarded verbatim into prompts, so:
# - oversize inputs waste tokens and money on every call
# - control characters can confuse downstream tooling or be used to
#   smuggle delimiters / fake markdown into the prompt
# A blunt strip is enough; full anti-prompt-injection defence belongs in
# the prompt template itself.
_USER_TEXT_MAX_CHARS = 10_000
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_user_text(value: str, *, max_chars: int = _USER_TEXT_MAX_CHARS, field: str = "input") -> str:
    """Clamp length and strip control characters from a user-provided string.

    Tabs (0x09), newlines (0x0a) and CR (0x0d) are preserved so multi-line
    inputs keep formatting. Everything else in the C0/DEL range is removed.
    """
    if not isinstance(value, str):
        raise ValueError(f"{field} debe ser texto")
    if len(value) > max_chars:
        raise ValueError(f"{field} excede el máximo de {max_chars} caracteres")
    return _CONTROL_CHARS_RE.sub("", value)


# Magic-byte signatures for the binary file types Mirror accepts as uploads.
# Validating by content (not just extension) prevents an authenticated user
# from disguising arbitrary payloads as PDFs/images and feeding them to the
# parsers (PyMuPDF, Pillow), which historically have had CVEs reachable via
# malformed inputs.
_BINARY_MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "webp": [b"RIFF"],  # WEBP has RIFF....WEBP; full check below.
}
_TEXT_EXTENSIONS = {"md", "markdown", "txt"}


def validate_upload_content(file_storage, extension: str) -> None:
    """Raise ValueError unless `file_storage` content matches `extension`.

    Always re-seeks the stream to position 0 before returning so the caller
    can continue reading/saving the file as if nothing happened.
    """
    if not extension:
        raise ValueError("Archivo sin extensión")

    extension = extension.lower().lstrip(".")

    # Read enough bytes for the longest signature plus the WEBP suffix.
    head = file_storage.stream.read(16)
    try:
        file_storage.stream.seek(0)
    except (OSError, ValueError):
        # Some streams cannot seek; refuse the upload rather than risk a
        # half-read file reaching the parser.
        raise ValueError("Archivo no es legible (stream no rebobinable)")

    if extension in _TEXT_EXTENSIONS:
        # Reject binaries dressed up as text (NUL bytes in the first 16 bytes
        # are a strong indicator). Otherwise accept; full text validation is
        # out of scope and the downstream parser tolerates encoding noise.
        if b"\x00" in head:
            raise ValueError(f"Contenido binario en archivo .{extension}")
        return

    signatures = _BINARY_MAGIC_SIGNATURES.get(extension)
    if not signatures:
        raise ValueError(f"Extensión .{extension} no soportada")

    if extension == "webp":
        # WEBP: RIFF at byte 0, "WEBP" at bytes 8..11.
        if not (head.startswith(b"RIFF") and head[8:12] == b"WEBP"):
            raise ValueError("Archivo no es un WebP válido")
        return

    if not any(head.startswith(sig) for sig in signatures):
        raise ValueError(f"El contenido del archivo no coincide con la extensión .{extension}")
