"""
Exportador de copias de seguridad: un `.tar.gz` coherente con todo lo que Simuloo guarda en disco.

Por qué existe: el servidor de producción no se puede alcanzar por SSH desde fuera, así que una copia «empujada»
desde allí no es posible; la app ofrece lo suyo por HTTPS a una credencial propia de SOLO LECTURA (`BACKUP_TOKEN`) y
otra máquina (el Mac mini) lo recoge cada noche y lo deja en el NAS. Ver `api/backup.py` y `ops/backup_remoto.sh`.

Qué incluye: todo `uploads/` (proyectos con sus documentos originales, simulaciones, informes) más un
`MANIFIESTO.json` con el tamaño y el sha256 de cada fichero. NO incluye el grafo de Neo4j: se reconstruye desde los
documentos originales (que sí van) y su volcado en caliente no existe en Neo4j Community (ver `ops/backup.sh --grafo`).

Coherencia:
- Los JSON se escriben de forma atómica (`utils/fs.py`), así que cada archivo se copia entero o no cambia.
- Las bases SQLite de OASIS se copian con la API de respaldo de SQLite (una instantánea coherente aunque la
  simulación esté escribiendo), no con una copia de bytes.
- Se saltan los temporales de escritura atómica (`.xxxx.tmp`) y las carpetas IPC (órdenes en tránsito).
"""

import hashlib
import json
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.backup')

MANIFEST_NAME = 'MANIFIESTO.json'
SKIP_DIRS = {'ipc_commands', 'ipc_responses', '__pycache__'}
SQLITE_SUFFIXES = ('.db', '.sqlite', '.sqlite3')
SQLITE_SIDE_FILES = ('-wal', '-shm', '-journal')
CHUNK = 1024 * 1024


def _is_temp(name: str) -> bool:
    return name.startswith('.') and name.endswith('.tmp')


def _iter_files(root: str):
    """(ruta absoluta, ruta relativa) de cada fichero a copiar, en orden estable."""
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if _is_temp(name) or name.endswith(SQLITE_SIDE_FILES):
                continue
            path = os.path.join(current, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            yield path, os.path.relpath(path, root)


def _sqlite_snapshot(src: str, tmp_dir: str) -> str:
    """Copia coherente de una base SQLite con la API de respaldo. Lanza sqlite3.Error si no se puede."""
    dst = os.path.join(tmp_dir, 'snapshot.db')
    if os.path.exists(dst):
        os.unlink(dst)
    source = sqlite3.connect(f'file:{src}?mode=ro', uri=True, timeout=10)
    try:
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return dst


def _sha256_and_size(path: str) -> Tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _count_children(root: str, sub: str) -> int:
    path = os.path.join(root, sub)
    try:
        return sum(1 for n in os.listdir(path) if not n.startswith('.'))
    except OSError:
        return 0


def build_backup(dest_path: str, root: str = None) -> Dict:
    """
    Escribe el `.tar.gz` en `dest_path` y devuelve el manifiesto (el mismo que va dentro).
    Un fichero que desaparece mientras se copia (se borró un proyecto) se anota en `omitidos`; no aborta la copia.
    """
    root = os.path.abspath(root or Config.UPLOAD_FOLDER)
    entries: List[Dict] = []
    skipped: List[Dict] = []
    with tempfile.TemporaryDirectory(prefix='backup-') as tmp_dir, \
            tarfile.open(dest_path, 'w:gz', compresslevel=6) as tar:
        for path, rel in _iter_files(root):
            source, note = path, None
            try:
                if rel.lower().endswith(SQLITE_SUFFIXES):
                    try:
                        source = _sqlite_snapshot(path, tmp_dir)
                        note = 'sqlite-snapshot'
                    except sqlite3.Error as exc:                       # base rota o bloqueada: copia de bytes, avisada
                        note = f'sqlite-copia-de-bytes ({type(exc).__name__})'
                        logger.warning(f"[copia] {rel}: no se pudo hacer la instantánea SQLite ({exc}); se copia tal cual")
                sha, size = _sha256_and_size(source)
                info = tar.gettarinfo(source, arcname=rel)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with open(source, 'rb') as f:
                    tar.addfile(info, f)
                entry = {'path': rel, 'size': size, 'sha256': sha}
                if note:
                    entry['nota'] = note
                entries.append(entry)
            except FileNotFoundError:
                skipped.append({'path': rel, 'motivo': 'desapareció durante la copia'})
            except OSError as exc:
                skipped.append({'path': rel, 'motivo': f'{type(exc).__name__}'})
                logger.warning(f"[copia] No se pudo copiar {rel}: {exc}")

        manifest = {
            'formato': 1,
            'creada': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'proyectos': _count_children(root, 'projects'),
            'simulaciones': _count_children(root, 'simulations'),
            'informes': _count_children(root, 'reports'),
            'ficheros': len(entries),
            'bytes': sum(e['size'] for e in entries),
            'omitidos': skipped,
            'archivos': entries,
        }
        data = json.dumps(manifest, ensure_ascii=False, indent=1).encode('utf-8')
        info = tarfile.TarInfo(MANIFEST_NAME)
        info.size = len(data)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        import io
        tar.addfile(info, io.BytesIO(data))
    return manifest
