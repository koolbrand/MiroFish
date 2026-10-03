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

# Qué ES la entidad, con independencia de su papel. Sin esto, «Universidad de Vigo» salía como audiencia (afecta a estudiantes)
# y se generaba como una estudiante de intercambio: un colectivo de personas es audiencia, una organización no.
NATURE_QUESTION = {
    "type": "choice",
    "instructions": (
        "¿Qué ES `entidad` en sí misma, con independencia de su papel en el tema? "
        "Fíjate en lo que es, no en a quién afecta."
    ),
    "criteria": {
        "personas": (
            "Una persona concreta o un colectivo de personas físicas: clientes, vecinos, estudiantes, "
            "teletrabajadores, votantes, familias, pacientes, un influencer o periodista a título personal"
        ),
        "organizacion": (
            "Una organización o institución con personalidad propia: empresa, marca, negocio, universidad, "
            "ayuntamiento, gobierno, partido político, asociación, medio de comunicación, plataforma o red social"
        ),
        "lugar_o_cosa": "Un lugar, un producto, un evento o un concepto que no es ni una persona ni una organización",
    },
}

AUDIENCE_ROLE = "audiencia"
INSTITUTION_ROLE = "implicado"        # adónde pasa una organización que Jev había puesto como audiencia
DROP_ROLE = "infraestructura"
ORGANIZATION_MIN_PROB = 0.6           # probabilidad de «organización» a partir de la cual deja de ser audiencia


@dataclass
class EntityRoleResult:
    kept: list
    dropped: List[Dict] = field(default_factory=list)
    roles: Dict[str, int] = field(default_factory=dict)
    classified: int = 0
    applied: bool = False
    reason: str = ""
    roles_by_uuid: Dict[str, str] = field(default_factory=dict)
    audience_expanded: int = 0
    reclassified: List[str] = field(default_factory=list)   # organizaciones que no se tratan como audiencia

    @property
    def audience_ratio(self) -> Optional[float]:
        # Sobre los agentes que quedan de verdad (incluidos los que Jev no clasificó)
        total = len(self.kept)
        return (self.roles.get(AUDIENCE_ROLE, 0) / total) if total > 0 else None

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
            "audience_expanded": self.audience_expanded,
            "reclassified": self.reclassified,
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
        "questions": {"rol": ROLE_QUESTION, "naturaleza": NATURE_QUESTION},
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
            answers = response.json()["answers"]
            answer = answers["rol"]
            naturaleza = answers.get("naturaleza") or {}
            org = float((naturaleza.get("probabilities") or {}).get("organizacion", 0) or 0)
            return {"role": answer["choice"], "confidence": float(answer.get("confidence", 0)), "organization": org}
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
        if role == AUDIENCE_ROLE and float(answer.get("organization", 0) or 0) >= ORGANIZATION_MIN_PROB:
            # Una universidad, un ayuntamiento o una empresa no es una persona ni un grupo de personas: no se genera como una
            role = INSTITUTION_ROLE
            result.reclassified.append(entity.name)
        result.roles_by_uuid[getattr(entity, "uuid", entity.name)] = role
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
        + (f", organizaciones fuera de la audiencia={result.reclassified}" if result.reclassified else "")
    )
    return result


# ---------------------------------------------------------------------------
# Ampliación de audiencia
# ---------------------------------------------------------------------------
INDIVIDUAL_FLAG = "__simuloo_individual"
GROUP_KEY = "__simuloo_group"       # uuid de la entidad base: ella y sus variantes forman un grupo del público
VARIANT_HINT = "__simuloo_variant"
TOPIC_HINT = "__simuloo_topic"


def expand_audience(entities: list, result: EntityRoleResult, topic: str = "") -> list:
    """Convierte la audiencia en personas y la amplía si queda por debajo del mínimo.

    - Toda entidad con papel «audiencia» se marca para generarse como persona
      individual (no como cuenta colectiva «que representa a…»).
    - Si la audiencia es < JEV_MIN_AUDIENCE_RATIO, cada grupo de audiencia se
      desdobla en variantes (personas distintas dentro del grupo) hasta el
      umbral, con topes por grupo y en total para no disparar la memoria.
    """
    import copy
    import math

    if not result.applied:
        return entities
    audience = [e for e in entities if result.roles_by_uuid.get(getattr(e, "uuid", e.name)) == AUDIENCE_ROLE]
    for e in audience:
        e.attributes = dict(e.attributes or {})
        e.attributes[INDIVIDUAL_FLAG] = True
        e.attributes[GROUP_KEY] = str(getattr(e, "uuid", e.name))
        if topic:
            e.attributes[TOPIC_HINT] = topic[:600]
    if not audience or not Config.AUDIENCE_EXPANSION:
        return entities

    total, n_aud, target = len(entities), len(audience), Config.JEV_MIN_AUDIENCE_RATIO
    if n_aud / total >= target:
        return entities
    needed = math.ceil(round((target * total - n_aud) / (1 - target), 6))  # round: 0,4*8 = 3,2000000000000006
    extra = min(needed, Config.AUDIENCE_MAX_EXTRA, n_aud * Config.AUDIENCE_MAX_VARIANTS)

    variants, per_group = [], {id(e): 1 for e in audience}
    i = 0
    while len(variants) < extra:
        base = audience[i % n_aud]
        per_group[id(base)] += 1
        n = per_group[id(base)]
        v = copy.copy(base)
        v.uuid = f"{getattr(base, 'uuid', base.name)}-v{n}"
        v.name = f"{base.name} · {n}"
        v.attributes = dict(base.attributes)
        v.attributes[VARIANT_HINT] = n
        v.related_edges = list(getattr(base, "related_edges", []) or [])
        v.related_nodes = list(getattr(base, "related_nodes", []) or [])
        variants.append(v)
        i += 1
    result.audience_expanded = len(variants)
    result.kept = list(entities) + variants
    result.roles[AUDIENCE_ROLE] = result.roles.get(AUDIENCE_ROLE, 0) + len(variants)
    logger.info(f"Audiencia ampliada: {n_aud} grupos -> +{len(variants)} personas (total {total + len(variants)})")
    return result.kept
