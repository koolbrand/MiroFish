"""Alcance geográfico de una simulación: ¿para qué público habla? Una ciudad, una región, un país, varios países o el mundo.

De esto depende casi todo lo demás (lo pidió Adrián tras la prueba del Kool Café, 3-oct-2026): a quién se busca en la encuesta,
cómo se genera a quien no sale de ella y con qué cautelas escribe el informe.

- LOCAL (ciudad, pueblo, barrio, comarca, provincia): gente de ese lugar. Se filtra el banco por la provincia y la región que lo
  contienen. Es lógico buscar vigueses para un proyecto de Vigo.
- REGIONAL (una comunidad autónoma, un estado…): gente de esa región.
- NACIONAL (un país entero): gente de TODO el país, sin acotar por lugar. Que una persona de Extremadura opine de algo del País
  Vasco no es un fallo si el problema es nacional. Una ciudad citada como sede o como sitio del evento no cambia el alcance.
- MULTINACIONAL / MUNDIAL: no hay una encuesta que represente a ese público. No se ancla a datos de un solo país (sesgaría hacia
  él); las personas se generan repartiendo culturas a propósito, en lugar de dejar que el modelo caiga en lo estadounidense.

Lo decide un modelo leyendo el brief (según DÓNDE VIVE EL PÚBLICO, no según la sede de la empresa ni el idioma del texto); la
persona puede fijarlo a mano. Si no queda claro, es `desconocido` y todo se comporta como antes (sin acotar).
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ...config import Config
from ...utils.logger import get_logger
from . import jev
from .fuentes import disponibles, abrir_banco

logger = get_logger('mirofish.alcance')

NIVELES = ("local", "regional", "nacional", "multinacional", "mundial")
DESCONOCIDO = "desconocido"
FICHERO = "alcance.json"
ETIQUETAS = {"local": "Local", "regional": "Regional", "nacional": "Nacional", "multinacional": "Multinacional",
             "mundial": "Mundial", DESCONOCIDO: "Sin determinar"}

# Culturas que se reparten, una por persona, cuando el público es de varios países o del mundo entero. El ORDEN importa: con pocas
# personas solo se usan las primeras, así que van alternando regiones lejanas (Occidente, Oriente, Sur global) en vez de agrupadas.
CULTURAS = ("Europa occidental", "Asia oriental", "Latinoamérica", "África subsahariana", "Norteamérica", "Sur de Asia",
            "Oriente Medio y norte de África", "Oceanía", "Europa del Este", "Sudeste asiático")


@dataclass
class Alcance:
    nivel: str = DESCONOCIDO
    lugar: str = ""                        # «Vigo», «Galicia», «España», «Latinoamérica»…
    region: Optional[str] = None           # valor de `Fuente.regiones` que contiene el lugar (local y regional)
    provincia: Optional[str] = None        # valor de las provincias del banco que contiene el lugar (solo local)
    lugares: List[str] = field(default_factory=list)   # multinacional: los países o bloques citados
    regiones: List[str] = field(default_factory=list)  # solo si el público ocupa VARIAS regiones enteras (el noroeste: tres)
    motivo: str = ""
    origen: str = "automatico"             # 'pedido' (lo fijó la persona) | 'automatico'

    def a_dict(self) -> Dict:
        d = asdict(self)
        d["etiqueta"] = self.descripcion()
        return d

    @classmethod
    def de_dict(cls, d: Optional[Dict]) -> Optional["Alcance"]:
        if not isinstance(d, dict):
            return None
        nivel = d.get("nivel") if d.get("nivel") in NIVELES else DESCONOCIDO
        return cls(nivel=nivel, lugar=str(d.get("lugar") or ""), region=d.get("region") or None,
                   regiones=[str(x) for x in (d.get("regiones") or [])][:12], provincia=d.get("provincia") or None, lugares=[str(x) for x in (d.get("lugares") or [])][:12],
                   motivo=str(d.get("motivo") or ""), origen=str(d.get("origen") or "automatico"))

    @property
    def lista_regiones(self) -> List[str]:
        return list(self.regiones) or ([self.region] if self.region else [])

    @property
    def acota_por_lugar(self) -> bool:
        """¿Hay que buscar gente SOLO de un lugar? (local y regional con un lugar que el banco entienda)"""
        return self.nivel in ("local", "regional") and bool(self.lista_regiones or self.provincia)

    @property
    def permite_anclar(self) -> bool:
        """Con varios países o con el mundo no hay una encuesta que represente al público: no se ancla a la de un solo país."""
        return self.nivel not in ("multinacional", "mundial")

    @property
    def zona(self) -> str:
        """La región(es) y la provincia que el banco entiende; nombra la zona cuando el brief no dio un sitio más concreto."""
        return ", ".join(x for x in (*self.lista_regiones, self.provincia) if x and x != self.lugar)

    def descripcion(self) -> str:
        if self.nivel == DESCONOCIDO:
            return ETIQUETAS[DESCONOCIDO]
        sitio = self.lugar or ", ".join(self.lugares)
        detalle = f"{sitio} ({self.zona})" if sitio and self.zona else (sitio or self.zona)
        return f"{ETIQUETAS[self.nivel]} · {detalle}" if detalle else ETIQUETAS[self.nivel]


# ---------------------------------------------------------------- guardar y cargar
def guardar(ruta: str, a: Alcance) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(a.a_dict(), f, ensure_ascii=False, indent=2)


def cargar(simulation_id: str) -> Optional[Alcance]:
    ruta = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, FICHERO)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return Alcance.de_dict(json.load(f))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- detección
PROMPT = """Decide el ALCANCE GEOGRÁFICO de este estudio: dónde vive el PÚBLICO cuya reacción se quiere simular.
Importa dónde vive ese público, no dónde está la empresa ni en qué idioma está escrito el texto.

