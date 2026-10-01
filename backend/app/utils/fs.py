"""
Archivos de estado en disco: escribir sin dejarlos a medias y leer sin que uno roto tumbe todo.

Todo el estado de Simuloo vive en JSON bajo `uploads/` (proyecto, simulación, informe...). `open(path, 'w')`
trunca el archivo al abrirlo: un lector que llega justo entonces ve un JSON vacío o a medias, y un corte
(memoria agotada, despliegue) lo deja roto para siempre. Aquí se escribe en un temporal de la misma carpeta y
se sustituye de golpe (`os.replace` es atómico en el mismo sistema de archivos).
"""

import json
import os
import tempfile
from typing import Any, Callable, Optional

from .logger import get_logger

logger = get_logger('mirofish.fs')


def atomic_write_text(path: str, text: str, *, fsync: bool = True, create_dir: bool = True) -> None:
    """Escribe `text` en `path` de forma atómica. Con `create_dir=False` falla si la carpeta ya no existe
    (un hilo que sigue vivo no debe resucitar la carpeta de algo que se acaba de borrar)."""
    directory = os.path.dirname(os.path.abspath(path))
    if create_dir:
        os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix='.', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            if fsync:
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, data: Any, *, indent: Optional[int] = 2, fsync: bool = True,
                      create_dir: bool = True, default: Optional[Callable] = None) -> None:
    """`json.dump` atómico. Serializa ANTES de tocar el disco: si `data` no se puede serializar, el archivo
    anterior queda intacto."""
    text = json.dumps(data, ensure_ascii=False, indent=indent, default=default)
    atomic_write_text(path, text, fsync=fsync, create_dir=create_dir)


def read_json_or_none(path: str, *, what: str = '') -> Optional[Any]:
    """
    Lee un JSON. `None` si no existe (o se borró mientras tanto) o si está ilegible: en ese caso lo
    registra y NO lanza, para que un solo archivo malo no tumbe un listado entero.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning(f"[estado] No se pudo leer {what or path}: {exc}")
        return None


def exists_but_unreadable(path: str) -> bool:
    """¿Hay un archivo pero no se puede interpretar como JSON? (se distingue de «no existe» para no dejar
    pasar a nadie por un archivo roto)."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        return False
    except (OSError, ValueError):
        return True
