"""
Exportación de la copia de seguridad (ver `services/backup_export.py`).

Credencial propia y de solo lectura: `BACKUP_TOKEN`, en la cabecera `X-Backup-Token`. No es la clave de administrador
ni un usuario de PocketBase, y no vale para ninguna otra ruta. Sin `BACKUP_TOKEN` (o de menos de 32 caracteres) la
ruta no existe: responde 404 y no revela que hay una copia posible.
"""

import hmac
import os
import tempfile
import threading
from datetime import datetime, timezone

from flask import Response, request

from . import backup_bp
from ..config import Config
from ..services import backup_export
from ..utils.logger import get_logger

logger = get_logger('mirofish.api.backup')

BACKUP_HEADER = 'X-Backup-Token'
BACKUP_PATH = '/api/backup/export'
MIN_TOKEN_CHARS = 32

# Una copia a la vez: empaquetar lee todo el disco y comprime; dos a la vez no aportan nada y gastan CPU
_export_lock = threading.Lock()


def backup_enabled() -> bool:
    return len(Config.BACKUP_TOKEN or '') >= MIN_TOKEN_CHARS


def check_backup_token():
    """None si la petición lleva el token correcto; si no, la respuesta de error. Comparación en tiempo constante."""
    if not backup_enabled():
        return {"success": False, "error": "Not found"}, 404
    given = request.headers.get(BACKUP_HEADER, '')
    if not given or not hmac.compare_digest(given.encode(), Config.BACKUP_TOKEN.encode()):
        logger.warning(f"[copia] Token de copia incorrecto o ausente desde {request.remote_addr}")
        return {"success": False, "error": "No autorizado"}, 401
    return None


@backup_bp.route('/export', methods=['GET'])
def export_backup():
    denied = check_backup_token()               # también lo comprueba el hook de la app: dos puertas
    if denied is not None:
        return denied
    if not _export_lock.acquire(blocking=False):
        return {"success": False, "error": "Ya hay una copia en curso"}, 429
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix='simuloo-backup-', suffix='.tar.gz')
        os.close(fd)
        manifest = backup_export.build_backup(tmp_path)
        size = os.path.getsize(tmp_path)
        sha, _ = backup_export._sha256_and_size(tmp_path)
        logger.info(f"[copia] Exportada: {manifest['proyectos']} proyectos, {manifest['ficheros']} ficheros, "
                    f"{size} bytes comprimidos, {len(manifest['omitidos'])} omitidos")
    except Exception as exc:                    # noqa: BLE001
        logger.error(f"[copia] Falló la exportación: {type(exc).__name__}: {exc}")
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        _export_lock.release()
        return {"success": False, "error": "No se pudo crear la copia"}, 500

    def stream():
        try:
            with open(tmp_path, 'rb') as f:
                for block in iter(lambda: f.read(backup_export.CHUNK), b''):
                    yield block
        finally:
            try:
                os.unlink(tmp_path)
            finally:
                _export_lock.release()

    name = f"simuloo-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.tar.gz"
    return Response(stream(), mimetype='application/gzip', headers={
        'Content-Disposition': f'attachment; filename="{name}"',
        'Content-Length': str(size),
        'X-Backup-Sha256': sha,
        'X-Backup-Projects': str(manifest['proyectos']),
        'X-Backup-Files': str(manifest['ficheros']),
        'Cache-Control': 'no-store',
    })
