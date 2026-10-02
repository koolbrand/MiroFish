"""Bancos SINTÉTICOS para los tests: personas inventadas, jamás datos reales de ninguna encuesta."""

import random

from app.services.poblacion import banco as B
from app.services.poblacion.fuentes import Fuente, olvidar, registrar
from app.services.poblacion.vocabulario import tramo_de_edad

PREGUNTAS_NO_POL = [
    ("¿Cuánto confía en sus vecinos?", ["Mucho", "Algo", "Poco"]),
    ("¿Con qué frecuencia hace deporte?", ["A diario", "Algún día", "Nunca"]),
    ("¿Cómo valora su salud?", ["Buena", "Regular", "Mala"]),
]
PREGUNTAS_POL = [("¿A qué partido votaría?", ["Partido A", "Partido B"]),
                 ("¿Dónde se sitúa en la escala de ideología?", ["Izquierda", "Centro", "Derecha"])]

REGIONES_ES_TEST = ["Madrid", "Galicia", "Cataluña", "Andalucía"]
# Provincias de cada región del banco sintético (la provincia sale de la región, como en la encuesta real)
PROVINCIAS_ES_TEST = {"Madrid": ["Madrid"], "Galicia": ["Pontevedra", "Coruña (A)"], "Cataluña": ["Barcelona"],
                      "Andalucía": ["Sevilla"]}
REGIONES_US_TEST = ["Texas", "Ohio", "California", "Florida"]


def crear_banco(path: str, n: int = 120, semilla: int = 7, fuente_id: str = "cis", pais: str = "ES",
                regiones=None, sitlab_mujeres=None) -> str:
    """`sitlab_mujeres`: si se da, es la lista de situaciones laborales de las mujeres de 25–64 (para que un país
    sintético tenga una distribución distinta de otro y se pueda comprobar que no se mezclan)."""
    rng = random.Random(semilla)
    regiones = regiones or REGIONES_ES_TEST
    conn = B.abrir(path)
    B.crear_esquema(conn, fuente_id, pais)
    conn.execute("INSERT INTO estudios VALUES ('9001','Estudio sintético A','2026-01')")
    conn.execute("INSERT INTO estudios VALUES ('9002','Estudio sintético B','2026-02')")
    for i in range(n):
        edad = rng.randint(18, 85)
        sexo = rng.choice(["Hombre", "Mujer"])
        estudio = "9001" if i % 2 == 0 else "9002"
        if sitlab_mujeres and sexo == "Mujer" and 25 <= edad <= 64:
            sitlab = rng.choice(sitlab_mujeres)
        else:
            sitlab = "jubilado" if edad >= 66 else rng.choice(["trabaja", "parado", "estudiante"])
        region = rng.choice(regiones)
        provincia = rng.choice(PROVINCIAS_ES_TEST.get(region, ["Subregión X"]))
        cur = conn.execute(
            "INSERT INTO encuestados (estudio,sexo,edad,tramo,region,subregion,tamuni,estudios,sitlab,estcivil,peso) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (estudio, sexo, edad, tramo_de_edad(edad), region, provincia,
             rng.choice(["rural", "pequeño", "mediano", "grande"]),
             rng.choice(["primarios", "secundarios", "universitarios"]), sitlab,
             rng.choice(["soltero", "casado"]), rng.uniform(0.4, 2.5)),
        )
        for preguntas, pol in ((PREGUNTAS_POL, 1), (PREGUNTAS_NO_POL, 0)):   # políticas primero a propósito
            for q, opciones in preguntas:
                conn.execute("INSERT INTO respuestas VALUES (?,?,?,?)", (cur.lastrowid, q, rng.choice(opciones), pol))
    conn.commit()
    conn.close()
    return path


def registrar_pais_sintetico(directorio, fuente_id="gss", pais="US", pais_nombre="Estados Unidos", nombre="GSS",
                             regiones=tuple(REGIONES_US_TEST), etiqueta_region="Estado", n=120, semilla=11,
                             sitlab_mujeres=None, licencia="solo_investigacion") -> Fuente:
    """Registra una segunda fuente (de otro país) con su banco sintético en `directorio`. Hay que `olvidar` después."""
    f = registrar(Fuente(id=fuente_id, pais=pais, pais_nombre=pais_nombre, nombre=nombre, nombre_largo=nombre,
                         fichero=f"banco_{fuente_id}.sqlite", regiones=tuple(regiones),
                         etiqueta_region=etiqueta_region, licencia=licencia))
    crear_banco(str(directorio / f.fichero), n=n, semilla=semilla, fuente_id=fuente_id, pais=pais,
                regiones=list(regiones), sitlab_mujeres=sitlab_mujeres)
    return f


__all__ = ["crear_banco", "registrar_pais_sintetico", "olvidar"]
