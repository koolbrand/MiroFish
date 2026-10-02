"""Público con datos reales: cada persona simulada del público se ancla a un encuestado real y anónimo del CIS.

Uso interno de I+D hasta tener la autorización escrita del CIS (Orden PRE/3188/2008, art. 6).
Los microdatos no están en el repo: se leen de un SQLite en `POBLACION_BANCO_PATH`.
"""

import random
from collections import Counter
from typing import Callable, Dict, List, Optional

from ...config import Config
from .banco import BancoCIS, Encuestado, Segmento
from .ficha import construir_ficha, genero_oasis, hechos_memoria
from .filtros import traducir_publico
from .vocabulario import TRAMOS

FUENTE = "CIS"
CITA = "Fuente de datos: CIS"


def modo_activo(pedido: Optional[bool] = None) -> bool:
    """El interruptor de la interfaz manda; si no llega, lo que diga POBLACION_CIS. Sin banco, nunca."""
    quiere = Config.POBLACION_CIS if pedido is None else bool(pedido)
    return bool(quiere and BancoCIS.disponible(Config.POBLACION_BANCO_PATH))


def banco_existe() -> bool:
    return BancoCIS.disponible(Config.POBLACION_BANCO_PATH)


class Asignacion:
    """Resultado de elegir N encuestados reales para una simulación (sin repetir a nadie)."""

    def __init__(self, banco: BancoCIS, segmento: Segmento, encuestados: List[Encuestado]):
        self.banco = banco
        self.segmento = segmento
        self.encuestados = encuestados

    def reparto(self) -> Dict:
        n = len(self.encuestados) or 1
        sexo = Counter(e.sexo or "?" for e in self.encuestados)
        tramo = Counter(e.tramo or "?" for e in self.encuestados)
        ccaa = Counter(e.ccaa or "?" for e in self.encuestados)
        return {
            "n": len(self.encuestados),
            "sexo": {k: round(v / n * 100) for k, v in sexo.most_common()},
            "edad": {t: round(tramo.get(t, 0) / n * 100) for t in TRAMOS if tramo.get(t)},
            "region": {k: round(v / n * 100) for k, v in ccaa.most_common(6)},
        }

    def resumen(self) -> Dict:
        estudios = sorted({e.estudio for e in self.encuestados})
        return {
            "fuente": CITA,
            "estudios": estudios,
            "filtros_pedidos": self.segmento.filtros_pedidos,
            "filtros_aplicados": self.segmento.filtros_aplicados,
            "relajado": self.segmento.relajado,
            "casos_segmento": len(self.segmento.ids),
            "avisos": self.segmento.avisos,
            "reparto": self.reparto(),
        }


def asignar(n: int, descripcion: str = "", llm: Optional[Callable[[str], str]] = None,
            rng: Optional[random.Random] = None, banco: Optional[BancoCIS] = None) -> Asignacion:
    banco = banco or BancoCIS(Config.POBLACION_BANCO_PATH)
    filtros = traducir_publico(descripcion, llm)
    seg = banco.segmento(filtros)
    ids = banco.muestrear(seg, n, rng=rng)
    if len(ids) < n:      # segmento agotado: se completa con el resto de adultos, sin repetir
        propios = len(ids)
        resto = banco.segmento({}, minimo=0)
        ids += banco.muestrear(resto, n - propios, excluidos=set(ids), rng=rng)
        seg.avisos.append(f"El segmento solo tenía {propios} personas distintas para {n}: se completó con población general.")
    return Asignacion(banco, seg, [banco.encuestado(i) for i in ids])


def cita_de_simulacion(simulation_id: str) -> str:
    """Lee `poblacion_cis.json` de la simulación y devuelve la cita con los estudios usados ('' si no hay)."""
    import json
    import os
    ruta = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id, "poblacion_cis.json")
    if not os.path.isfile(ruta):
        return ""
    with open(ruta, encoding="utf-8") as f:
        estudios = json.load(f).get("estudios") or []
    return f"{CITA} (estudio {', '.join(estudios)})" if estudios else CITA


__all__ = ["FUENTE", "CITA", "modo_activo", "banco_existe", "asignar", "Asignacion", "construir_ficha",
           "hechos_memoria", "genero_oasis", "BancoCIS"]
