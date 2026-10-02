"""Medidas para comprobar que la gente elegida de una encuesta no queda aplanada ni deformada.

La evidencia (Park et al. 2024; Bisbee et al. 2024; Wang et al. 2025) pide medir la POBLACIÓN, no solo a cada persona:
distancia entre distribuciones (Jensen–Shannon), dispersión dentro del grupo (un modelo tiende a colapsar hacia el
promedio) y cuánto de lo observado es solo ruido de muestreo. Todo son funciones puras, sin LLM ni red.
"""

import math
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence

CAMPOS_CALIDAD = ("sexo", "tramo", "region", "sitlab", "estudios")


def distribucion(valores: Iterable, pesos: Optional[Sequence[float]] = None) -> Dict[str, float]:
    """Proporciones (suman 1). Los valores vacíos (None) no cuentan."""
    acc: Dict = {}
    vals = list(valores)
    ws = list(pesos) if pesos is not None else [1.0] * len(vals)
    for v, w in zip(vals, ws):
        if v is None or w is None or w <= 0:
            continue
        acc[v] = acc.get(v, 0.0) + float(w)
    total = sum(acc.values())
    return {k: x / total for k, x in acc.items()} if total > 0 else {}


def jsd(p: Dict, q: Dict) -> float:
    """Jensen–Shannon en base 2: 0 = iguales, 1 = disjuntas. Acepta pesos sin normalizar."""
    claves = set(p) | set(q)
    sp, sq = sum(p.values()) or 1.0, sum(q.values()) or 1.0
    P = {k: p.get(k, 0) / sp for k in claves}
    Q = {k: q.get(k, 0) / sq for k in claves}
    M = {k: (P[k] + Q[k]) / 2 for k in claves}
    kl = lambda A, B: sum(A[k] * math.log2(A[k] / B[k]) for k in claves if A[k] > 0)  # noqa: E731
    return max(0.0, (kl(P, M) + kl(Q, M)) / 2)


def wasserstein1(p: Dict, q: Dict, orden: Sequence) -> float:
    """Distancia de Wasserstein-1 entre dos distribuciones sobre categorías ORDENADAS, normalizada a 0–1.
    Mira cuánto hay que mover la masa, así que distingue «un escalón de diferencia» de «el extremo opuesto»."""
    if len(orden) < 2:
        return 0.0
    sp, sq = sum(p.values()) or 1.0, sum(q.values()) or 1.0
    acum, total = 0.0, 0.0
    for c in orden[:-1]:
        acum += p.get(c, 0) / sp - q.get(c, 0) / sq
        total += abs(acum)
    return total / (len(orden) - 1)


def entropia_normalizada(p: Dict) -> float:
    """0 = todos iguales, 1 = reparto uniforme. Mide cuánta variedad hay dentro de un grupo."""
    xs = [v for v in p.values() if v > 0]
    if len(xs) < 2:
        return 0.0
    s = sum(xs)
    return -sum(v / s * math.log2(v / s) for v in xs) / math.log2(len(xs))


def desviacion(valores: Sequence[float]) -> float:
    n = len(valores)
    if n < 2:
        return 0.0
    m = sum(valores) / n
    return math.sqrt(sum((v - m) ** 2 for v in valores) / (n - 1))


Z_ALERTA = 3.09        # cola de 0,1 %: con ~6 medidas por grupo, una falsa alarma cada ~150 grupos


def umbral_ruido(k: int, n: int, z: float = Z_ALERTA) -> float:
    """JSD (base 2) que se espera por puro azar al sacar n personas de una población con k categorías.
    Para diferencias pequeñas, JSD ≈ χ²/(8 n ln 2) con k−1 grados de libertad; el cuantil de la χ² sale de la
    aproximación de Wilson–Hilferty (la cola de una χ² con pocos grados NO es normal: por eso no media + 3 σ)."""
    if n <= 0 or k < 2:
        return 0.0
    nu = k - 1
    chi2 = nu * (1 - 2 / (9 * nu) + z * math.sqrt(2 / (9 * nu))) ** 3
    return chi2 / (8 * n * math.log(2))


def calidad_de_grupo(muestra: Dict[str, List], referencia: Dict[str, List], pesos_ref: Sequence[float],
                     z: float = Z_ALERTA) -> Dict:
    """
    Compara las personas elegidas con el segmento del que salieron. `muestra`/`referencia`: campo → lista de valores
    (y 'edad' → números). Una distancia por encima del ruido esperable, o una edad con mucha menos dispersión que su
    segmento, significa que el muestreo está deformando o aplanando al grupo.
    """
    n = len(next(iter(muestra.values()), []))
    campos, avisos = {}, []
    for c in CAMPOS_CALIDAD:
        ref = distribucion(referencia.get(c, []), pesos_ref)
        mue = distribucion(muestra.get(c, []))
        if not ref or not mue:
            continue
        d, tope = jsd(mue, ref), umbral_ruido(len(ref), n, z)
        campos[c] = {"jsd": round(d, 4), "ruido_esperable": round(tope, 4), "dentro_del_ruido": d <= tope}
        if d > tope:
            avisos.append(f"«{c}»: la muestra se aleja del segmento más de lo que explica el azar.")
    res: Dict = {"n": n, "campos": campos}
    edades, edades_ref = muestra.get("edad") or [], referencia.get("edad") or []
    if n >= 8 and len(edades_ref) >= 2:
        sd_ref = desviacion(edades_ref) or 1e-9
        ratio = desviacion(edades) / sd_ref
        minimo = max(0.0, 1 - z / math.sqrt(2 * n))                  # error típico de una desviación: 1/√(2n)
        res["dispersion_edad"] = {"razon": round(ratio, 3), "minimo_aceptable": round(minimo, 3), "aplanada": ratio < minimo}
        if ratio < minimo:
            avisos.append("«edad»: el grupo quedó con menos variedad de edades que su segmento (aplanado).")
    res["avisos"] = avisos
    res["representativa"] = not avisos
    return res


def moda_por_celda(filas: Sequence[Dict], campo: str, celda: Sequence[str] = ("sexo", "tramo")) -> Dict:
    """Línea base SIN modelo: la respuesta más común de cada celda demográfica. Si un LLM no la supera, no aporta."""
    por: Dict = {}
    for f in filas:
        if f.get(campo) is None:
            continue
        por.setdefault(tuple(f.get(c) for c in celda), Counter())[f[campo]] += 1
    return {k: c.most_common(1)[0][0] for k, c in por.items()}
