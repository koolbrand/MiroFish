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
# Cuando el segmento está acotado por un LUGAR (alcance local o regional) el lugar es lo último que se suelta: se acepta un
# segmento más corto antes que mandar a un vecino de Extremadura a opinar de un café de Vigo
MIN_CASOS_LUGAR = 10
LUGAR = ("region",)


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
        self._tabla: Optional[Dict[int, Dict]] = None

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
                 estudios: Optional[Sequence[str]] = None, proteger: Sequence[str] = LUGAR,
                 minimo_lugar: int = MIN_CASOS_LUGAR) -> Segmento:
        """
        Casos que cumplen los filtros; si son pocos, relaja uno a uno (ORDEN_RELAJAR) y lo dice. Los campos de `proteger` (el
        lugar) se sueltan los últimos y, mientras se conserven, basta con `minimo_lugar` casos.
        """
        pedidos = {k: v for k, v in (filtros or {}).items() if v not in (None, [], "")}
        aplicados = dict(pedidos)
        avisos: List[str] = []
        ids, pesos = self._normalizados(aplicados, estudios)

        def objetivo() -> int:
            return min(minimo, minimo_lugar) if any(c in aplicados for c in proteger) else minimo

        def soltar(campo: str) -> None:
            nonlocal ids, pesos
            avisos.append(f"Segmento corto ({len(ids)} casos): se quita el filtro «{campo}».")
            aplicados.pop(campo)
            ids, pesos = self._normalizados(aplicados, estudios)

        for campo in ORDEN_RELAJAR:
            if len(ids) >= objetivo():
                break
            if campo in aplicados and campo not in proteger:
                soltar(campo)
        for campo in ORDEN_RELAJAR:                         # lo último, y solo si ni así se llega al mínimo
            if len(ids) >= objetivo():
                break
            if campo in aplicados:
                soltar(campo)
        if len(ids) < objetivo():
            avisos.append(f"Ni sin filtros hay {objetivo()} casos: el banco solo tiene {len(ids)} adultos.")
        elif len(ids) < minimo:
            avisos.append(f"Segmento acotado por lugar con pocos casos ({len(ids)}): se prefiere a mezclar con gente de otros sitios.")
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

    def columnas(self, ids: Sequence[int], campos: Sequence[str]) -> Dict[str, List]:
        """Valores de `campos` para esos ids (sin respuestas), en el mismo orden. Para medir la calidad de una muestra."""
        if self._tabla is None:
            cols = ("id", "sexo", "tramo", "region", "sitlab", "estudios", "edad")
            self._tabla = {r["id"]: dict(zip(cols[1:], tuple(r)[1:]))
                           for r in self.conn.execute(f"SELECT {','.join(cols)} FROM encuestados")}
        return {c: [self._tabla[i][c] for i in ids if i in self._tabla] for c in campos}

    def catalogo(self, min_cobertura: float = 0.1, politica: bool = False) -> List[str]:
        """Preguntas que contesta al menos `min_cobertura` de la gente del banco (las de uso general, no las baterías de un
        solo estudio). Sirve para elegir, según el tema de la simulación, qué respuestas van a la ficha. Por defecto, SIN las
        políticas (voto, ideología): solo entran cuando el tema es político (`politica=True`)."""
        total = self.conn.execute("SELECT COUNT(*) FROM encuestados").fetchone()[0] or 1
        donde = "" if politica else "WHERE politica = 0 "
        filas = self.conn.execute(
            f"SELECT pregunta, COUNT(*) c FROM respuestas {donde}GROUP BY pregunta HAVING c >= ? ORDER BY c DESC, pregunta",
            (int(total * min_cobertura),)).fetchall()
        return [r["pregunta"] for r in filas]

    def subregiones(self) -> List[str]:
        """Provincias presentes en el banco (para que el alcance local pueda nombrarlas con el texto exacto)."""
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT subregion FROM encuestados WHERE subregion IS NOT NULL AND subregion != '' ORDER BY 1")]

    def regiones_de(self, provincia: str) -> List[str]:
        """Región o regiones a las que pertenece una provincia según el propio banco."""
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT region FROM encuestados WHERE subregion = ? AND region IS NOT NULL", (provincia,))]

    def titulo_estudio(self, estudio: str) -> str:
        r = self.conn.execute("SELECT titulo FROM estudios WHERE id = ?", (estudio,)).fetchone()
        return (r["titulo"] if r and r["titulo"] else f"estudio {estudio}")
