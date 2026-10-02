"""Banco de encuestados reales (una encuesta oficial por fichero) en SQLite: lectura, filtrado y muestreo ponderado.

Cada fuente (CIS, y las que se añadan por país) tiene su propio fichero, construido OFFLINE por un script de
`scripts/poblacion/` y guardado FUERA del repo (ruta ignorada por git, `POBLACION_BANCOS_DIR`). Todos comparten este
esquema, así que el resto del sistema no sabe de qué país es cada banco. Aquí solo se lee. Nada se reidentifica ni se
cruza con otros datos.
"""

import math
import os
import random
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from .vocabulario import COLUMNAS_FILTRABLES, ORDEN_RELAJAR

if TYPE_CHECKING:
    from .fuentes import Fuente

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS estudios (id TEXT PRIMARY KEY, titulo TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS encuestados (
  id INTEGER PRIMARY KEY, estudio TEXT NOT NULL, sexo TEXT, edad INTEGER, tramo TEXT, region TEXT, subregion TEXT,
  tamuni TEXT, estudios TEXT, sitlab TEXT, estcivil TEXT, peso REAL NOT NULL DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS respuestas (
  enc_id INTEGER NOT NULL, pregunta TEXT NOT NULL, respuesta TEXT NOT NULL, politica INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_resp_enc ON respuestas(enc_id);
CREATE INDEX IF NOT EXISTS ix_enc_estudio ON encuestados(estudio);
"""

# Mínimo de casos para dar un segmento por bueno; por debajo se relajan los filtros (y se avisa)
MIN_CASOS = 30


@dataclass
class Encuestado:
    id: int
    estudio: str
    sexo: Optional[str]
    edad: Optional[int]
    tramo: Optional[str]
    region: Optional[str]
    subregion: Optional[str]
    tamuni: Optional[str]
    estudios: Optional[str]
    sitlab: Optional[str]
    estcivil: Optional[str]
    peso: float
    respuestas: List[Dict] = field(default_factory=list)   # [{pregunta, respuesta, politica}]


@dataclass
class Segmento:
    ids: List[int]
    pesos: List[float]
    filtros_pedidos: Dict
    filtros_aplicados: Dict
    relajado: bool
    avisos: List[str]


def abrir(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def crear_esquema(conn: sqlite3.Connection, fuente_id: str = "", pais: str = "") -> None:
    """Crea las tablas y, si se dice, deja escrito en el propio fichero de qué fuente y país es."""
    conn.executescript(SCHEMA)
    for k, v in (("fuente", fuente_id), ("pais", pais)):
        if v:
            conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, v))
    conn.commit()


class Banco:
    def __init__(self, path: str, fuente: Optional["Fuente"] = None):
        self.path = path
        self.fuente = fuente
        self._conn: Optional[sqlite3.Connection] = None

    # ---- disponibilidad -------------------------------------------------
    @staticmethod
    def disponible(path: Optional[str]) -> bool:
        if not path or not os.path.isfile(path):
            return False
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                n = conn.execute("SELECT COUNT(*) FROM encuestados").fetchone()[0]
            finally:
                conn.close()
            return n > 0
        except sqlite3.Error:
            return False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def estudios(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT e.id, e.titulo, e.fecha, (SELECT COUNT(*) FROM encuestados WHERE estudio = e.id) AS n "
            "FROM estudios e ORDER BY e.id"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- filtrado -------------------------------------------------------
    def _where(self, filtros: Dict, estudios: Optional[Sequence[str]]):
        cond, par = ["1=1"], []
        for campo in COLUMNAS_FILTRABLES:
            vals = filtros.get(campo)
            if vals:
                cond.append(f"{campo} IN ({','.join('?' * len(vals))})")
                par.extend(vals)
        if filtros.get("edad_min") is not None:
            cond.append("edad >= ?")
            par.append(int(filtros["edad_min"]))
        if filtros.get("edad_max") is not None:
            cond.append("edad <= ?")
            par.append(int(filtros["edad_max"]))
        if estudios:
            cond.append(f"estudio IN ({','.join('?' * len(estudios))})")
            par.extend(estudios)
        return " AND ".join(cond), par

    def _normalizados(self, filtros: Dict, estudios: Optional[Sequence[str]]):
        """Ids y pesos del segmento. Cada estudio pesa lo mismo: el peso se normaliza dentro de cada uno."""
        where, par = self._where(filtros, estudios)
        rows = self.conn.execute(
            f"SELECT id, estudio, peso FROM encuestados WHERE {where} AND edad >= 18", par
        ).fetchall()
        total = {}
        for r in rows:
            total[r["estudio"]] = total.get(r["estudio"], 0.0) + max(float(r["peso"] or 0), 0.0)
        ids, pesos = [], []
        for r in rows:
            t = total.get(r["estudio"]) or 0.0
            w = max(float(r["peso"] or 0), 0.0)
            if t > 0 and w > 0:
                ids.append(r["id"])
                pesos.append(w / t)
        return ids, pesos

    def segmento(self, filtros: Optional[Dict] = None, minimo: int = MIN_CASOS,
                 estudios: Optional[Sequence[str]] = None) -> Segmento:
        """Casos que cumplen los filtros; si son pocos, relaja uno a uno (ORDEN_RELAJAR) y lo dice."""
        pedidos = {k: v for k, v in (filtros or {}).items() if v not in (None, [], "")}
        aplicados = dict(pedidos)
        avisos: List[str] = []
        ids, pesos = self._normalizados(aplicados, estudios)
        for campo in ORDEN_RELAJAR:
            if len(ids) >= minimo:
                break
            if campo in aplicados:
                avisos.append(f"Segmento corto ({len(ids)} casos): se quita el filtro «{campo}».")
                aplicados.pop(campo)
                ids, pesos = self._normalizados(aplicados, estudios)
        if len(ids) < minimo:
            avisos.append(f"Ni sin filtros hay {minimo} casos: el banco solo tiene {len(ids)} adultos.")
        return Segmento(ids, pesos, pedidos, aplicados, aplicados != pedidos, avisos)

    # ---- muestreo -------------------------------------------------------
    @staticmethod
    def muestrear(segmento: Segmento, n: int, excluidos: Optional[set] = None,
                  rng: Optional[random.Random] = None) -> List[int]:
        """n ids sin repetir, ponderados por peso (Efraimidis–Spirakis). `excluidos` evita repetir
        a quien ya salió en la misma simulación. Si hay menos casos que n, devuelve los que haya."""
        rng = rng or random.Random()
        excluidos = excluidos or set()
        claves = []
        for i, w in zip(segmento.ids, segmento.pesos):
            if i in excluidos or w <= 0:
                continue
            u = rng.random() or 1e-12
            claves.append((math.log(u) / w, i))      # mayor clave = antes; equivale a u^(1/w)
        claves.sort(reverse=True)
        return [i for _, i in claves[:n]]

    def encuestado(self, enc_id: int) -> Encuestado:
        r = self.conn.execute("SELECT * FROM encuestados WHERE id = ?", (enc_id,)).fetchone()
        if r is None:
            raise KeyError(enc_id)
        resp = self.conn.execute(
            "SELECT pregunta, respuesta, politica FROM respuestas WHERE enc_id = ? ORDER BY rowid", (enc_id,)
        ).fetchall()
        d = {k: r[k] for k in r.keys()}
        return Encuestado(respuestas=[dict(x) for x in resp], **d)

    def titulo_estudio(self, estudio: str) -> str:
        r = self.conn.execute("SELECT titulo FROM estudios WHERE id = ?", (estudio,)).fetchone()
        return (r["titulo"] if r and r["titulo"] else f"estudio {estudio}")
