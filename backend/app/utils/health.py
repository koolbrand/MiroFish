"""
Comprobaciones de «listo para trabajar» (`/health/ready`).

`/health` solo dice que Flask responde: con Neo4j caído o el disco lleno sigue diciendo «ok» mientras todo lo
que importa (grafo, simulaciones, informes) falla. Aquí se comprueba lo que la app necesita de verdad:

- Neo4j: conexión y autenticación (`verify_connectivity`), con plazo corto.
- Disco de `uploads/`: se puede escribir y queda espacio (un disco lleno corta guardados a medias).

El resultado se guarda unos segundos: quien sondee sin parar (un monitor, un balanceador) no abre una conexión
a Neo4j por cada visita. La respuesta solo lleva verdadero/falso, nunca direcciones, rutas ni mensajes de error.
"""

import os
import shutil
import tempfile
import threading
import time
from typing import Callable, Dict, Tuple

from ..config import Config
from .logger import get_logger

logger = get_logger('mirofish.health')

CACHE_SECONDS = 10.0
NEO4J_TIMEOUT_SECONDS = 3.0

_lock = threading.Lock()
_cached: Tuple[float, Dict[str, bool]] = (0.0, {})


def check_neo4j() -> bool:
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
            connection_timeout=NEO4J_TIMEOUT_SECONDS,
            max_transaction_retry_time=NEO4J_TIMEOUT_SECONDS,
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return True
    except Exception as exc:                                       # cualquier fallo = no listo
        logger.warning(f"[health] Neo4j no responde: {type(exc).__name__}")
        return False


def check_disk() -> bool:
    folder = os.path.abspath(Config.UPLOAD_FOLDER)
    try:
        os.makedirs(folder, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, prefix='.health-', suffix='.tmp') as probe:
            probe.write(b'ok')
            probe.flush()
            os.fsync(probe.fileno())
        free_mb = shutil.disk_usage(folder).free / (1024 * 1024)
        if free_mb < Config.MIN_FREE_DISK_MB:
            logger.warning(f"[health] Queda poco disco: {free_mb:.0f} MB (mínimo {Config.MIN_FREE_DISK_MB} MB)")
            return False
        return True
    except OSError as exc:
        logger.warning(f"[health] No se puede escribir en el disco de datos: {type(exc).__name__}")
        return False


CHECKS: Dict[str, Callable[[], bool]] = {'neo4j': check_neo4j, 'disk': check_disk}


def readiness(force: bool = False) -> Tuple[bool, Dict[str, bool]]:
    """(todo listo, resultado de cada comprobación). Reutiliza el último resultado durante `CACHE_SECONDS`."""
    global _cached
    with _lock:
        stamp, result = _cached
        if not force and result and time.monotonic() - stamp < CACHE_SECONDS:
            return all(result.values()), dict(result)
        result = {name: bool(check()) for name, check in CHECKS.items()}
        _cached = (time.monotonic(), result)
        return all(result.values()), dict(result)


def reset_cache() -> None:
    global _cached
    with _lock:
        _cached = (0.0, {})
