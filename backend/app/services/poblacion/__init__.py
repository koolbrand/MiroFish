"""Público con datos reales: cada persona simulada del público se ancla a un encuestado real y anónimo de la encuesta
oficial del PAÍS del público (CIS para España; el registro de `fuentes.py` admite más).

Uso interno de I+D hasta tener la autorización escrita de cada titular de los datos (ver `docs/estrategia-poblacion-por-pais.md`).
Los microdatos no están en el repo: se leen de SQLite en `POBLACION_BANCOS_DIR`.

Cómo se reparte la gente (la idea central): el grafo del brief da GRUPOS («jubilados», «familias jóvenes del barrio»…) y
las variantes de cada grupo; la encuesta pone a las PERSONAS. Cada grupo pide a su propio segmento tantos encuestados como
personas tenga, sin repetir a nadie en la simulación. Así un grupo de jubilados no recibe a una estudiante de 22 años, y
dentro de un grupo cada variante es una persona distinta con sus propias respuestas (la variedad la pone la encuesta, no
la temperatura del modelo).
"""

import json
import os
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ...config import Config
from ...utils.logger import get_logger
from .banco import Banco, Encuestado, Segmento
from .ficha import construir_ficha as _construir_ficha
from .ficha import genero_oasis, hechos_memoria
from .filtros import traducir_grupos
from .metricas import CAMPOS_CALIDAD, calidad_de_grupo
from .fuentes import (FUENTES, Fuente, abrir_banco, disponibles, fuente_de_pais, registrar, ruta_banco,
                      tiene_banco)
from .pais import Deteccion, detectar
from .vocabulario import TRAMOS

logger = get_logger('mirofish.poblacion')

RESUMEN = "poblacion.json"
RESUMEN_ANTIGUO = "poblacion_cis.json"        # nombre de antes de que hubiera más de un país


def modo_activo(pedido: Optional[bool] = None) -> bool:
    """El interruptor de la interfaz manda; si no llega, lo que diga POBLACION_DATOS_REALES. Sin ningún banco, nunca."""
    quiere = Config.POBLACION_DATOS_REALES if pedido is None else bool(pedido)
    return bool(quiere and disponibles())


def banco_existe() -> bool:
    return bool(disponibles())


def construir_ficha(e: Encuestado, fuente: Optional[Fuente] = None, tema: str = "",
                    relevantes: Optional[List[str]] = None) -> str:
    return _construir_ficha(e, fuente=fuente, tema=tema, relevantes=relevantes)


PROMPT_RELEVANTES = """Se simula cómo reaccionaría un público a este tema:
\"\"\"{tema}\"\"\"

De la siguiente lista de preguntas de una encuesta oficial, elige hasta {n} que más ayuden a entender cómo reaccionaría
una persona real a ESE tema: su situación económica, ingresos y consumo, sus valores y su confianza, sus preocupaciones
cotidianas. DESCARTA las preguntas sobre noticias o sucesos concretos que no tengan relación con el tema (fronteras,
incendios, visitas, líderes) y las de trabajo de campo.

Preguntas:
{lista}

Devuelve SOLO un objeto JSON, sin texto alrededor: {{"indices": [<números de la lista>]}}"""


def preguntas_relevantes(banco: Banco, tema: str, llm: Optional[Callable[[str], str]], n: int = 15) -> List[str]:
    """
    Qué preguntas de la encuesta llevan a la ficha de cada persona para ESTE tema. Una sola llamada por simulación sobre
    el catálogo de preguntas de uso general. Sin tema, sin modelo o si algo falla devuelve [] y la ficha usa el orden de
    siempre (lo que no tiene que ver con el tema no se cuela porque el modelo solo puede ELEGIR de la lista).
    """
    if llm is None or not (tema or "").strip():
        return []
    try:
        catalogo = banco.catalogo()
        if not catalogo:
            return []
        lista = "\n".join(f"{i}. {q[:140]}" for i, q in enumerate(catalogo))
        crudo = llm(PROMPT_RELEVANTES.format(tema=" ".join(tema.split())[:1200], n=n, lista=lista))
        m = re.search(r"\{.*\}", crudo or "", flags=re.S)
        indices = json.loads(m.group(0)).get("indices", []) if m else []
        vistos, elegidas = set(), []
        for i in indices:
            if isinstance(i, int) and 0 <= i < len(catalogo) and i not in vistos:
                vistos.add(i)
                elegidas.append(catalogo[i])
        if not elegidas:
            logger.warning("Preguntas relevantes: el modelo no eligió ninguna válida (respuesta: %r)", (crudo or "")[:120])
        return elegidas[:n]
    except Exception as e:
        logger.warning("Preguntas relevantes: no se pudieron elegir (%s); la ficha usa el orden de siempre", e)
        return []