Niveles (elige UNO):
- local: un lugar acotado: ciudad, pueblo, barrio, comarca o provincia (una cafetería de barrio en Vigo; un comercio en Ourense).
- regional: una región o comunidad entera dentro de un país (Galicia, Cataluña, un estado).
- nacional: un país entero. Aunque el texto cite una ciudad como sede, tienda online o sitio del evento, si el público es de todo el país es nacional.
- multinacional: varios países concretos o un bloque (España y Portugal, la UE, Latinoamérica).
- mundial: sin país concreto, global.

{listas}Devuelve SOLO un objeto JSON, sin texto alrededor:
{{"nivel": "<local|regional|nacional|multinacional|mundial>", "lugar": "<nombre del lugar o país; vacío si es mundial>", "region": "<valor EXACTO de la lista de regiones que contiene el lugar, o null>", "regiones": ["<valores EXACTOS de la lista, SOLO si el público ocupa VARIAS regiones enteras (p. ej. el noroeste: varias comunidades); si no, []>"], "provincia": "<valor EXACTO de la lista de provincias que contiene el lugar, o null>", "lugares": ["<países o bloques, solo si es multinacional>"], "motivo": "<una frase>"}}

Reglas:
- Si el brief no dice dónde vive el público, elige el nivel más razonable por el tipo de producto y dilo en el motivo; no inventes un lugar.
- Región y provincia SOLO en local o regional, y solo si puedes asegurarlas con la lista. En nacional, multinacional y mundial, null.
- Una empresa local que vende por internet a todo el país es nacional. Una empresa extranjera que prueba algo en un solo barrio es local.
- Los visitantes (turistas, peregrinos, asistentes a un evento) son de donde VIENEN, no del sitio que visitan: si llegan de varios países, es multinacional.

Pregunta del estudio:
\"\"\"{pregunta}\"\"\"

