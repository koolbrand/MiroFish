#!/usr/bin/env python3
"""Mide cuánto vocabulario de pronóstico («pronostica», «predice», «predicción», «el futuro será»…) escribe el redactor del informe.

    cd backend && .venv/bin/python scripts/informe/evaluar_vocabulario.py [--anterior origin/main] [--repeticiones 3] [--json salida.json]

Compara los prompts del redactor en un commit ANTERIOR (`--anterior`, por defecto origin/main: sirve mientras el cambio no esté
fusionado; después pasa el commit previo al PR) con los de ahora, sobre el mismo material simulado (tres escenarios con citas
de agentes inventadas):
  · esquema: el modelo propone título, resumen y secciones del informe (prompt de planificación).
  · sección: el modelo redacta el cuerpo de una sección con el resultado de una herramienta ya a la vista (prompt de sección).
Cuenta las respuestas VÁLIDAS (esquema con su JSON, sección con «Final Answer:» y cuerpo) que contienen alguna raíz de
`VOCABULARIO_VETADO` y qué palabras salen; las que el modelo no completa se descartan y se cuentan aparte. Llama al modelo del .env (LLM_*):
unas decenas de llamadas, unos céntimos. NO es parte del CI. Es un banco de pruebas, no el informe real: sin herramientas ni grafo.
"""
import argparse
import ast
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from app.services import report_agent as R  # noqa: E402
from app.utils.llm_client import LLMClient  # noqa: E402

NOMBRES = ("PLAN_SYSTEM_PROMPT", "PLAN_USER_PROMPT_TEMPLATE", "SECTION_SYSTEM_PROMPT_TEMPLATE", "SECTION_USER_PROMPT_TEMPLATE")

ESCENARIOS = [
    {
        "id": "linea14",
        "requisito": "El ayuntamiento anuncia que suprimirá la línea 14 de autobús, que une los barrios periféricos con el centro y el centro de salud, para ahorrar costes. ¿Cómo reaccionará cada grupo?",
        "seccion": "Cómo reaccionan los barrios afectados",
        "citas": [
            "[vecinos_periferia] El 14 es el único autobús que nos lleva al centro de salud. Si lo quitan, mi madre se queda sin consulta.",
            "[vecinos_periferia] Nos juntamos en la plaza para hablar de la línea 14. Había ganas de hacer ruido.",
            "[comerciante_centro] Mis clientes de los barrios vienen los sábados en el 14; sin él no sé cómo vendrán.",
            "[concejala_movilidad] El borrador del plan es una propuesta abierta a alegaciones; el servicio a demanda es una alternativa.",
            "[vecinos_periferia] Hemos pedido una reunión con la concejala. De momento no hay fecha.",
            "[periodista_local] Los vecinos preparan un escrito para el pleno y los comerciantes aún no han tomado postura.",
        ],
    },
    {
        "id": "cafeteria",
        "requisito": "Una cafetería de barrio sube el precio del café de 1,40 € a 1,70 € y retira el menú del día de los lunes. ¿Cómo reaccionarán clientes habituales, oficinistas y estudiantes?",
        "seccion": "La reacción de los clientes habituales",
        "citas": [
            "[cliente_habitual] Llevo años viniendo cada mañana; subir el café así de golpe me escuece, pero la dueña es de aquí.",
            "[oficinista] Si quitan el menú del lunes, me llevo el tupper. Era lo que me hacía bajar.",
            "[estudiante] A mí el café me da igual, vengo por el wifi y por sentarme.",
            "[duena_cafeteria] Los costes de la leche y de la luz me han obligado. No me gusta nada subir precios.",
            "[cliente_habitual] Hay otra cafetería en la esquina; no me iría, pero lo comentaría.",
        ],
    },
    {
        "id": "mensaje_politico",
        "requisito": "Un partido local lanza el lema «Menos obras, más barrios» en redes sociales antes de las elecciones municipales. ¿Cómo lo recibirán votantes indecisos, afines y críticos?",
        "seccion": "Qué hacen los indecisos",
        "citas": [
            "[indeciso_1] El lema suena bien, pero no sé qué significa en concreto. ¿Menos obras dónde?",
            "[afin] Por fin alguien dice que hay que cuidar los barrios y no solo el centro.",
            "[critico] «Menos obras» es una excusa para no hacer nada. Lo vi con el gobierno anterior.",
            "[indeciso_2] Me fijo más en el candidato que en el lema. Todavía no sé a quién votaré.",
            "[periodista_local] El lema ha tenido bastante eco en Twitter, sobre todo entre quienes ya simpatizaban.",
        ],
    },
]


def prompts_anteriores(ref: str) -> dict:
    """Los prompts del redactor tal como estaban en `ref` (git show + ast: no se importa código viejo)."""
    src = subprocess.check_output(["git", "show", f"{ref}:backend/app/services/report_agent.py"], text=True, cwd=BACKEND)
    out = {}
    for nodo in ast.parse(src).body:
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], "id", None) in NOMBRES:
            try:
                out[nodo.targets[0].id] = ast.literal_eval(nodo.value)
            except ValueError:
                sys.exit(f"En {ref} los prompts ya son los nuevos (no son un literal): pasa con --anterior un commit previo al cambio.")
    return out


