"""
Security helpers for API authentication and safe error responses.
"""

import base64
import hmac
import json
import re
import secrets
from typing import Any, Mapping, Optional, Tuple

import httpx
from cachetools import TTLCache
from flask import jsonify

from ..config import Config


# Secreto interno del proceso. Lo usan los hilos del modo automático para
# llamar a las rutas de la API con `app.test_client()` sin token de usuario.
# Se genera al arrancar, vive solo en memoria: no sale del proceso, no se
# loguea y no se devuelve nunca al cliente. Cada arranque genera uno nuevo.
INTERNAL_AUTH_HEADER = "X-Simuloo-Internal"
_INTERNAL_TOKEN = secrets.token_urlsafe(32)


def internal_request_headers() -> dict:
    """Cabeceras que identifican una llamada interna del propio proceso."""
    return {INTERNAL_AUTH_HEADER: _INTERNAL_TOKEN}


def is_internal_request(headers: Mapping[str, str]) -> bool:
    """True si la petición lleva el secreto interno (comparación en tiempo constante)."""
    value = headers.get(INTERNAL_AUTH_HEADER, "") if headers else ""
    if not value:
        return False
    return hmac.compare_digest(value.encode(), _INTERNAL_TOKEN.encode())


# Bounded cache for validated PocketBase Bearer tokens.
# The previous implementation was an unbounded dict — an attacker (or a
# buggy client) could grow it indefinitely by hitting /api/* with many
# distinct tokens, eventually exhausting the container memory.
# 10k slots × 300 s TTL absorbs realistic load while capping worst-case
# footprint to a few MB. Evictions happen automatically on access.
_PB_TOKEN_CACHE: "TTLCache[str, str]" = TTLCache(maxsize=10000, ttl=300)   # token → id del usuario
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
    return bool(expected) and hmac.compare_digest(token.encode(), expected.encode())


def _jwt_claim(token: str, claim: str) -> Optional[str]:
    """Una reclamación del payload de un JWT, sin verificar la firma (PocketBase ya validó el token)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        value = json.loads(base64.urlsafe_b64decode(payload)).get(claim)
        return value if isinstance(value, str) and value else None
    except (IndexError, ValueError):
        return None


def _pocketbase_user_id(token: str) -> Optional[str]:
    """Id del usuario de PocketBase dueño del token, o None si no es un token válido."""
    if token in _PB_TOKEN_CACHE:
        return _PB_TOKEN_CACHE[token]

    pb_url = (Config.POCKETBASE_URL or "").rstrip("/")
    if not pb_url:
        return None

    try:
        with httpx.Client(timeout=8) as client:
            response = client.post(
                f"{pb_url}/api/collections/users/auth-refresh",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            return None
        try:
            body = response.json()
        except ValueError:
            body = {}
        record = (body.get("record") or body.get("user") or {}) if isinstance(body, dict) else {}
        user_id = record.get("id") if isinstance(record, dict) else None
        user_id = user_id if isinstance(user_id, str) and user_id else _jwt_claim(token, "id")
        if user_id:
            _PB_TOKEN_CACHE[token] = user_id
            return user_id
    except (httpx.HTTPError, httpx.InvalidURL):
        return None

    return None


def identify_bearer(auth_header: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Quién es el dueño de un `Authorization: Bearer …`:
    ("admin", None) si es la clave estática de emergencia, ("user", id) si es un usuario de PocketBase,
    None si no es válido.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None
    if _validate_static_token(token):
        return "admin", None
    user_id = _pocketbase_user_id(token)
    return ("user", user_id) if user_id else None


def validate_bearer_token(auth_header: str) -> bool:
    return identify_bearer(auth_header) is not None


def validate_storage_id(value: str, *allowed_prefixes: str) -> str:
    """Reject path traversal and unexpected storage identifiers."""
    if not isinstance(value, str) or not _STORAGE_ID_RE.fullmatch(value):
        raise ValueError("Identificador no válido")
    if allowed_prefixes and not any(value.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError("Identificador no válido")
    return value


def is_valid_storage_id(value: str, *allowed_prefixes: str) -> bool:
    """Versión booleana de validate_storage_id, para filtrar listados de disco
    (.DS_Store, duplicados de iCloud tipo 'proj_x 2', etc.)."""
    try:
        validate_storage_id(value, *allowed_prefixes)
        return True
    except ValueError:
        return False


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


# Magic-byte signatures for the binary file types Simuloo accepts as uploads.
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
