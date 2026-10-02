#!/usr/bin/env python3
"""Medición de fidelidad: ¿cuánto mejora anclar a una persona a sus datos reales?

Con ~150 encuestados de un estudio del banco se esconden 8–10 preguntas de actitud y se le pide al LLM que las
responda en dos condiciones:
  (a) solo sociodemografía
  (b) sociodemografía + el resto de sus respuestas reales (las escondidas no aparecen en ninguna)
y se compara con lo que respondió cada persona: acierto individual y distancia entre la distribución prevista y
la real (Jensen–Shannon, base 2, con pesos). Líneas base: la moda de su grupo demográfico (sexo × tramo de edad,
sin contarse a sí mismo) y el azar.

    cd backend
    uv run python scripts/poblacion/fidelidad.py --estudio 3535 --estimar        # solo calcula el coste
    uv run python scripts/poblacion/fidelidad.py --estudio 3535 --ejecutar       # lanza (cuesta dinero real)

Referencia: Park et al. (Stanford 2024, arXiv 2411.10109): 74 % con solo demografía, 82 % con encuesta y 86 % con
encuesta y entrevista, frente a lo que la misma persona repite a las dos semanas. Otro estudio (arXiv 2509.19088)
avisa de que, persona a persona y ante estímulos nuevos, solo se llega a r = 0,20: se vende como ensayo, no como
predicción. Uso interno de I+D. Fuente de datos: CIS.
"""

import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import Config                                  # noqa: E402
from app.services.poblacion.banco import BancoCIS               # noqa: E402
from app.services.poblacion.ficha import lineas_sociodemografia, _recortar  # noqa: E402

# MiniMax-M3 (producción): 0,30 $/M entrada · 1,20 $/M salida
PRECIO_ENTRADA, PRECIO_SALIDA = 0.30 / 1e6, 1.20 / 1e6
SALIDA_ESTIMADA = 1500     # tokens de salida por llamada (modelo de razonamiento: se razona antes de responder)
CHARS_POR_TOKEN = 3.6


# ---------------------------------------------------------------- métricas (puras)
def jsd(p: Dict[str, float], q: Dict[str, float]) -> float:
    """Jensen–Shannon en base 2 (0 = iguales, 1 = disjuntas) entre dos distribuciones sobre las mismas claves."""
    claves = set(p) | set(q)
    sp, sq = sum(p.values()) or 1.0, sum(q.values()) or 1.0
    P = {k: p.get(k, 0) / sp for k in claves}
    Q = {k: q.get(k, 0) / sq for k in claves}
    M = {k: (P[k] + Q[k]) / 2 for k in claves}
    kl = lambda A, B: sum(A[k] * math.log2(A[k] / B[k]) for k in claves if A[k] > 0)  # noqa: E731
    return max(0.0, (kl(P, M) + kl(Q, M)) / 2)


def distribucion(respuestas: List[Optional[str]], pesos: List[float], opciones: List[str]) -> Dict[str, float]:
    d = {o: 0.0 for o in opciones}
    for r, w in zip(respuestas, pesos):
        if r in d:
            d[r] += w
    return d


# ---------------------------------------------------------------- preparación
def cargar_muestra(banco: BancoCIS, estudio: str, n: int, semilla: int):
    ids = [r[0] for r in banco.conn.execute(
        "SELECT id FROM encuestados WHERE estudio=? AND edad>=18 ORDER BY id", (estudio,)).fetchall()]
    random.Random(semilla).shuffle(ids)
    return [banco.encuestado(i) for i in ids[:n]]


def elegir_preguntas(muestra, cuantas: int = 10, min_cobertura: float = 0.8):
    """Preguntas de actitud NO políticas, respondidas por casi todos, con 3–7 opciones y sin una moda aplastante."""
    por_p = defaultdict(list)
    for e in muestra:
        for r in e.respuestas:
            if not r["politica"]:
                por_p[r["pregunta"]].append(r["respuesta"])
    cand = []
    for q, rs in por_p.items():
        c = Counter(rs)
        cobertura = len(rs) / len(muestra)
        if cobertura >= min_cobertura and 3 <= len(c) <= 7 and max(c.values()) / len(rs) <= 0.8:
            entropia = -sum(v / len(rs) * math.log2(v / len(rs)) for v in c.values())
            cand.append((entropia, q, sorted(c)))
    cand.sort(reverse=True)
    return [(q, ops) for _, q, ops in cand[:cuantas]]


