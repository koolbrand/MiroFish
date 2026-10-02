"""Vocabulario cerrado de la sociodemografía del banco (lo comparten el constructor y el filtro)."""

SEXOS = ("Hombre", "Mujer")
TRAMOS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+")
TAMUNI = ("rural", "pequeño", "mediano", "grande")           # <2.000 · <10.000 · <100.000 · ≥100.000
ESTUDIOS = ("sin_estudios", "primarios", "secundarios", "fp", "universitarios")
SITLAB = ("trabaja", "parado", "jubilado", "estudiante", "labores_hogar", "otra")
ESTCIVIL = ("soltero", "casado", "pareja", "viudo", "separado_divorciado")
CCAA = (
    "Andalucía", "Aragón", "Asturias", "Baleares", "Canarias", "Cantabria", "Castilla y León",
    "Castilla-La Mancha", "Cataluña", "Comunidad Valenciana", "Extremadura", "Galicia", "Madrid",
    "Murcia", "Navarra", "País Vasco", "La Rioja", "Ceuta", "Melilla",
)

# Campos filtrables → valores válidos (las listas son los valores admitidos; edad_min/edad_max son enteros)
CAMPOS_LISTA = {
    "sexo": SEXOS, "tramo": TRAMOS, "tamuni": TAMUNI, "estudios": ESTUDIOS,
    "sitlab": SITLAB, "estcivil": ESTCIVIL, "ccaa": CCAA,
}
CAMPOS_EDAD = ("edad_min", "edad_max")

# Orden en que se relajan los filtros cuando el segmento queda corto (lo más accesorio primero)
ORDEN_RELAJAR = ("tamuni", "estcivil", "ccaa", "estudios", "sitlab", "sexo", "tramo", "edad_min", "edad_max")

ETIQUETAS = {
    "sexo": "Sexo", "edad": "Edad", "ccaa": "Comunidad autónoma", "provincia": "Provincia",
    "tamuni": "Tamaño del municipio", "estudios": "Estudios", "sitlab": "Situación laboral",
    "estcivil": "Estado civil",
}
ETIQUETAS_VALOR = {
    "sin_estudios": "sin estudios", "primarios": "estudios primarios", "secundarios": "estudios secundarios",
    "fp": "formación profesional", "universitarios": "estudios universitarios",
    "trabaja": "trabaja", "parado": "en paro", "jubilado": "jubilado/a o pensionista",
    "estudiante": "estudiante", "labores_hogar": "labores del hogar", "otra": "otra situación",
    "soltero": "soltero/a", "casado": "casado/a", "pareja": "en pareja", "viudo": "viudo/a",
    "separado_divorciado": "separado/a o divorciado/a",
    "rural": "municipio rural (menos de 2.000 hab.)", "pequeño": "municipio pequeño (2.000–10.000 hab.)",
    "mediano": "ciudad mediana (10.000–100.000 hab.)", "grande": "gran ciudad (más de 100.000 hab.)",
}


def tramo_de_edad(edad):
    if edad is None:
        return None
    e = int(edad)
    if e < 18:
        return None
    for lim, nombre in ((24, "18-24"), (34, "25-34"), (44, "35-44"), (54, "45-54"), (64, "55-64")):
        if e <= lim:
            return nombre
    return "65+"
