"""
Filtro de entidades con Jev (TypeSafe) antes de crear los agentes.

El grafo trae entidades que no opinarían en redes sobre el tema (tiendas de
apps, servicios en la nube, herramientas de analítica...). Convertirlas en
agentes gasta memoria, tiempo y llamadas al LLM, y diluye a la audiencia real:
en el piloto de Northkin eran 8 de 23 agentes y la audiencia solo 3 de 23.

Jev devuelve una decisión cerrada con probabilidad calibrada (~0,6 s, una
fracción de céntimo). Reglas:
- Una petición por entidad, en paralelo (un state = un asunto).
- Solo se descarta la infraestructura con confianza alta; lo dudoso se queda.
- Si Jev no está configurado o falla, no se descarta nada (fail-open).
"""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.entity_role_filter')

ROLE_QUESTION = {
    "type": "choice",
    "instructions": (
        "¿Qué papel tiene `entidad` en la conversación pública en redes sociales "
        "sobre `tema_de_la_simulacion`?"
    ),
    "criteria": {
        "audiencia": (
            "Personas o colectivos de personas a quienes va dirigido el tema o a "
            "quienes afecta: consumidores, usuarios, familias, ciudadanos, vecinos, "
            "estudiantes, pacientes..."
        ),
        "competidor": (
            "Un producto, marca, negocio o alternativa que compite con lo que se "
            "lanza o propone, incluidas las alternativas gratuitas o de siempre"
        ),
        "voz_influyente": (
            "Creadores de contenido, periodistas, medios, blogs, expertos o líderes "
            "de opinión que comentan y recomiendan"
        ),
        "implicado": (
            "Una organización con interés directo que opinaría públicamente: la "
            "propia marca o empresa que lanza, un gobierno, un regulador, un socio, "
            "una asociación"
        ),
        "infraestructura": (
            "Una plataforma, tienda, servicio técnico, herramienta o fuente de datos "
            "que no opinaría como usuario ni como parte interesada sobre el tema "
            "(tiendas de apps, nube, analítica, pasarelas de pago, una red social "
            "como empresa)"
        ),
    },
}

AUDIENCE_ROLE = "audiencia"
DROP_ROLE = "infraestructura"


@dataclass
class EntityRoleResult:
    kept: list
    dropped: List[Dict] = field(default_factory=list)
    roles: Dict[str, int] = field(default_factory=dict)
    classified: int = 0
    applied: bool = False
    reason: str = ""

    @property
    def audience_ratio(self) -> Optional[float]:
        total = sum(self.roles.values())
        return (self.roles.get(AUDIENCE_ROLE, 0) / total) if total else None

    def summary(self) -> Dict:
        ratio = self.audience_ratio
        return {
            "applied": self.applied,
            "reason": self.reason,
            "classified": self.classified,
            "kept": len(self.kept),
            "dropped": self.dropped,
            "roles": self.roles,
            "audience_ratio": round(ratio, 3) if ratio is not None else None,
            "low_audience": (
                ratio is not None and ratio < Config.JEV_MIN_AUDIENCE_RATIO
            ),
        }


def _ask_jev(client: httpx.Client, entity, topic: str) -> Optional[Dict]:
    """Una decisión por entidad. Devuelve {'role', 'confidence'} o None si falla."""
    payload = {
        "model": Config.JEV_MODEL,
        "state": {
            "tema_de_la_simulacion": topic,
            "entidad": {
                "nombre": entity.name,
                "tipo": entity.get_entity_type() if hasattr(entity, "get_entity_type") else None,
                "resumen": (entity.summary or "")[:1500],
            },
        },
        "questions": {"rol": ROLE_QUESTION},
    }
    delay = 1.0
    for attempt in range(3):
        try:
            response = client.post(Config.TYPESAFE_API_URL, json=payload)
            if response.status_code in (429, 529) and attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            answer = response.json()["answers"]["rol"]
            return {"role": answer["choice"], "confidence": float(answer.get("confidence", 0))}
        except Exception as e:  # noqa: BLE001 — fail-open: sin respuesta, la entidad se queda
            if attempt == 2:
                logger.warning(f"Jev no clasificó '{entity.name}': {type(e).__name__}: {str(e)[:120]}")
            else:
                time.sleep(delay)
                delay *= 2
    return None


def filter_entities(entities: list, topic: str) -> EntityRoleResult:
    """Clasifica las entidades y descarta la infraestructura con confianza alta."""
    if not Config.JEV_ENTITY_FILTER:
        return EntityRoleResult(kept=list(entities), reason="desactivado")
    if not Config.TYPESAFE_API_KEY:
        return EntityRoleResult(kept=list(entities), reason="sin TYPESAFE_API_KEY")
    if not entities:
        return EntityRoleResult(kept=[], reason="sin entidades")

    headers = {"Authorization": f"Bearer {Config.TYPESAFE_API_KEY}"}
    with httpx.Client(timeout=20, headers=headers) as client:
        with ThreadPoolExecutor(max_workers=min(16, len(entities))) as pool:
            answers = list(pool.map(lambda e: _ask_jev(client, e, topic), entities))

    result = EntityRoleResult(kept=[], applied=True)
    for entity, answer in zip(entities, answers):
        if answer is None:
            result.kept.append(entity)
            continue
        result.classified += 1
        role = answer["role"]
        result.roles[role] = result.roles.get(role, 0) + 1
        if role == DROP_ROLE and answer["confidence"] >= Config.JEV_DROP_CONFIDENCE:
            result.dropped.append({"name": entity.name, "confidence": round(answer["confidence"], 2)})
        else:
            result.kept.append(entity)

    # Si Jev no respondió a ninguna, es un fallo del servicio: no se aplica nada
    if result.classified == 0:
        return EntityRoleResult(kept=list(entities), reason="Jev no respondió")

    # Nunca dejar la simulación sin agentes por culpa del filtro
    if not result.kept:
        return EntityRoleResult(kept=list(entities), roles=result.roles,
                                classified=result.classified, reason="el filtro lo descartaba todo")

    logger.info(
        f"Filtro Jev: {result.classified}/{len(entities)} clasificadas, "
        f"{len(result.dropped)} descartadas (infraestructura), roles={result.roles}"
    )
    return result