def prompt_persona(e, ocultas: set, con_respuestas: bool, preguntas) -> str:
    partes = ["Eres una persona real que respondió a una encuesta del CIS en España. Datos:"]
    partes += [f"- {l}" for l in lineas_sociodemografia(e)]
    if con_respuestas:
        previas = [r for r in e.respuestas if r["pregunta"] not in ocultas]
        previas.sort(key=lambda r: r["politica"])
        if previas:
            partes.append("\nLo que ya respondiste en la encuesta:")
            partes += [f"- {_recortar(r['pregunta'], 140)} → {_recortar(r['respuesta'], 120)}" for r in previas[:60]]
    partes.append("\nAhora responde cada pregunta como lo haría esta persona, eligiendo EXACTAMENTE una de las opciones:")
    for i, (q, ops) in enumerate(preguntas, 1):
        partes.append(f"{i}. {q} Opciones: {' | '.join(ops)}")
    partes.append('\nDevuelve SOLO un JSON {"1": "<opción>", "2": "<opción>", ...} sin texto alrededor.')
    return "\n".join(partes)


def estimar_coste(muestra, preguntas, salida_tokens: int = SALIDA_ESTIMADA) -> Dict:
    ocultas = {q for q, _ in preguntas}
    ent = sal = 0
    for e in muestra:
        for con in (False, True):
            ent += int(len(prompt_persona(e, ocultas, con, preguntas)) / CHARS_POR_TOKEN)
            sal += salida_tokens
    usd = ent * PRECIO_ENTRADA + sal * PRECIO_SALIDA
    return {"llamadas": len(muestra) * 2, "tokens_entrada": ent, "tokens_salida": sal, "usd": round(usd, 3)}


# ---------------------------------------------------------------- ejecución
def parsear(texto: str, preguntas) -> Dict[int, Optional[str]]:
    m = re.search(r"\{.*\}", texto or "", flags=re.S)
    out: Dict[int, Optional[str]] = {i: None for i in range(1, len(preguntas) + 1)}
    if not m:
        return out
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return out
    for i, (_, ops) in enumerate(preguntas, 1):
        v = str(d.get(str(i), "")).strip()
        ok = [o for o in ops if o.lower() == v.lower()]
        out[i] = ok[0] if ok else None
    return out


def llm_por_defecto() -> Callable[[str], str]:
    from openai import OpenAI
    from app.utils.llm_client import strip_reasoning
    cli = OpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL, timeout=Config.LLM_TIMEOUT_SECONDS)

    def llm(prompt: str) -> str:
        r = cli.chat.completions.create(model=Config.LLM_MODEL_NAME, temperature=0,
                                        messages=[{"role": "user", "content": prompt}])
        return strip_reasoning(r.choices[0].message.content)
    return llm


def evaluar(muestra, preguntas, llm: Callable[[str], str], semilla: int = 1) -> Dict:
    ocultas = {q for q, _ in preguntas}
    pesos = [max(e.peso, 1e-9) for e in muestra]
    real = {q: [next((r["respuesta"] for r in e.respuestas if r["pregunta"] == q), None) for e in muestra]
            for q, _ in preguntas}
    pred = {"a": {q: [] for q, _ in preguntas}, "b": {q: [] for q, _ in preguntas}}
    for e in muestra:
        for cond, con in (("a", False), ("b", True)):
            res = parsear(llm(prompt_persona(e, ocultas, con, preguntas)), preguntas)
            for i, (q, _) in enumerate(preguntas, 1):
                pred[cond][q].append(res[i])
    # línea base: moda del grupo (sexo × tramo), sin contarse a sí mismo
    grupo = lambda e: (e.sexo, e.tramo)  # noqa: E731
    base = {q: [] for q, _ in preguntas}
    for k, e in enumerate(muestra):
        for q, ops in preguntas:
            c = Counter(real[q][j] for j, o in enumerate(muestra) if j != k and grupo(o) == grupo(e) and real[q][j])
            if not c:
                c = Counter(real[q][j] for j in range(len(muestra)) if j != k and real[q][j])
            base[q].append(c.most_common(1)[0][0] if c else None)
    rng = random.Random(semilla)
    cond_res = {}
    for nombre, preds in (("a_sociodemografia", pred["a"]), ("b_con_respuestas", pred["b"]), ("moda_del_grupo", base)):
        aciertos = []; aciertos_w = []; dist = []; sin_resp = 0
        for q, ops in preguntas:
            for r, p, w in zip(real[q], preds[q], pesos):
                if r is None:
                    continue
                if p is None:
                    sin_resp += 1
                aciertos.append(1.0 if p == r else 0.0)
                aciertos_w.append((1.0 if p == r else 0.0, w))
            validos = [(r, p, w) for r, p, w in zip(real[q], preds[q], pesos) if r is not None]
            dist.append(jsd(distribucion([p for _, p, _ in validos], [w for _, _, w in validos], ops),
                            distribucion([r for r, _, _ in validos], [w for _, _, w in validos], ops)))
        cond_res[nombre] = {
            "acierto": sum(aciertos) / len(aciertos) if aciertos else 0.0,
            "acierto_ponderado": sum(a * w for a, w in aciertos_w) / (sum(w for _, w in aciertos_w) or 1),
            "jsd_medio": sum(dist) / len(dist) if dist else 1.0, "sin_respuesta": sin_resp,
        }
    azar_acierto = sum(1 / len(ops) for _, ops in preguntas) / len(preguntas)
    azar_jsd = []
    for q, ops in preguntas:
        validos = [(r, w) for r, w in zip(real[q], pesos) if r is not None]
        azar_jsd.append(jsd({o: 1.0 for o in ops}, distribucion([r for r, _ in validos], [w for _, w in validos], ops)))
    cond_res["azar"] = {"acierto": azar_acierto, "acierto_ponderado": azar_acierto, "jsd_medio": sum(azar_jsd) / len(azar_jsd), "sin_respuesta": 0}
    return cond_res