Brief y contexto:
\"\"\"{contexto}\"\"\"
"""


def _listas() -> Tuple[str, Dict[str, List[str]], Dict[str, List[str]]]:
    """Regiones y provincias de los países con banco, para que el modelo pueda nombrarlas con el texto exacto."""
    regiones: Dict[str, List[str]] = {}
    provincias: Dict[str, List[str]] = {}
    for f in disponibles():
        try:
            regiones[f.pais_nombre] = list(f.regiones)
            provincias[f.pais_nombre] = abrir_banco(f).subregiones()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"No se pudieron leer las provincias de {f.id}: {e}")
    if not regiones:
        return "", {}, {}
    txt = ""
    for pais, regs in regiones.items():
        txt += f"Regiones de {pais}: {', '.join(regs)}\n"
        if provincias.get(pais):
            txt += f"Provincias de {pais}: {', '.join(provincias[pais])}\n"
    return txt + "\n", regiones, provincias


def _extraer(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto or "", flags=re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def _norm(x) -> str:
    return " ".join(str(x or "").split()).strip()


def _lista_texto(x, maximo: int = 12, largo: int = 80) -> List[str]:
    """Una lista de textos limpia venga como venga del modelo: un texto suelto es UN elemento (no se parte en letras) y lo
    que no es lista ni texto se ignora."""
    if isinstance(x, str):
        x = [x]
    if not isinstance(x, (list, tuple)):
        return []
    return [_norm(i)[:largo] for i in x if isinstance(i, (str, int, float)) and _norm(i)][:maximo]


def _regiones_de_provincia(provincia: Optional[str]) -> List[str]:
    """Las regiones que, según los bancos disponibles, contienen esa provincia (la región la dice el propio banco)."""
    regs: List[str] = []
    if not provincia:
        return regs
    for f in disponibles():
        try:
            regs += [r for r in abrir_banco(f).regiones_de(provincia) if r not in regs]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"No se pudo mirar la región de {provincia} en {f.id}: {e}")
    return regs


# Con Jev el nivel se decide en ~1 s; por debajo de esta confianza se pregunta además al modelo grande
CONFIANZA_JEV = 0.6
UMBRAL_SI = 0.5

CRITERIOS_NIVEL = {
    "local": "El público vive en un lugar acotado: una ciudad, un pueblo, un barrio, una comarca o una provincia concreta.",
    "regional": "El público vive en una región o comunidad entera, o en varias comunidades vecinas (Galicia, Cataluña, el noroeste peninsular).",
    "nacional": ("El público es de un país entero, aunque el texto cite una ciudad como sede de la empresa, como tienda online o como "
                 "sitio de un evento al que llega gente de todo el país."),
    "multinacional": ("El público es de varios países concretos o de un bloque (España y Portugal, la UE, Latinoamérica), incluidos los "
                      "visitantes o turistas que llegan de varios países."),
    "mundial": "El público es global, sin un país concreto.",
}


def _detectar_con_jev(pregunta: str, contexto: str, nivel_fijado: Optional[str] = None) -> Optional[Alcance]:
    """
    Nivel, región(es) y provincia con Jev, en UNA petición (todas las preguntas se evalúan en paralelo). Devuelve None si Jev no está,
    falla, no está seguro (confianza baja) o el alcance es multinacional (hacen falta los países por su nombre: eso lo extrae el modelo).
    `nivel_fijado` (local o regional, lo eligió la persona): no se pregunta el nivel, pero sí dónde, para no perder el lugar.
    Jev no extrae el NOMBRE del sitio (Vigo): da la provincia y la región; el sitio concreto lo conoce quien lee el brief.
    """
    if not jev.disponible() or not (_norm(pregunta) or _norm(contexto)):
        return None
    listas, regiones, provincias = _listas()
    todas_regiones = [r for v in regiones.values() for r in v]
    todas_provincias = [p for v in provincias.values() for p in v]
    preguntas = {}
    if not nivel_fijado:
        preguntas["nivel"] = jev.choice(
            "¿Dónde vive el público cuya reacción se quiere simular? Importa dónde vive ese público, no dónde está la empresa ni en qué "
            "idioma está escrito el texto. Los visitantes, turistas o asistentes a un evento son de donde VIENEN, no del sitio que visitan.",
            CRITERIOS_NIVEL)
    for r in todas_regiones:
        preguntas[f"region::{r}"] = jev.noul(
            f"¿El público del estudio vive en la región «{r}»? Si el estudio es de una ciudad, comarca o provincia de «{r}», sí. Si el "
            f"público es de todo el país o de otros sitios, no.")
    if todas_provincias:
        preguntas["provincia"] = jev.choice(
            "Si el público vive en un lugar acotado, ¿en qué provincia está ese lugar? «ninguna» si el público no es de una sola provincia "
            "(región entera, país entero, varios países o el mundo).",
            {**{p: f"La provincia de {p}" for p in todas_provincias}, "ninguna": "No es de una provincia concreta"})
    if not preguntas:
        return None
    r = jev.preguntar({"pregunta_del_estudio": _norm(pregunta)[:1500], "brief": (contexto or "").strip()[:4000]}, preguntas)
    if not r or (not nivel_fijado and "nivel" not in r):
        return None
    if nivel_fijado:
        nivel, motivo = nivel_fijado, "Lugar decidido con Jev."
    else:
        nivel = r["nivel"].get("choice")
        confianza = float(r["nivel"].get("confidence", 0))
        if nivel not in NIVELES or confianza < CONFIANZA_JEV or nivel == "multinacional":
            return None
        motivo = f"Decidido con Jev (confianza {confianza:.2f})."
    a = Alcance(nivel=nivel, motivo=motivo)
    if nivel in ("local", "regional"):
        elegidas = [x for x in todas_regiones if float(r.get(f"region::{x}", {}).get("noul", 0)) >= UMBRAL_SI]
        prov = (r.get("provincia") or {}).get("choice")
        if nivel == "local" and prov in todas_provincias and float((r["provincia"].get("probabilities") or {}).get(prov, 0)) >= UMBRAL_SI:
            a.provincia = prov
            regs_prov = _regiones_de_provincia(prov)
            if regs_prov:                            # la provincia manda: su región la dice el banco, aunque un «sí» suelto diga otra
                a.region = next((x for x in regs_prov if x in elegidas), regs_prov[0])
                elegidas = []
        if a.region is None:
            if len(elegidas) == 1:
                a.region = elegidas[0]
            elif len(elegidas) >= 2:                 # varias regiones enteras (el noroeste): sin «principal» ni provincia
                a.regiones = elegidas[:12]
                a.provincia = None
        if nivel == "regional":
            a.provincia = None
    return a                                          # `lugar` queda vacío: nunca se pasa una provincia por el sitio, ni un país por el banco


def detectar(pedido: Optional[str], pregunta: str, contexto: str,
             llm: Optional[Callable[[str], str]]) -> Alcance:
    """
    `pedido`: un nivel fijado por la persona, o 'auto'/None para que lo decida el modelo. Si el modelo no responde, no se
    inventa nada: `desconocido`, que se comporta como antes. Si la persona fijó el nivel, manda ella aunque el modelo falle.
    """
    fijado = str(pedido).strip().lower() if pedido else ""
    fijado = fijado if fijado in NIVELES else ""
    if fijado in ("mundial", "nacional"):            # lo fijó la persona y no lleva lugar: no hace falta ni preguntar
        return Alcance(fijado, motivo="Alcance elegido por la persona.", origen="pedido")
    detectado = Alcance()
    rapido = None
    if fijado != "multinacional":                    # los países por su nombre solo los extrae el modelo grande
        try:
            rapido = _detectar_con_jev(pregunta, contexto, fijado or None)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Jev no pudo decidir el alcance: {e}")
    if rapido is not None:
        detectado = rapido
    elif llm is not None and (_norm(pregunta) or _norm(contexto)):
        listas, regiones, provincias = _listas()
        try:
            crudo = _extraer(llm(PROMPT.format(listas=listas, pregunta=_norm(pregunta)[:1500],
                                               contexto=(contexto or "").strip()[:4000])))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"No se pudo decidir el alcance: {e}")
            crudo = {}
        nivel = _norm(crudo.get("nivel")).lower()
        if nivel in NIVELES:
            todas_regiones = {r for v in regiones.values() for r in v}
            todas_provincias = {p for v in provincias.values() for p in v}
            region = _norm(crudo.get("region")) if _norm(crudo.get("region")) in todas_regiones else None
            provincia = _norm(crudo.get("provincia")) if _norm(crudo.get("provincia")) in todas_provincias else None
            varias = [r for r in dict.fromkeys(_lista_texto(crudo.get("regiones"))) if r in todas_regiones]
            if region and region not in varias:
                varias.insert(0, region)
            regiones: List[str] = []
            if len(varias) >= 2:                           # un público de varias regiones enteras: sin una «principal» ni provincia
                regiones, region, provincia = varias[:12], None, None
            elif len(varias) == 1:
                region = varias[0]
            if nivel not in ("local", "regional"):
                region = provincia = None
                regiones = []
            if nivel == "regional":
                provincia = None
            if nivel == "local" and provincia and not regiones:
                regs_prov = _regiones_de_provincia(provincia)    # la provincia manda: su región la dice el banco
                if regs_prov:
                    region = next((x for x in regs_prov if x == region), regs_prov[0])
            lugares = _lista_texto(crudo.get("lugares"), largo=60) if nivel == "multinacional" else []
            detectado = Alcance(nivel=nivel, lugar=_norm(crudo.get("lugar"))[:80], region=region, regiones=regiones,
                                provincia=provincia, lugares=lugares, motivo=_norm(crudo.get("motivo"))[:300])
        else:
            detectado.motivo = "El modelo no dio un alcance válido."
    elif llm is None or not (_norm(pregunta) or _norm(contexto)):
        detectado.motivo = "No hay texto para decidir el alcance."
    if not fijado:
        return detectado
    # La persona lo fijó: manda su nivel. El lugar del modelo solo vale si sigue teniendo sentido en ese nivel.
    mantiene = fijado in ("local", "regional") and detectado.nivel in ("local", "regional", "nacional")
    a = Alcance(nivel=fijado, lugar=detectado.lugar if mantiene else "",
                region=detectado.region if mantiene else None,
                regiones=detectado.regiones if mantiene else [],
                provincia=detectado.provincia if fijado == "local" and mantiene else None,
                lugares=detectado.lugares if fijado == "multinacional" else [],
                motivo="Alcance elegido por la persona.", origen="pedido")
    return a


# ---------------------------------------------------------------- lo que implica cada nivel
def pista_para_persona(a: Optional[Alcance], indice: int = 0) -> str:
    """
    Una frase para el prompt de una persona del público que NO sale de la encuesta, según el alcance. `indice` es el orden de la
    persona ENTRE las del público (no el de la entidad en el grafo): reparte las culturas de forma pareja.
    """
    if a is None or a.nivel == DESCONOCIDO:
        return ""
    if a.nivel == "local":
        if a.lugar:
            donde = f"vive en {a.lugar} o muy cerca"
            sitio = a.lugar
        else:                                        # solo se sabe la zona: el sitio concreto es el que cite el estudio
            sitio = a.zona or "ese lugar"
            donde = (f"vive en el lugar al que se refiere el estudio (la ciudad o el barrio que citan los documentos), dentro de esta "
                     f"zona: {sitio}; no lo cambies por la provincia")
        return (f"Alcance de la simulación: LOCAL ({sitio}). Esta persona {donde}; usa referencias reales y "
                "cotidianas de ese sitio (barrios, costumbres, precios) sin caricaturizarlo ni caer en tópicos.")
    if a.nivel == "regional":
        sitio = a.lugar or ", ".join(a.lista_regiones) or "esa región"
        return (f"Alcance de la simulación: REGIONAL ({sitio}). Esta persona vive en {sitio}, en cualquier ciudad o pueblo de allí "
                "(si son varias comunidades, varía de una a otra); varía el lugar concreto de una persona a otra.")
    if a.nivel == "nacional":
        sitio = a.lugar or "el país del que habla el estudio"
        return (f"Alcance de la simulación: NACIONAL ({sitio}). Esta persona vive en cualquier parte de {sitio}: varía el lugar de "
                "una persona a otra (no todas de la capital ni de la misma ciudad) y no la sitúes en la ciudad de la sede o del evento "
                "por defecto.")
    pool = a.lugares or list(CULTURAS)
    cultura = pool[indice % len(pool)]
    return (f"Alcance de la simulación: {ETIQUETAS[a.nivel].upper()}. El público es de varios países o del mundo entero, así que esta "
            f"persona NO es de un país por defecto: vive en o procede de «{cultura}» (país y cultura que debes concretar con "
            "coherencia). Que sus costumbres, su manera de consumir y de hablar sean las de allí, no las de un estadounidense genérico.")


def texto_para_informe(a: Optional[Alcance]) -> str:
    """Cautelas de alcance para quien escribe el informe (nivel de las conclusiones, estereotipos y límites)."""
    if a is None or a.nivel == DESCONOCIDO:
        return ""
    base = f"ALCANCE GEOGRÁFICO DE LA SIMULACIÓN: {a.descripcion()}."
    if a.nivel == "local":
        if a.lugar:
            donde = f"{base} Las conclusiones valen para ese lugar"
            sitio_txt = f" ({a.lugar})"
        else:
            # Jev da la zona (región/provincia) pero no el nombre del sitio: el nombre sale de los documentos, y la provincia NO es
            # «la ciudad» (visto en producción: un informe sobre Vigo titulado «Kool Café en Pontevedra» por esta nota)
            base = (f"ALCANCE GEOGRÁFICO DE LA SIMULACIÓN: LOCAL, en la zona de {a.zona or 'un lugar concreto'}. El lugar exacto (una ciudad, "
                    "un barrio) es el que citan los documentos del estudio: usa SIEMPRE ese nombre y no lo sustituyas por la provincia ni por "
                    "la región; la zona solo sirve para situarlo.")
            donde = f"{base} Las conclusiones valen para ese lugar"
            sitio_txt = ""
        return (f"{donde}: no las extrapoles al país ni a otras ciudades. Contextualiza con el mercado local{sitio_txt} solo con lo que "
                "muestren la simulación y los documentos: no inventes datos de competencia, precios ni hábitos locales que no tengas, y no "
                "uses estereotipos de otros lugares.")
    if a.nivel == "regional":
        return (f"{base} Las conclusiones valen para esa región, no para el país entero. Matiza las diferencias entre sus ciudades y "
                "comarcas solo si la simulación las muestra, y no uses estereotipos de otras regiones.")
    if a.nivel == "nacional":
        return (f"{base} Habla del país entero: no atribuyas lo observado a una ciudad concreta salvo que la simulación lo muestre, "
                "y trata las diferencias entre regiones como matiz, no como tesis. Evita estereotipos de una sola zona.")
    return (f"{base} Los agentes representan culturas distintas y hay pocos por cultura: no generalices a un solo país, indica qué parte de "
            "lo observado parece cultural y cuál no, y avisa de que con tan pocos agentes por cultura las diferencias son orientativas.")
