"""
Precarga en segundo plano del modelo del recomendador de la red tipo X (TwHIN-BERT).

OASIS lo descarga de Hugging Face (1,1 GB) la primera vez que una simulación
lo necesita. En un contenedor nuevo eso ocurre en medio de la primera simulación
de cada despliegue: espera larga y un fallo opaco si el servicio de descarga no
responde en ese momento. Aquí se descarga al arrancar el servidor, en un hilo
aparte y solo a disco (no se carga en memoria), y con un volumen para la caché
se hace una sola vez, no en cada despliegue.

Solo se traen los cinco archivos que usa el modelo, no todo el repositorio.
Un fallo aquí nunca impide arrancar: se registra y la simulación lo reintentará.
Se desactiva con RECSYS_PREWARM=0.
"""
import os
import threading
from typing import Optional

from .logger import get_logger

logger = get_logger('mirofish.recsys_prewarm')

MODEL_ID = 'Twitter/twhin-bert-base'
FILES = ['config.json', 'model.safetensors', 'special_tokens_map.json', 'tokenizer.json', 'tokenizer_config.json']


def _download() -> None:
    try:
        from huggingface_hub import snapshot_download
        path = snapshot_download(MODEL_ID, allow_patterns=FILES)
        logger.info(f"Modelo del recomendador listo en caché: {path}")
    except Exception as exc:  # sin red, servicio caído, disco lleno…
        logger.warning(f"No se pudo precargar el modelo del recomendador ({MODEL_ID}): {exc}. Se descargará al lanzar la primera simulación.")


def start_prewarm() -> Optional[threading.Thread]:
    """Lanza la precarga en segundo plano; devuelve el hilo (o None si está desactivada)."""
    if os.environ.get('RECSYS_PREWARM', '1') != '1':
        return None
    thread = threading.Thread(target=_download, name='recsys-prewarm', daemon=True)
    thread.start()
    return thread