def informe_md(estudio, n, preguntas, res, coste) -> str:
    f = lambda x: f"{x * 100:.1f} %"  # noqa: E731
    filas = "\n".join(
        f"| {n_} | {f(v['acierto'])} | {f(v['acierto_ponderado'])} | {v['jsd_medio']:.3f} |"
        for n_, v in res.items())
    qs = "\n".join(f"- {q} ({' / '.join(ops)})" for q, ops in preguntas)
    return f"""# Fidelidad con datos del CIS — estudio {estudio}

*Fuente de datos: CIS (estudio {estudio}). Uso interno de I+D.*

{n} encuestados reales · {len(preguntas)} preguntas de actitud escondidas · coste real aproximado {coste['usd']} $ ({coste['llamadas']} llamadas).

## Resultado

| Condición | Acierto individual | Acierto ponderado | Distancia JS media (0 = igual) |
|---|---|---|---|
{filas}

Referencia (Park et al., Stanford 2024, arXiv 2411.10109): 74 % con solo demografía, 82 % con encuesta, 86 % con
encuesta y entrevista, frente a lo que la misma persona repite a las dos semanas. Otro estudio (arXiv 2509.19088):
persona a persona y ante estímulos nuevos solo r = 0,20 → **se vende como ensayo, no como predicción**.

## Preguntas escondidas
{qs}

## Cómo leerlo
- *a_sociodemografia*: el modelo solo sabe sexo, edad, región, estudios, situación laboral.
- *b_con_respuestas*: además sabe el resto de lo que esa persona contestó (las escondidas no aparecen).
- *moda_del_grupo*: línea base sin LLM — la respuesta más común de su grupo (sexo × tramo de edad).
- *azar*: elegir al azar entre las opciones.
La mejora de b sobre a es lo que aporta anclar a la persona a sus datos reales; la de a sobre la moda del grupo, lo
que aporta el modelo.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estudio", default="3535")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--preguntas", type=int, default=10)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--estimar", action="store_true", help="solo calcula el coste y sale")
    ap.add_argument("--ejecutar", action="store_true", help="lanza las llamadas (cuesta dinero real)")
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--salida", default="")
    a = ap.parse_args(argv)
    if not BancoCIS.disponible(Config.POBLACION_BANCO_PATH):
        raise SystemExit("No hay banco: construye uno con build_banco_cis.py (POBLACION_BANCO_PATH).")
    banco = BancoCIS(Config.POBLACION_BANCO_PATH)
    muestra = cargar_muestra(banco, a.estudio, a.n, a.semilla)
    preguntas = elegir_preguntas(muestra, a.preguntas)
    if len(muestra) < 30 or len(preguntas) < 3:
        raise SystemExit(f"Muestra insuficiente ({len(muestra)} personas, {len(preguntas)} preguntas aptas).")
    coste = estimar_coste(muestra, preguntas)
    print(f"{len(muestra)} personas · {len(preguntas)} preguntas escondidas")
    print(f"Coste estimado: {coste['usd']} $ ({coste['llamadas']} llamadas, {coste['tokens_entrada']:,} tokens de entrada, "
          f"~{coste['tokens_salida']:,} de salida) con MiniMax-M3")
    if not a.ejecutar:
        return
    if coste["usd"] > a.max_usd:
        raise SystemExit(f"El coste estimado supera --max-usd={a.max_usd}. No se lanza.")
    res = evaluar(muestra, preguntas, llm_por_defecto(), a.semilla)
    md = informe_md(a.estudio, len(muestra), preguntas, res, coste)
    salida = a.salida or os.path.join(os.path.dirname(Config.POBLACION_BANCO_PATH), "fidelidad.md")
    Path(salida).write_text(md, encoding="utf-8")
    print(md)
    print(f"Informe guardado en {salida}")


if __name__ == "__main__":
    main()
