"""Registro de fuentes de datos reales: una encuesta oficial por país.

Añadir un país = una entrada aquí + un constructor offline (`scripts/poblacion/build_banco_*.py`) que deje un SQLite
con el esquema común de `banco.py` en `POBLACION_BANCOS_DIR/<fichero>`. El resto del sistema (detección del país,
asignación por grupos, ficha, prompt, interfaz, cita) no sabe de España: lee de aquí.

LICENCIAS (verificadas en páginas oficiales el 2-oct-2026; detalle y enlaces en `docs/estrategia-poblacion-por-pais.md`):
solo el CIS (y el INE) publican microdatos con reutilización comercial, y el CIS tiene además una Orden de 2008 que exige
autorización expresa para el uso comercial: dos textos que se contradicen. El resto (ESS, WVS/EVS, Latinobarómetro,
LAPOP, Eurobarómetro) es solo investigación; GSS y ANES no lo dicen. Por eso toda fuente nace como `solo_investigacion`
(uso interno de I+D) y solo pasa a `autorizada` cuando hay autorización ESCRITA de su titular; mientras tanto la
interfaz lo dice. `licencia_nota` guarda en una frase el estado de cada una.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ...config import Config
from .banco import Banco

LICENCIA_INVESTIGACION = "solo_investigacion"
LICENCIA_AUTORIZADA = "autorizada"

REGIONES_ES = (
    "Andalucía", "Aragón", "Asturias", "Baleares", "Canarias", "Cantabria", "Castilla y León",
    "Castilla-La Mancha", "Cataluña", "Comunidad Valenciana", "Extremadura", "Galicia", "Madrid",
    "Murcia", "Navarra", "País Vasco", "La Rioja", "Ceuta", "Melilla",
)


@dataclass(frozen=True)
class Fuente:
    id: str                       # 'cis'
    pais: str                     # ISO 3166-1 alfa-2: 'ES'
    pais_nombre: str              # en español, para la interfaz: 'España'
    nombre: str                   # 'CIS'
    nombre_largo: str
    fichero: str                  # nombre del SQLite dentro de POBLACION_BANCOS_DIR
    regiones: Tuple[str, ...]     # valores válidos del filtro «region» en esta fuente
    etiqueta_region: str          # cómo se llama la región en este país: 'Comunidad autónoma', 'Estado'…
    licencia: str = LICENCIA_INVESTIGACION
    licencia_nota: str = ""

    @property
    def cita(self) -> str:
        return f"Fuente de datos: {self.nombre}"

    @property
    def uso_interno(self) -> bool:
        return self.licencia != LICENCIA_AUTORIZADA


FUENTES: Dict[str, Fuente] = {}


def registrar(fuente: Fuente) -> Fuente:
    FUENTES[fuente.id] = fuente
    return fuente


def olvidar(fuente_id: str) -> None:
    FUENTES.pop(fuente_id, None)


registrar(Fuente(
    id="cis", pais="ES", pais_nombre="España", nombre="CIS",
    nombre_largo="Centro de Investigaciones Sociológicas", fichero="banco_cis.sqlite",
    regiones=REGIONES_ES, etiqueta_region="Comunidad autónoma",
    licencia_nota="Las condiciones de reutilización del CIS permiten el uso comercial citando la fuente; la Orden "
                  "PRE/3188/2008 (art. 6) exige autorización expresa. Pendiente de confirmación escrita del CIS.",
))


def ruta_banco(fuente: Fuente) -> str:
    """Dónde está el SQLite de esta fuente. El CIS conserva su variable propia (`POBLACION_BANCO_PATH`)."""
    if fuente.id == "cis" and Config.POBLACION_BANCO_PATH:
        return Config.POBLACION_BANCO_PATH
    return os.path.join(Config.POBLACION_BANCOS_DIR, fuente.fichero)


def tiene_banco(fuente: Fuente) -> bool:
    return Banco.disponible(ruta_banco(fuente))


def disponibles() -> List[Fuente]:
    """Fuentes con banco construido y con gente dentro, en el orden del registro."""
    return [f for f in FUENTES.values() if tiene_banco(f)]


def fuente_de_pais(pais: Optional[str]) -> Optional[Fuente]:
    """La fuente DISPONIBLE de un país (ISO alfa-2, sin distinguir mayúsculas), o None."""
    if not pais:
        return None
    pais = str(pais).strip().upper()
    for f in disponibles():
        if f.pais == pais:
            return f
    return None


def abrir_banco(fuente: Fuente) -> Banco:
    return Banco(ruta_banco(fuente), fuente)