def prompts_actuales() -> dict:
    return {n: getattr(R, n) for n in NOMBRES}


def mensajes_esquema(p: dict, esc: dict) -> list:
    sistema = f"Por favor, responde en español.\n\n{p['PLAN_SYSTEM_PROMPT']}"
    usuario = p["PLAN_USER_PROMPT_TEMPLATE"].format(
        simulation_requirement=esc["requisito"], total_nodes=40, total_edges=95, entity_types=["Vecino", "Comerciante", "Institución"],
        total_entities=12, related_facts_json=json.dumps(esc["citas"], ensure_ascii=False, indent=2))
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


def mensajes_seccion(p: dict, esc: dict) -> list:
    sistema = "Por favor, responde en español.\n\n" + p["SECTION_SYSTEM_PROMPT_TEMPLATE"].format(
        report_title=f"Informe: {esc['id']}", report_summary="Cómo reaccionan los grupos ante la medida.",
        simulation_requirement=esc["requisito"], section_title=esc["seccion"], tools_description="(insight_forge, panorama_search, quick_search, interview_agents)")
    usuario = p["SECTION_USER_PROMPT_TEMPLATE"].format(previous_content="(Este es el primer capítulo)", section_title=esc["seccion"])
    observacion = ("Observation (resultado de la herramienta):\n\n═══ Retorno de la herramienta insight_forge ═══\n"
                   + "\n".join(f"{i}. {c}" for i, c in enumerate(esc["citas"], 1))
                   + "\n\n" + R.REACT_TOOL_LIMIT_MSG.format(tool_calls_count=5, max_tool_calls=5))     # el aviso real del tope de llamadas: obliga al texto final
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario},
            {"role": "assistant", "content": "Thought: necesito los hechos de la simulación.\n<tool_call>\n{\"name\": \"insight_forge\", \"parameters\": {\"query\": \"reacciones\"}}\n</tool_call>"},
            {"role": "user", "content": observacion}]


def es_valida(tipo: str, texto: str) -> bool:
    """Una sección cuenta solo si el modelo llegó a escribir el cuerpo («Final Answer:» y texto); el esquema, si trae el JSON."""
    return ("Final Answer:" in texto and len(texto) > 300) if tipo == "sección" else ('"sections"' in texto)


def palabras_vetadas(texto: str) -> list:
    plano = texto.lower()
    palabras = []
    for raiz in R.VOCABULARIO_VETADO:
        palabras += re.findall(rf"\w*{re.escape(raiz)}\w*", plano)
    return palabras


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anterior", default="origin/main", help="commit con los prompts de antes (default origin/main)")
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--paralelo", type=int, default=6)
    ap.add_argument("--json", help="guarda todas las respuestas en este fichero")
    a = ap.parse_args(argv)

    try:
        llm = LLMClient()
    except ValueError as e:
        sys.exit(f"{e}. Pon LLM_API_KEY (y LLM_BASE_URL, LLM_MODEL_NAME) en el .env de la raíz del proyecto.")
    versiones = {"anterior": prompts_anteriores(a.anterior), "actual": prompts_actuales()}
    trabajos = [(v, tipo, esc, r) for v in versiones for tipo in ("esquema", "sección") for esc in ESCENARIOS for r in range(a.repeticiones)]

    def uno(t):
        version, tipo, esc, rep = t
        construir = mensajes_esquema if tipo == "esquema" else mensajes_seccion
        try:
            texto = llm.chat(messages=construir(versiones[version], esc), temperature=0.3 if tipo == "esquema" else 0.5, max_tokens=1800)
            return {"version": version, "tipo": tipo, "escenario": esc["id"], "rep": rep, "texto": texto,
                    "vetadas": palabras_vetadas(texto), "valida": es_valida(tipo, texto), "error": None}
        except Exception as e:  # una llamada fallida no tumba la medición
            return {"version": version, "tipo": tipo, "escenario": esc["id"], "rep": rep, "texto": "", "vetadas": [], "valida": False, "error": str(e)[:200]}

    print(f"{len(trabajos)} respuestas ({len(ESCENARIOS)} escenarios × {a.repeticiones} repeticiones × 2 tipos × 2 versiones)…")
    with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as pool:
        resultados = list(pool.map(uno, trabajos))

    print(f"\n{'':10}{'versión':10}{'válidas':>12}{'con vocabulario de pronóstico':>32}{'%':>7}{'descartadas':>13}")
    for tipo in ("esquema", "sección"):
        for v in versiones:
            fila = [r for r in resultados if r["tipo"] == tipo and r["version"] == v]
            ok = [r for r in fila if not r["error"] and r["valida"]]
            con = [r for r in ok if r["vetadas"]]
            print(f"{tipo:10}{v:10}{len(ok):>12}{len(con):>32}{(len(con) / len(ok) if ok else 0):>7.0%}{len(fila) - len(ok):>13}")
    for v in versiones:
        palabras = sorted({p for r in resultados if r["version"] == v for p in r["vetadas"]})
        print(f"\nPalabras que salen ({v}): {', '.join(palabras) or '—'}")
    if a.json:
        json.dump(resultados, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nRespuestas completas en {a.json}")


if __name__ == "__main__":
    main()