@dataclass
class Grupo:
    clave: str                 # identificador estable del grupo (uuid de la entidad base)
    nombre: str
    descripcion: str
    n: int                     # cuántas personas tiene (el grupo + sus variantes)


@dataclass
class GrupoAsignado:
    grupo: Grupo
    segmento: Segmento
    encuestados: List[Encuestado] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    calidad: Optional[Dict] = None      # ¿la gente elegida se parece al segmento del que salió? (metricas.py)

    def resumen(self) -> Dict:
        return {
            "nombre": self.grupo.nombre, "personas": len(self.encuestados),
            "filtros_pedidos": self.segmento.filtros_pedidos, "filtros_aplicados": self.segmento.filtros_aplicados,
            "relajado": self.segmento.relajado, "casos_segmento": len(self.segmento.ids),
            "avisos": self.segmento.avisos + self.avisos,
            "calidad": self.calidad,
        }


class Asignacion:
    """Resultado de elegir encuestados reales para una simulación (sin repetir a nadie)."""

    def __init__(self, fuente: Fuente, banco: Banco, por_grupo: Dict[str, GrupoAsignado],
                 deteccion: Optional[Deteccion] = None):
        self.fuente = fuente
        self.banco = banco
        self.por_grupo = por_grupo
        self.deteccion = deteccion

    def de_grupo(self, clave: str) -> List[Encuestado]:
        g = self.por_grupo.get(clave)
        return list(g.encuestados) if g else []

    @property
    def encuestados(self) -> List[Encuestado]:
        return [e for g in self.por_grupo.values() for e in g.encuestados]

    def reparto(self) -> Dict:
        todos = self.encuestados
        n = len(todos) or 1
        sexo = Counter(e.sexo or "?" for e in todos)
        tramo = Counter(e.tramo or "?" for e in todos)
        region = Counter(e.region or "?" for e in todos)
        return {
            "n": len(todos),
            "sexo": {k: round(v / n * 100) for k, v in sexo.most_common()},
            "edad": {t: round(tramo.get(t, 0) / n * 100) for t in TRAMOS if tramo.get(t)},
            "region": {k: round(v / n * 100) for k, v in region.most_common(6)},
        }

    def calidad(self) -> Dict:
        """Resumen de la comprobación de cada grupo: ¿se ha deformado o aplanado a alguien al elegir?"""
        evaluados = [g.calidad for g in self.por_grupo.values() if g.calidad]
        avisos = [a for q in evaluados for a in q["avisos"]]
        return {"grupos_evaluados": len(evaluados), "representativa": not avisos, "avisos": avisos}

    def resumen(self) -> Dict:
        estudios = sorted({e.estudio for e in self.encuestados})
        grupos = [g.resumen() for g in self.por_grupo.values()]
        return {
            "fuente": self.fuente.nombre, "fuente_id": self.fuente.id, "cita": self.fuente.cita,
            "pais": self.fuente.pais, "pais_nombre": self.fuente.pais_nombre,
            "uso_interno": self.fuente.uso_interno, "estudios": estudios,
            "etiqueta_region": self.fuente.etiqueta_region,
            "pais_decidido_por": self.deteccion.origen if self.deteccion else "pedido",
            "pais_motivo": self.deteccion.motivo if self.deteccion else "",
            "grupos": grupos, "relajado": any(g["relajado"] for g in grupos),
            "avisos": [a for g in grupos for a in g["avisos"]],
            "reparto": self.reparto(),
            "calidad": self.calidad(),
        }


