#!/usr/bin/env python3
"""Mide cuánto acierta el detector de ALCANCE geográfico con un conjunto de briefs etiquetados por otras personas (o agentes).

    cd backend && .venv/bin/python scripts/poblacion/evaluar_alcance.py briefs.json [--paralelo 8]

`briefs.json`: lista de {id, texto, pregunta, nivel_esperado, [niveles_aceptables], lugar_esperado, region_esperada, provincia_esperada}.
Si un brief trae `niveles_aceptables` (casos límite), se cuenta también como «aceptable» el acierto en cualquiera de ellos.
Llama al modelo de producción (una llamada por brief, unos céntimos). Imprime acierto de nivel, matriz de confusión y los fallos.
"""
import argparse
import json
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.oasis_profile_generator import OasisProfileGenerator  # noqa: E402
from app.services.poblacion import alcance as A                         # noqa: E402
from app.services.poblacion.fuentes import disponibles                  # noqa: E402

ALIAS = {"principado de asturias": "asturias", "comunidad de madrid": "madrid", "region de murcia": "murcia",
         "illes balears": "baleares", "islas baleares": "baleares", "comunidad foral de navarra": "navarra",
         "comunitat valenciana": "comunidad valenciana", "cataluna": "cataluna", "catalunya": "cataluna",
         "pais vasco": "pais vasco", "euskadi": "pais vasco", "la rioja": "la rioja"}


def plano(s) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")
    return ALIAS.get(s.strip(), s.strip())


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("briefs")
    ap.add_argument("--paralelo", type=int, default=8)
    a = ap.parse_args(argv)
    briefs = json.load(open(a.briefs, encoding="utf-8"))
    llm = OasisProfileGenerator()._llm_texto
    if not disponibles():
        print("Aviso: no hay banco; el detector no puede validar regiones ni provincias (solo se mide el nivel).")

    def uno(b):
        return A.detectar("auto", b.get("pregunta", ""), b.get("texto", ""), llm)

    with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as pool:
        resultados = list(pool.map(uno, briefs))

    ok = 0
    aceptable = 0
    confusion = Counter()
    fallos, reg_ok, reg_n, prov_ok, prov_n = [], 0, 0, 0, 0
    for b, r in zip(briefs, resultados):
        esperado = b["nivel_esperado"]
        confusion[(esperado, r.nivel)] += 1
        if r.nivel == esperado:
            ok += 1
        if r.nivel in (b.get("niveles_aceptables") or [esperado]):
            aceptable += 1
        else:
            fallos.append((b["id"], "/".join(b.get("niveles_aceptables") or [esperado]), r.nivel, r.lugar, r.motivo))
        if esperado in ("local", "regional") and b.get("region_esperada"):
            reg_n += 1
            esperadas = {plano(x) for x in str(b["region_esperada"]).split(",") if x.strip()}   # varias comunidades: «A, B, C»
            reg_ok += {plano(x) for x in r.lista_regiones} == esperadas
        if esperado == "local" and b.get("provincia_esperada"):
            prov_n += 1
            prov_ok += plano(r.provincia) == plano(b["provincia_esperada"])
    print(f"Nivel acertado (el esperado): {ok}/{len(briefs)} ({ok / len(briefs):.0%})")
    print(f"Nivel aceptable (cualquiera de los aceptables): {aceptable}/{len(briefs)} ({aceptable / len(briefs):.0%})")
    if reg_n:
        print(f"Región acertada (local y regional): {reg_ok}/{reg_n}")
    if prov_n:
        print(f"Provincia acertada (local): {prov_ok}/{prov_n}")
    print("\nMatriz (esperado más razonable → detectado):")
    for (e, d), n in sorted(confusion.items()):
        print(f"  {e:14} → {d:14} {n}")
    if fallos:
        print("\nFuera de lo aceptable:")
        for f in fallos:
            print(f"  {f[0]}: esperado {f[1]}, detectó {f[2]} ({f[3]}) — {f[4][:140]}")
    sin_region = [b["id"] for b, r in zip(briefs, resultados)
                  if b["nivel_esperado"] in ("local", "regional") and b.get("region_esperada")
                  and {plano(x) for x in r.lista_regiones} != {plano(x) for x in str(b["region_esperada"]).split(",") if x.strip()}]
    if sin_region:
        print("\nRegión distinta de la esperada en:", ", ".join(sin_region))


if __name__ == "__main__":
    main()
