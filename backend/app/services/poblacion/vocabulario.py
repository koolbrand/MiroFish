"""Vocabulario cerrado de la sociodemografía del banco (lo comparten los constructores, el filtro y la ficha).

Es COMÚN a todos los países: sexo, tramo de edad, tamaño del municipio, estudios, situación laboral y estado civil se
normalizan a estas categorías al construir el banco de cada fuente, de modo que se pueda comparar una persona de España
con una de EE. UU. con las mismas palabras. Lo único que cambia de un país a otro es la REGIÓN (comunidad autónoma,
estado, provincia…): la lista de valores válidos la declara cada fuente (`fuentes.py`).
"""

SEXOS = ("Hombre", "Mujer")
TRAMOS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+")
TAMUNI = ("rural", "pequeño", "mediano", "grande")           # <2.000 · <10.000 · <100.000 · ≥100.000
ESTUDIOS = ("sin_estudios", "primarios", "secundarios", "fp", "universitarios")
SITLAB = ("trabaja", "parado", "jubilado", "estudiante", "labores_hogar", "otra")
ESTCIVIL = ("soltero", "casado", "pareja", "viudo", "separado_divorciado")

# Campos filtrables con lista de valores común a todos los países. «region» también es filtrable, pero sus valores
# válidos dependen de la fuente (ver `campos_lista`).
CAMPOS_COMUNES = {
    "sexo": SEXOS, "tramo": TRAMOS, "tamuni": TAMUNI, "estudios": ESTUDIOS,
    "sitlab": SITLAB, "estcivil": ESTCIVIL,
}
CAMPOS_EDAD = ("edad_min", "edad_max")
# Columnas del banco por las que se puede filtrar (el orden no importa; sí el nombre: son columnas de SQLite)
# («subregion» = provincia: no la propone el modelo al traducir un grupo, la pone el ALCANCE de la simulación cuando es local)
COLUMNAS_FILTRABLES = tuple(CAMPOS_COMUNES) + ("region", "subregion")

# Orden en que se relajan los filtros cuando el segmento queda corto (lo más accesorio primero)
ORDEN_RELAJAR = ("subregion", "tamuni", "estcivil", "region", "estudios", "sitlab", "sexo", "tramo", "edad_min", "edad_max")

ETIQUETAS = {
    "sexo": "Sexo", "edad": "Edad", "region": "Región", "subregion": "Provincia",
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


def campos_lista(regiones=()):
    """Campos filtrables → valores válidos, con las regiones de la fuente concreta."""
    campos = dict(CAMPOS_COMUNES)
    if regiones:
        campos["region"] = tuple(regiones)
    return campos


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