def asignar_por_grupos(grupos: List[Grupo], general: str = "", llm: Optional[Callable[[str], str]] = None,
                       pais: Optional[str] = None, pregunta: str = "", rng: Optional[random.Random] = None,
                       fuente: Optional[Fuente] = None, deteccion: Optional[Deteccion] = None) -> Optional[Asignacion]:
    """
    Elige los encuestados de cada grupo. Devuelve None si no hay país claro o no hay banco de ese país (entonces el
    público se genera como siempre). `fuente` fuerza una fuente concreta y se salta la detección del país.
    """
    grupos = [g for g in grupos if g.n > 0]
    if not grupos:
        return None
    if fuente is None:
        deteccion = deteccion or detectar(pais, pregunta, general, llm)
        fuente = deteccion.fuente
    if fuente is None or not tiene_banco(fuente):
        return None

    banco = abrir_banco(fuente)
    filtros = traducir_grupos(
        [{"clave": g.clave, "nombre": g.nombre, "descripcion": g.descripcion} for g in grupos], general, llm, fuente)

    segmentos = {g.clave: banco.segmento(filtros.get(g.clave) or {}) for g in grupos}
    # Los grupos con menos gente en la encuesta eligen primero: los comunes no deben agotarles el segmento
    orden = sorted(grupos, key=lambda g: len(segmentos[g.clave].ids))
    usados: set = set()
    elegidos: Dict[str, GrupoAsignado] = {}
    for g in orden:
        seg = segmentos[g.clave]
        ids = banco.muestrear(seg, g.n, excluidos=usados, rng=rng)
        avisos: List[str] = []
        if len(ids) < g.n:      # segmento agotado: se completa con el resto de adultos del país, sin repetir
            propios = len(ids)
            resto = banco.segmento({}, minimo=0)
            ids += banco.muestrear(resto, g.n - propios, excluidos=usados | set(ids), rng=rng)
            avisos.append(f"«{g.nombre}»: el segmento solo tenía {propios} personas distintas para {g.n}; "
                          "se completó con población general.")
        usados.update(ids)
        calidad = None
        if not avisos and len(ids) >= 5:          # solo si todo salió del segmento: si se completó, ya lo dice el aviso
            try:
                campos = CAMPOS_CALIDAD + ("edad",)
                calidad = calidad_de_grupo(banco.columnas(ids, campos), banco.columnas(seg.ids, campos), seg.pesos)
            except Exception:
                calidad = None
        elegidos[g.clave] = GrupoAsignado(g, seg, [banco.encuestado(i) for i in ids], avisos, calidad)
    return Asignacion(fuente, banco, {g.clave: elegidos[g.clave] for g in grupos}, deteccion)


def asignar(n: int, descripcion: str = "", llm: Optional[Callable[[str], str]] = None,
            rng: Optional[random.Random] = None, banco: Optional[Banco] = None,
            fuente: Optional[Fuente] = None) -> Optional[Asignacion]:
    """Atajo de UN solo grupo (todo el público) sobre la primera fuente disponible, sin detectar el país."""
    if fuente is None:
        quedan = disponibles()
        fuente = quedan[0] if quedan else None
    return asignar_por_grupos([Grupo("publico", "Público", descripcion, n)], descripcion, llm, rng=rng, fuente=fuente)


def cita_de_simulacion(simulation_id: str) -> str:
    """Cita con los estudios usados en una simulación ('' si no se anclaron datos reales). Lee el resumen guardado."""
    datos = resumen_de_simulacion(simulation_id)
    if not datos:
        return ""
    cita = datos.get("cita") or "Fuente de datos: CIS"
    estudios = datos.get("estudios") or []
    return f"{cita} (estudio {', '.join(estudios)})" if estudios else cita


def resumen_de_simulacion(simulation_id: str) -> Optional[Dict]:
    base = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
    for nombre in (RESUMEN, RESUMEN_ANTIGUO):
        ruta = os.path.join(base, nombre)
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    return None


__all__ = ["FUENTES", "Fuente", "Grupo", "Asignacion", "Banco", "Encuestado", "RESUMEN", "modo_activo",
           "banco_existe", "asignar_por_grupos", "asignar", "construir_ficha", "hechos_memoria", "genero_oasis",
           "cita_de_simulacion", "resumen_de_simulacion", "preguntas_relevantes", "disponibles", "fuente_de_pais", "registrar", "ruta_banco",
           "tiene_banco", "abrir_banco", "detectar"]
