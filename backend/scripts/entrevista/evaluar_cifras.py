#!/usr/bin/env python3
"""Mide cuántas respuestas de una persona simulada traen cifras que no están en su perfil, su memoria ni el texto base.

    cd backend && .venv/bin/python scripts/entrevista/evaluar_cifras.py [--perfiles perfiles.json] [--prompt anterior|actual|ambos]
                                                                        [--via vivo|fallback|ambas] [--repeticiones 2] [--json salida.json]
    ...evaluar_cifras.py --reevaluar salida.json     # vuelve a contar las cifras de respuestas ya guardadas, sin llamar al modelo

Cinco preguntas que invitan a inventar (porcentaje, recuento de firmas, encuestas, importes, fechas) a tres perfiles. Por cada
respuesta extrae las cifras (`app/utils/cifras.py`) y cuenta las que no aparecen en las fuentes de la persona. Una cifra que
sí consta («somos 37 en el grupo») no cuenta; una que viene en la propia pregunta, tampoco.

Compara el texto que se mandaba ANTES de la regla (3-oct-2026, copiado aquí abajo para poder repetir la comparación) con el de
ahora, por las dos vías por las que se entrevista:
  · vivo: el entorno de simulación sigue abierto → mensaje de sistema = perfil + memorias; la pregunta lleva el prefijo.
  · fallback: el entorno ya no existe → el modelo hace de la persona con `build_interview_system_prompt`; la pregunta va tal cual.
Llama al modelo configurado en .env (LLM_*): unas decenas de llamadas cortas, unos céntimos. NO es parte del CI.
Qué no mide: cifras escritas enteras en letra («mil doscientas») ni números pequeños en letra («dos vecinas»); un porcentaje que
coincida por casualidad con un número de la memoria cuenta como respaldado.
"""
import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.interview_guard import (  # noqa: E402
    build_context_block, build_interview_system_prompt, optimize_interview_prompt,
)
from app.utils.cifras import cifras_sin_respaldo  # noqa: E402
from app.utils.llm_client import LLMClient  # noqa: E402

TEMPERATURA = 0.85   # la del fallback en producción

# El texto de ANTES de la regla: se conserva aquí para poder repetir la medición «antes / ahora»
PREFIJO_ANTERIOR = (
    "Basándote en tu perfil, todas tus memorias y acciones pasadas, "
    "responde directamente con texto en español sin invocar ninguna herramienta: "
)
SISTEMA_ANTERIOR = (
    "{contexto}Eres {username}, {profession}.\nTu perfil: {bio}\n\n"
    "Responde siempre en español, en primera persona, con autenticidad y en el tono "
    "propio de tu profesión e identidad. No uses prefijos ni introducciones: ve directo "
    "al grano como si fuera una conversación real."
)


def memoria_como_texto(perfil: dict, base: str) -> str:
    memorias = "\n".join(f"- {m}" for m in perfil.get("memoria", []))
    return f"\n\nTexto base de la simulación: {base}\n\nTus memorias (lo que dijiste, viste e hiciste en la simulación):\n{memorias}"


def mensajes(variante: str, perfil: dict, contexto: dict, pregunta: str) -> list:
    """El par (sistema, usuario) que recibiría el modelo. variante = «<anterior|actual>-<vivo|fallback>»."""
    prompt, via = variante.split("-")
    bio = perfil["bio"]
    if via == "vivo":
        sistema = f"Eres {perfil['username']}, {perfil['profession']}.\nTu perfil: {bio}" + memoria_como_texto(perfil, contexto.get("texto_base", ""))
        usuario = (PREFIJO_ANTERIOR + pregunta) if prompt == "anterior" else optimize_interview_prompt(pregunta)
    else:
        bloque = build_context_block(contexto.get("proyecto", ""), contexto.get("hipotesis", ""), contexto.get("texto_base", ""))
        if prompt == "anterior":
            sistema = SISTEMA_ANTERIOR.format(contexto=bloque, username=perfil["username"], profession=perfil["profession"], bio=bio[:600])
        else:
            sistema = build_interview_system_prompt(perfil["username"], perfil["profession"], bio, bloque)
        usuario = pregunta
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


