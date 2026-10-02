#!/usr/bin/env python3
"""Constructor OFFLINE del banco de encuestados del CIS.

Lee los ZIP de microdatos (MD3535, MD3571, MD3530, MD3505…), normaliza la sociodemografía común y guarda
TODAS las respuestas etiquetadas (texto de la pregunta → texto de la respuesta, sin NS/NC) en un SQLite.

    cd backend
    uv run --with pyreadstat --with pandas python scripts/poblacion/build_banco_cis.py ~/Downloads/MD35*.zip

Salida: `POBLACION_BANCO_PATH` (por defecto backend/data/poblacion/banco_cis.sqlite, ignorado por git).
⚠️ Los microdatos NUNCA van al repo ni a la imagen Docker. Uso interno de I+D hasta tener la autorización
escrita del CIS (Orden PRE/3188/2008, art. 6). No se cruza con nada ni se intenta reidentificar a nadie.
Cita obligada en cualquier salida: «Fuente de datos: CIS».
"""

import argparse
import os
import re
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.poblacion import banco as B                      # noqa: E402
from app.services.poblacion.vocabulario import CCAA, tramo_de_edad  # noqa: E402

TITULOS = {
    "3535": ("Encuesta sobre tendencias sociales V", "2026-01"),
    "3571": ("Barómetro de julio 2026", "2026-07"),
    "3530": ("Barómetro de noviembre 2025", "2025-11"),
    "3505": ("Barómetro de abril 2025", "2025-04"),
}

# Nombre de la variable en cada estudio. Se prueban en orden y sin distinguir mayúsculas; se pueden fijar
# a mano por estudio en MAPEOS_ESTUDIO tras mirar su codebook (los nombres cambian de un estudio a otro).
CANDIDATAS = {
    "sexo": ["SEXO"], "edad": ["EDAD"], "ccaa": ["CCAA"], "provincia": ["PROV", "PROVINCIA"],
    "tamuni": ["TAMUNI", "TAMUNI2"], "estudios": ["ESTUDIOS", "ESTUDIOS_REC", "NIVELESTUDIOS"],
    "sitlab": ["SITLAB", "SITLAB_REC", "RELLAB"], "estcivil": ["ECIVIL", "ESTCIVIL", "ESTADOCIVIL"],
    "peso": ["PESO", "PESOCCAA", "PESOSEXO", "PONDERA", "PESOFINAL"],
}
MAPEOS_ESTUDIO: Dict[str, Dict[str, str]] = {}

# Columnas que nunca son «una respuesta» (identificadores, técnicas, la propia sociodemografía)
EXCLUIR = re.compile(r"^(ESTUDIO|CUES|REGISTRO|ENTREV\w*|FECHA\w*|HORA\w*|DURACION|PESO\w*|PONDERA|CUESTION\w*|"
                     r"MUN|MUNI\w*|SECC\w*|DIST\w*|ID\w*|NUM\w*|TAMUNI\w*|CCAA|PROV\w*|SEXO|EDAD\w*)$", re.I)
SIN_RESPUESTA = re.compile(r"^(n\.?\s?s\.?|n\.?\s?c\.?|ns/nc|no sabe|no contesta|no recuerda|no procede|"
                           r"n\.?\s?p\.?|no mencionado|no aplicable|\s*)$", re.I)
POLITICA = re.compile(r"\b(partido|voto|votar|votaría|elecciones|ideolog\w*|izquierda|derecha|gobierno|presidente|"
                      r"pol[ií]tic\w*|ministr\w*|l[ií]der|parlament\w*|diputad\w*|oposici[oó]n|monarqu\w*|"
                      r"republic\w*|independen\w*|nacionalis\w*|inmigra\w*|constituci[oó]n)\b", re.I)


