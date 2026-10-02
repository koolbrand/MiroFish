"""Jev (TypeSafe) para las decisiones cerradas y rápidas del público: nivel de alcance, región, provincia y qué preguntas de la
encuesta importan para un tema.

Jev responde con una decisión cerrada y una probabilidad calibrada en ~1 s, y todas las preguntas de una misma petición se evalúan
en paralelo (https://docs.typesafe.ai/patterns/fan-out.md): decenas de decisiones cuestan lo mismo que una. El modelo de
razonamiento grande tarda de 20 a 60 s por decisión y a veces devuelve vacío. Por eso Jev decide y el modelo grande queda de respaldo:
sin clave, con un fallo del servicio o con poca confianza, quien llama sigue con el camino lento de siempre.

Una petición es `{"model", "state", "questions": {id: {type, instructions, criteria}}}` y la respuesta trae `answers[id]` con
`choice` + `probabilities` + `confidence` (Choice) o `noul` (probabilidad del sí). La clave es la misma del filtro de entidades.
"""

import time
from typing import Dict, Optional

import httpx

from ...config import Config
from ...utils.logger import get_logger

logger = get_logger('mirofish.poblacion.jev')

TIMEOUT = 25
MAX_POR_PETICION = 120          # la documentación no fija un tope; se trocea para no depender de él


def disponible() -> bool:
    return bool(Config.TYPESAFE_API_KEY) and Config.JEV_ENTITY_FILTER is not False


def choice(instrucciones: str, criterios: Dict[str, str]) -> dict:
    """Una pregunta de elegir una opción (máximo 255)."""
    return {"type": "choice", "instructions": instrucciones, "criteria": criterios}


def noul(instrucciones: str, si: str = "Sí", no: str = "No") -> dict:
    """Una pregunta de sí o no: devuelve la probabilidad del sí."""
    return {"type": "noul", "instructions": instrucciones, "criteria": {"true": si, "false": no}}


def _post(cliente: httpx.Client, state, preguntas: Dict[str, dict]) -> Optional[Dict[str, dict]]:
    payload = {"model": Config.JEV_MODEL, "state": state, "questions": preguntas}
    espera = 1.0
    for intento in range(3):
        try:
            r = cliente.post(Config.TYPESAFE_API_URL, json=payload)
            if r.status_code in (429, 529) and intento < 2:
                time.sleep(espera)
                espera *= 2
                continue
            r.raise_for_status()
            return r.json()["answers"]
        except Exception as e:  # noqa: BLE001 — sin respuesta, quien llama usa el camino lento
            if intento == 2:
                logger.warning(f"Jev no respondió: {type(e).__name__}: {str(e)[:120]}")
            else:
                time.sleep(espera)
                espera *= 2
    return None


def preguntar(state, preguntas: Dict[str, dict]) -> Optional[Dict[str, dict]]:
    """
    Todas las preguntas sobre el mismo `state` (se trocean si son muchas). Devuelve {id: respuesta} o None si no hay clave o
    Jev falla en algún trozo: una respuesta a medias no vale para decidir.
    """
    if not disponible() or not preguntas:
        return None
    ids = list(preguntas)
    respuestas: Dict[str, dict] = {}
    with httpx.Client(timeout=TIMEOUT, headers={"Authorization": f"Bearer {Config.TYPESAFE_API_KEY}"}) as cliente:
        for i in range(0, len(ids), MAX_POR_PETICION):
            parte = _post(cliente, state, {k: preguntas[k] for k in ids[i:i + MAX_POR_PETICION]})
            if parte is None:
                return None
            respuestas.update(parte)
    return respuestas
