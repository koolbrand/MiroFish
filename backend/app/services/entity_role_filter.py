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
- Ampliar/anclar requiere confirmar un colectivo poblacional (fail-closed).
"""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from ..config import Config
from ..utils.logger import get_logger
from ..utils.locale import t

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
        "colectivo_personas": (
            "Un grupo poblacional de personas físicas anónimas: clientes, vecinos, estudiantes, "
            "teletrabajadores, votantes, familias, pacientes. Puede muestrearse con distintas personas "
            "sin perder su identidad. No es una persona concreta ni una organización."
        ),
        "persona_identificada": (
            "Una persona concreta identificada por su nombre, apellido o cargo individual: "
            "un juez, una política, un influencer o periodista a título personal. Aunque el tema "
            "le afecte, no es un colectivo poblacional ni puede sustituirse por encuestados anónimos."
        ),
        "organizacion": (
            "Una organización o institución con personalidad propia: empresa, marca, negocio, universidad, "
            "ayuntamiento, gobierno, partido político, asociación, medio de comunicación, plataforma o red social"
        ),
        "lugar_o_cosa": (
            "Un lugar o territorio, un texto legal, un evento, una fecha, un concepto, una página web o una fuente de datos: "
            "no tiene voz propia ni opina"
        ),
    },
}

AUDIENCE_ROLE = "audiencia"
INSTITUTION_ROLE = "implicado"        # adónde pasa una organización que Jev había puesto como audiencia
DROP_ROLE = "infraestructura"
ORGANIZATION_MIN_PROB = 0.6           # probabilidad de «organización» a partir de la cual deja de ser audiencia
NON_SPEAKING_MIN_PROB = 0.8           # probabilidad de «lugar o cosa» a partir de la cual no se crea un agente (no tiene voz)
POPULATION_MIN_PROB = 0.65          # ampliar/anclar requiere confirmar que es un colectivo, no solo «personas»


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
    population_group_ids: List[str] = field(default_factory=list)
    population_unconfirmed: List[str] = field(default_factory=list)
    audience_requested: Optional[int] = None

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
            "population_groups": len(self.population_group_ids),
            "population_unconfirmed": self.population_unconfirmed,
            # El rol audiencia también puede incluir actores identificados.
            # Solo estos individuos confirmados pueden muestrearse del banco.
            "audience_requested": self.audience_requested,
            "audience_count": sum(bool((getattr(e, 'attributes', None) or {}).get(INDIVIDUAL_FLAG))
                                  for e in self.kept),
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
            probs = naturaleza.get("probabilities") or {}
            org = float(probs.get("organizacion", 0) or 0)
            cosa = float(probs.get("lugar_o_cosa", 0) or 0)
            return {"role": answer["choice"], "confidence": float(answer.get("confidence", 0)),
                    "organization": org, "thing": cosa,
                    "population_group": float(probs.get("colectivo_personas", 0) or 0),
                    "named_person": float(probs.get("persona_identificada", 0) or 0)}
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
        elif role == AUDIENCE_ROLE:
            # Fallar al clasificar NO borra al actor; sí impide cambiar su identidad por microdatos.
            # La antigua clase «personas» mezclaba jueces nombrados y electorado anónimo.
            collective = float(answer.get("population_group", 0) or 0)
            named = float(answer.get("named_person", 0) or 0)
            if (collective >= POPULATION_MIN_PROB and collective > named
                    and float(answer.get("thing", 0) or 0) < NON_SPEAKING_MIN_PROB
                    and answer["confidence"] >= POPULATION_MIN_PROB):
                result.population_group_ids.append(str(getattr(entity, "uuid", entity.name)))
            else:
                # Puede ser un consumidor concreto y seguir siendo audiencia; se conserva
                # su papel e identidad, pero no se le sustituye por personas anónimas.
                result.population_unconfirmed.append(entity.name)
        result.roles_by_uuid[getattr(entity, "uuid", entity.name)] = role
        result.roles[role] = result.roles.get(role, 0) + 1
        if role == DROP_ROLE and answer["confidence"] >= Config.JEV_DROP_CONFIDENCE:
            result.dropped.append({"name": entity.name, "confidence": round(answer["confidence"], 2)})
        elif role != AUDIENCE_ROLE and float(answer.get("thing", 0) or 0) >= NON_SPEAKING_MIN_PROB:
            # Un lugar (Asturias), un texto legal («Real Decreto-ley 25/2026») o una web no opinan: sin agente, sin perfil que generar
            result.dropped.append({"name": entity.name, "confidence": round(float(answer["thing"]), 2), "motivo": "no habla"})
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


MAX_AUDIENCE_SIZE = 150      # tope duro de `target_size` (cada persona es una llamada al modelo y memoria en la simulación)
MIN_AUDIENCE_SIZE = 5
AUDIENCE_SIZE_UNSET = object()


def validate_audience_size(value) -> Optional[int]:
    """None es automático; valores explícitos son enteros JSON, nunca coerciones."""
    if value is None or type(value) is int and MIN_AUDIENCE_SIZE <= value <= MAX_AUDIENCE_SIZE:
        return value
    raise ValueError(t('api.invalidAudienceSize'))


def expand_audience(entities: list, result: EntityRoleResult, topic: str = "", target_size: Optional[int] = None) -> list:
    """Convierte la audiencia en personas y la amplía si queda por debajo del mínimo.

    - Solo colectivos poblacionales confirmados se marcan para generarse como persona
      individual (no como cuenta colectiva «que representa a…»).
    - Si la audiencia es < JEV_MIN_AUDIENCE_RATIO, cada grupo de audiencia se
      desdobla en variantes (personas distintas dentro del grupo) hasta el
      umbral, con topes por grupo y en total para no disparar la memoria.
    - `target_size` (por simulación): el público llega a ese número de
      personas, repartidas por igual entre los grupos, sin mirar el umbral ni los topes de la configuración. Tope duro: 150.
      Esto no garantiza representatividad nacional ni cuotas políticas.
    """
    import copy
    import math

    result.audience_requested = target_size
    for e in entities:
        # Incluso sin Jev: una preparación nueva no arrastra permiso de una
        # clasificación anterior. Solo se repone tras confirmar un colectivo.
        attributes = dict(getattr(e, "attributes", None) or {})
        for key in (INDIVIDUAL_FLAG, GROUP_KEY, VARIANT_HINT, TOPIC_HINT):
            attributes.pop(key, None)
        e.attributes = attributes
    if not result.applied:
        return entities
    groups = set(result.population_group_ids)
    audience = [e for e in entities if str(getattr(e, "uuid", e.name)) in groups
                and result.roles_by_uuid.get(getattr(e, "uuid", e.name)) == AUDIENCE_ROLE]
    for e in audience:
        e.attributes = dict(e.attributes or {})
        e.attributes[INDIVIDUAL_FLAG] = True
        e.attributes[GROUP_KEY] = str(getattr(e, "uuid", e.name))
        if topic:
            e.attributes[TOPIC_HINT] = topic[:600]
    if not audience or (not target_size and not Config.AUDIENCE_EXPANSION):
        return entities

    total, n_aud = len(entities), len(audience)
    if target_size:
        extra = max(0, min(int(target_size), MAX_AUDIENCE_SIZE) - n_aud)
        if extra == 0:
            return entities
    else:
        target = Config.JEV_MIN_AUDIENCE_RATIO
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
