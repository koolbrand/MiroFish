"""
Cifras de un texto y cuáles no tienen respaldo en las fuentes que se le dieron a quien lo escribió.

Sirve para medir si una persona simulada se inventa datos (`scripts/entrevista/evaluar_cifras.py`), no para filtrar
respuestas en producción: la memoria de la persona vive en el proceso de OASIS, no en Flask.

Detecta (y compara por valor: «78 %», «78 por ciento» y «tres reuniones» valen lo mismo que un «78» o un «3» de la memoria):
  · números en cifras: «78 %», «4.200», «1.200 hogares», «12,5», años y fechas («2026», «12 de marzo»);
  · «N de cada M» («tres de cada cuatro») y «la mitad de», «dos tercios», «tres cuartos»;
  · «ochenta por ciento» (número en letra + «por ciento»);
  · órdenes de magnitud sin cifra: «miles de», «cientos de», «centenares de», «decenas de», «millones de».
  · cantidades en letra del dos en adelante seguidas de algo que se cuenta: «cuatro días», «doscientas firmas», «dos reuniones».
No detecta un número compuesto en letra («mil doscientas firmas» solo se ve como «mil… firmas» si van seguidas), ni un
ordinal («la tercera vuelta»), ni un «un/una» (artículo). Una cifra verbal está respaldada solo si la misma expresión
aparece tal cual en las fuentes.
"""

import re
import unicodedata
from typing import Iterable, List

# 1.200 · 4.200,5 · 78 · 12,5   (el punto o el espacio duro solo separan miles cuando van seguidos de tres cifras)
_NUMERO = re.compile(r"(?<![\w.,])\d{1,3}(?:[.\u00a0\u202f]\d{3})+(?:,\d+)?(?![\w])|(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")

_UNO_A_DIEZ = r"(?:un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"
_NUMERO_EN_LETRA = (r"(?:cero|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|"
                    r"veinte|veinticinco|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|mil)")
# Del dos en adelante (un/una/uno son artículo en el habla corriente) y seguido de algo que se cuenta: «cuatro días»,
# «doscientas firmas», «cuarenta minutos». Solo cuenta como cifra si lo que se cuenta es una persona, una firma, un acto,
# dinero o un plazo: «tres cosas» o «dos veces» son lenguaje corriente.
_CANTIDAD_EN_LETRA = (r"(?:dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|veinte|treinta|"
                      r"cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|doscient[oa]s|trescient[oa]s|"
                      r"cuatrocient[oa]s|quinient[oa]s|mil)")
_COSA_CONTADA = (r"(?:firmas|adhesiones|apoyos|personas|vecinos|vecinas|familias|hogares|socios|socias|miembros|comerciantes|"
                 r"votantes|asistentes|euros|reuniones|asambleas|concentraciones|manifestaciones|encuestas|dias|semanas|"
                 r"meses|anos|horas|minutos)")   # sin tildes ni «ñ»: se busca sobre el texto en plano
_CANTIDAD = re.compile(rf"\b({_CANTIDAD_EN_LETRA})\s+{_COSA_CONTADA}\b")
_VALOR_EN_LETRA = {
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11,
    "doce": 12, "trece": 13, "catorce": 14, "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "mil": 1000,
    "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
    "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
}
_VERBAL = [
    re.compile(rf"\b{_NUMERO_EN_LETRA}\s+de\s+cada\s+\w+\b"),
    re.compile(r"\bla\s+mitad\s+de\s+(?:los|las|nosotros|nosotras|vosotros|ellos|ellas|la\s+gente|mis|nuestros|nuestras)\b"),
    re.compile(rf"\b(?:un\s+tercio|dos\s+tercios|un\s+cuarto|tres\s+cuartos|{_UNO_A_DIEZ}\s+quintos)\b"),
    re.compile(rf"\b{_NUMERO_EN_LETRA}\s+por\s+ciento\b"),
    re.compile(r"\b(?:miles|cientos|centenares|decenas|millones|millares)\s+de\b"),
]

# «Pregunta 2:», «P3)», «1.» o «2)» al empezar la línea: numeran la respuesta, no son una cifra
_NUMERACION = re.compile(r"(?m)^\s*(?:(?:pregunta|p)\s*)?\d{1,2}\s*[.):]\s+", re.IGNORECASE)


def _plano(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in texto if unicodedata.category(c) != "Mn"))


def _valor(token: str) -> str:
    """78 → «78», «1.200» → «1200», «12,5» → «12.5», «007» → «7»."""
    t = token.replace("\u00a0", "").replace("\u202f", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", t):
        t = t.replace(".", "")
    t = t.replace(",", ".")
    if "." in t:
        entero, dec = t.split(".", 1)
        dec = dec.rstrip("0")
        return f"{int(entero)}.{dec}" if dec else str(int(entero))
    return str(int(t))


def extraer_cifras(texto: str) -> List[str]:
    """Cifras del texto, en orden y sin repetir: valores normalizados para los números y la expresión para las verbales."""
    texto = _NUMERACION.sub("", str(texto or ""))
    vistas, cifras = set(), []
    for m in _NUMERO.finditer(texto):
        v = _valor(m.group(0))
        if v not in vistas:
            vistas.add(v)
            cifras.append(v)
    plano = _plano(texto)
    for m in _CANTIDAD.finditer(plano):                      # «cuatro días» → «4»: se compara por valor, como las cifras
        v = str(_VALOR_EN_LETRA[m.group(1)])
        if v not in vistas:
            vistas.add(v)
            cifras.append(v)
    for patron in _VERBAL:
        for m in patron.finditer(plano):
            v = m.group(0)
            if v not in vistas:
                vistas.add(v)
                cifras.append(v)
    return cifras


def cifras_sin_respaldo(respuesta: str, fuentes: Iterable[str]) -> List[str]:
    """Cifras de la respuesta que no aparecen en ninguna de las fuentes (perfil, memoria, texto base, la propia pregunta)."""
    fuentes = [str(f or "") for f in fuentes]
    numeros = {c for f in fuentes for c in extraer_cifras(f) if c[0].isdigit()}
    planas = [_plano(f) for f in fuentes]
    return [c for c in extraer_cifras(respuesta)
            if not (c in numeros if c[0].isdigit() else any(c in p for p in planas))]