def fuentes(perfil: dict, contexto: dict, pregunta: str) -> list:
    return [perfil["bio"], *perfil.get("memoria", []), contexto.get("texto_base", ""), contexto.get("hipotesis", ""), pregunta]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perfiles", default=str(Path(__file__).with_name("perfiles_ejemplo.json")))
    ap.add_argument("--prompt", choices=["anterior", "actual", "ambos"], default="ambos")
    ap.add_argument("--via", choices=["vivo", "fallback", "ambas"], default="ambas")
    ap.add_argument("--repeticiones", type=int, default=2, help="veces que se hace cada pregunta a cada perfil (default 2)")
    ap.add_argument("--paralelo", type=int, default=6)
    ap.add_argument("--json", help="guarda todas las respuestas y sus cifras en este fichero")
    ap.add_argument("--reevaluar", help="fichero guardado con --json: recuenta sus cifras con el detector actual, sin llamar al modelo")
    a = ap.parse_args(argv)

    datos = json.load(open(a.perfiles, encoding="utf-8"))
    contexto, preguntas, perfiles = datos.get("contexto", {}), datos["preguntas"], datos["perfiles"]
    prompts = ["anterior", "actual"] if a.prompt == "ambos" else [a.prompt]
    vias = ["vivo", "fallback"] if a.via == "ambas" else [a.via]
    variantes = [f"{p}-{v}" for p in prompts for v in vias]

    if a.reevaluar:                         # mismas respuestas, detector actual: no cuesta ni una llamada
        resultados = json.load(open(a.reevaluar, encoding="utf-8"))
        por_id = {p["id"]: p for p in perfiles}
        textos = {q["id"]: q["texto"] for q in preguntas}
        for r in resultados:
            perfil = por_id[r["perfil"]]
            pregunta = textos[r["pregunta"]].format(entorno=perfil.get("entorno", "las personas de tu entorno"))
            r["cifras_sin_respaldo"] = cifras_sin_respaldo(r["respuesta"], fuentes(perfil, contexto, pregunta)) if not r["error"] else []
        variantes = sorted({r["variante"] for r in resultados}, key=lambda v: (v.split("-")[0] != "anterior", v))
    else:
        try:
            llm = LLMClient()
        except ValueError as e:
            sys.exit(f"{e}. Pon LLM_API_KEY (y LLM_BASE_URL, LLM_MODEL_NAME) en el .env de la raíz del proyecto.")

        trabajos = [(v, p, q, r) for v in variantes for p in perfiles for q in preguntas for r in range(a.repeticiones)]

        def uno(trabajo):
            variante, perfil, q, rep = trabajo
            pregunta = q["texto"].format(entorno=perfil.get("entorno", "las personas de tu entorno"))
            try:
                respuesta = llm.chat(messages=mensajes(variante, perfil, contexto, pregunta), temperature=TEMPERATURA, max_tokens=600)
                inventadas = cifras_sin_respaldo(respuesta, fuentes(perfil, contexto, pregunta))
                return {"variante": variante, "perfil": perfil["id"], "pregunta": q["id"], "rep": rep,
                        "respuesta": respuesta, "cifras_sin_respaldo": inventadas, "error": None}
            except Exception as e:  # una llamada fallida no tumba la medición: se cuenta aparte
                return {"variante": variante, "perfil": perfil["id"], "pregunta": q["id"], "rep": rep,
                        "respuesta": "", "cifras_sin_respaldo": [], "error": str(e)[:200]}

        print(f"{len(trabajos)} respuestas ({len(perfiles)} perfiles × {len(preguntas)} preguntas × {a.repeticiones} repeticiones × {len(variantes)} variantes)…")
        with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as pool:
            resultados = list(pool.map(uno, trabajos))


    por_variante, por_celda = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0])   # [respuestas, con cifras inventadas, errores]
    por_pregunta = defaultdict(lambda: [0, 0])
    for r in resultados:
        fila = por_variante[r["variante"]]
        if r["error"]:
            fila[2] += 1
            continue
        fila[0] += 1
        fila[1] += bool(r["cifras_sin_respaldo"])
        celda = por_celda[(r["variante"], r["perfil"])]
        celda[0] += 1
        celda[1] += bool(r["cifras_sin_respaldo"])
        pregunta = por_pregunta[(r["variante"], r["pregunta"])]
        pregunta[0] += 1
        pregunta[1] += bool(r["cifras_sin_respaldo"])

    print(f"\n{'variante':22}{'respuestas':>12}{'con cifras sin respaldo':>26}{'%':>7}{'errores':>9}")
    for v in variantes:
        n, k, e = por_variante[v]
        print(f"{v:22}{n:>12}{k:>26}{(k / n if n else 0):>7.0%}{e:>9}")
    print("\nPor perfil (con cifras sin respaldo / respuestas):")
    for p in perfiles:
        print(f"  {p['id']:22}" + "  ".join(f"{v}: {por_celda[(v, p['id'])][1]}/{por_celda[(v, p['id'])][0]}" for v in variantes))

    print("\nPor pregunta (con cifras sin respaldo / respuestas):")
    for q in preguntas:
        print(f"  {q['id']:22}" + "  ".join(f"{v}: {por_pregunta[(v, q['id'])][1]}/{por_pregunta[(v, q['id'])][0]}" for v in variantes))

    ejemplos = [r for r in resultados if r["cifras_sin_respaldo"] and r["variante"].startswith("actual")][:8]
    if ejemplos:
        print("\nCon el texto actual todavía se inventan cifras (hasta 8):")
        for r in ejemplos:
            print(f"  [{r['variante']}] {r['perfil']} · {r['pregunta']} → {', '.join(r['cifras_sin_respaldo'])}\n      «{r['respuesta'][:240].strip()}…»")
    if a.json:
        json.dump(resultados, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nRespuestas completas en {a.json}")


if __name__ == "__main__":
    main()