# ---------------------------------------------------------------- normalización (puro, sin pandas)
def _plano(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def norm_sexo(v) -> Optional[str]:
    p = _plano(v)
    return "Hombre" if p.startswith(("hombre", "varon")) else "Mujer" if p.startswith("mujer") else None


_CCAA_CLAVES = [
    ("andaluc", "Andalucía"), ("aragon", "Aragón"), ("asturias", "Asturias"), ("balear", "Baleares"),
    ("canarias", "Canarias"), ("cantabria", "Cantabria"), ("castilla y leon", "Castilla y León"),
    ("castilla-la mancha", "Castilla-La Mancha"), ("castilla la mancha", "Castilla-La Mancha"),
    ("catalu", "Cataluña"), ("valencia", "Comunidad Valenciana"), ("extremadura", "Extremadura"),
    ("galicia", "Galicia"), ("madrid", "Madrid"), ("murcia", "Murcia"), ("navarra", "Navarra"),
    ("pais vasco", "País Vasco"), ("euskadi", "País Vasco"), ("rioja", "La Rioja"), ("ceuta", "Ceuta"),
    ("melilla", "Melilla"),
]


def norm_ccaa(v) -> Optional[str]:
    p = _plano(v)
    for clave, nombre in _CCAA_CLAVES:
        if clave in p:
            return nombre
    return None


def norm_tamuni(v) -> Optional[str]:
    """Por el tope superior del tramo: «hasta 2.000» rural, «2.001 a 10.000» pequeño, «hasta 100.000» mediano."""
    p = _plano(v)
    nums = [int(n.replace(".", "")) for n in re.findall(r"\d[\d\.]*", p) if n.replace(".", "").isdigit()]
    if not nums:
        return None
    if re.search(r"\bmas de\b|\bmayor\b|\bmas\b", p) and len(nums) == 1:
        tope = nums[0] * 10
    else:
        tope = max(nums)
    return "rural" if tope <= 2000 else "pequeño" if tope <= 10000 else "mediano" if tope <= 100000 else "grande"


def norm_estudios(v) -> Optional[str]:
    p = _plano(v)
    if "sin estudios" in p or "analfabet" in p or "no sabe leer" in p:
        return "sin_estudios"
    if "primaria" in p or "primarios" in p or "1ª etapa" in p and "secund" not in p:
        return "primarios"
    if "profesional" in p or p.startswith("fp") or "grado medio" in p or "grado superior" in p and "universit" not in p:
        return "fp"
    if "superior" in p or "universit" in p or "licenciad" in p or "grado" in p or "doctor" in p or "diplomad" in p:
        return "universitarios"
    if "secundaria" in p or "bachiller" in p or "eso" in p:
        return "secundarios"
    return None


def norm_sitlab(v) -> Optional[str]:
    p = _plano(v)
    if "jubilad" in p or "pensionista" in p:
        return "jubilado"
    if "parad" in p or "desemple" in p or "primer empleo" in p:
        return "parado"
    if "estudiante" in p or "estudia" in p:
        return "estudiante"
    if "domestic" in p or "hogar" in p:
        return "labores_hogar"
    if "trabaja" in p or "ocupad" in p or "empleado" in p:
        return "trabaja"
    return "otra" if p.strip() else None


def norm_estcivil(v) -> Optional[str]:
    p = _plano(v)
    if "solter" in p:
        return "soltero"
    if "pareja" in p:
        return "pareja"
    if "casad" in p:
        return "casado"
    if "viud" in p:
        return "viudo"
    if "separad" in p or "divorciad" in p:
        return "separado_divorciado"
    return None


def es_politica(pregunta: str) -> bool:
    return bool(POLITICA.search(_plano(pregunta)))


def limpiar_pregunta(etiqueta: str) -> str:
    t = re.sub(r"^\s*[Pp]?\d+[A-Za-z]{0,2}\s*[\.\):\-–]*\s*", "", str(etiqueta or "")).strip()
    return t or str(etiqueta or "").strip()


def respuesta_valida(v) -> Optional[str]:
    if v is None:
        return None
    t = " ".join(str(v).split())
    if t.lower() == "nan" or SIN_RESPUESTA.match(t):
        return None
    return t[:300]


# ---------------------------------------------------------------- lectura
def _buscar(cols_por_plano: Dict[str, str], campo: str, estudio: str) -> Optional[str]:
    fijo = MAPEOS_ESTUDIO.get(estudio, {}).get(campo)
    for c in ([fijo] if fijo else CANDIDATAS[campo]):
        if c and c.lower() in cols_por_plano:
            return cols_por_plano[c.lower()]
    return None


def cargar_zip(zip_path: str, estudio: str, conn, verbose: bool = True) -> Dict:
    import pyreadstat  # solo en el constructor (uv run --with pyreadstat): no es dependencia del runtime
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as z:
            sav = [n for n in z.namelist() if n.lower().endswith(".sav")]
            if not sav:
                raise SystemExit(f"{zip_path}: no trae .sav (todos los estudios desde 2018 lo traen)")
            z.extract(sav[0], tmp)
        df, meta = pyreadstat.read_sav(os.path.join(tmp, sav[0]), apply_value_formats=True,
                                       formats_as_category=False)
    cols = {c.lower(): c for c in df.columns}
    var = {campo: _buscar(cols, campo, estudio) for campo in CANDIDATAS}
    faltan = [c for c in ("sexo", "edad") if not var[c]]
    if faltan:
        raise SystemExit(f"{zip_path}: no encuentro {faltan}. Mira el codebook y añade el nombre a MAPEOS_ESTUDIO.")
    etiquetas = dict(zip(meta.column_names, meta.column_labels))
    titulo, fecha = TITULOS.get(estudio, (f"Estudio {estudio}", ""))
    conn.execute("INSERT OR REPLACE INTO estudios VALUES (?,?,?)", (estudio, titulo, fecha))

    sociodemo = {v for v in var.values() if v}
    candidatas = []
    for c in df.columns:
        if c in sociodemo or EXCLUIR.match(str(c)):
            continue
        serie = df[c]
        if serie.dtype.kind in "fiu":            # numérica sin etiquetas: identificador o medida continua
            continue
        if serie.nunique(dropna=True) > 40:      # texto abierto
            continue
        candidatas.append(c)

    n = 0
    for row in df.to_dict("records"):
        try:
            edad = int(float(row[var["edad"]]))
        except (TypeError, ValueError):
            continue
        if edad < 18 or edad > 110:
            continue
        peso = 1.0
        if var["peso"]:
            try:
                peso = float(row[var["peso"]])
            except (TypeError, ValueError):
                peso = 1.0
            if not peso == peso or peso <= 0:
                peso = 1.0
        g = lambda campo, f: f(row[var[campo]]) if var[campo] else None  # noqa: E731
        prov = row[var["provincia"]] if var["provincia"] else None
        cur = conn.execute(
            "INSERT INTO encuestados (estudio,sexo,edad,tramo,ccaa,provincia,tamuni,estudios,sitlab,estcivil,peso) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (estudio, g("sexo", norm_sexo), edad, tramo_de_edad(edad), g("ccaa", norm_ccaa),
             (str(prov) if prov not in (None, "") and str(prov) != "nan" else None),
             g("tamuni", norm_tamuni), g("estudios", norm_estudios), g("sitlab", norm_sitlab),
             g("estcivil", norm_estcivil), peso),
        )
        eid = cur.lastrowid
        for c in candidatas:
            r = respuesta_valida(row[c])
            if r is None:
                continue
            p = limpiar_pregunta(etiquetas.get(c) or c)
            conn.execute("INSERT INTO respuestas VALUES (?,?,?,?)", (eid, p, r, 1 if es_politica(p) else 0))
        n += 1
    conn.commit()
    if verbose:
        print(f"  {estudio}: {n} encuestados, {len(candidatas)} preguntas candidatas, variables: "
              + ", ".join(f"{k}={v}" for k, v in var.items() if v))
    return {"estudio": estudio, "encuestados": n, "preguntas": len(candidatas), "variables": var}


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zips", nargs="+")
    ap.add_argument("--salida", default=os.environ.get("POBLACION_BANCO_PATH") or str(
        Path(__file__).resolve().parents[2] / "data" / "poblacion" / "banco_cis.sqlite"))
    ap.add_argument("--reemplazar", action="store_true", help="borra el banco existente antes de construir")
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    if a.reemplazar and os.path.exists(a.salida):
        os.remove(a.salida)
    conn = B.abrir(a.salida)
    B.crear_esquema(conn)
    for z in a.zips:
        m = re.search(r"MD?(\d{4})", os.path.basename(z), re.I)
        if not m:
            raise SystemExit(f"No saco el número de estudio del nombre {z!r} (esperaba algo como MD3535.zip)")
        estudio = m.group(1)
        conn.execute("DELETE FROM respuestas WHERE enc_id IN (SELECT id FROM encuestados WHERE estudio=?)", (estudio,))
        conn.execute("DELETE FROM encuestados WHERE estudio=?", (estudio,))
        cargar_zip(z, estudio, conn)
    print(f"Banco en {a.salida} ({os.path.getsize(a.salida) / 1e6:.1f} MB). No lo subas a git ni a la imagen Docker.")


if __name__ == "__main__":
    main()
