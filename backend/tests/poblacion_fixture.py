"""Banco SINTÉTICO para los tests: personas inventadas, jamás datos reales del CIS."""

import random

from app.services.poblacion import banco as B
from app.services.poblacion.vocabulario import tramo_de_edad

PREGUNTAS_NO_POL = [
    ("¿Cuánto confía en sus vecinos?", ["Mucho", "Algo", "Poco"]),
    ("¿Con qué frecuencia hace deporte?", ["A diario", "Algún día", "Nunca"]),
    ("¿Cómo valora su salud?", ["Buena", "Regular", "Mala"]),
]
PREGUNTAS_POL = [("¿A qué partido votaría?", ["Partido A", "Partido B"]),
                 ("¿Dónde se sitúa en la escala de ideología?", ["Izquierda", "Centro", "Derecha"])]


def crear_banco(path: str, n: int = 120, semilla: int = 7) -> str:
    rng = random.Random(semilla)
    conn = B.abrir(path)
    B.crear_esquema(conn)
    conn.execute("INSERT INTO estudios VALUES ('9001','Estudio sintético A','2026-01')")
    conn.execute("INSERT INTO estudios VALUES ('9002','Estudio sintético B','2026-02')")
    for i in range(n):
        edad = rng.randint(18, 85)
        estudio = "9001" if i % 2 == 0 else "9002"
        cur = conn.execute(
            "INSERT INTO encuestados (estudio,sexo,edad,tramo,ccaa,provincia,tamuni,estudios,sitlab,estcivil,peso) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (estudio, rng.choice(["Hombre", "Mujer"]), edad, tramo_de_edad(edad),
             rng.choice(["Madrid", "Galicia", "Cataluña", "Andalucía"]), "Provincia X",
             rng.choice(["rural", "pequeño", "mediano", "grande"]),
             rng.choice(["primarios", "secundarios", "universitarios"]),
             "jubilado" if edad >= 66 else rng.choice(["trabaja", "parado", "estudiante"]),
             rng.choice(["soltero", "casado"]), rng.uniform(0.4, 2.5)),
        )
        for preguntas, pol in ((PREGUNTAS_POL, 1), (PREGUNTAS_NO_POL, 0)):   # políticas primero a propósito
            for q, opciones in preguntas:
                conn.execute("INSERT INTO respuestas VALUES (?,?,?,?)", (cur.lastrowid, q, rng.choice(opciones), pol))
    conn.commit()
    conn.close()
    return path
