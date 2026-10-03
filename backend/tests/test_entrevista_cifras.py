"""
Una persona simulada no se inventa cifras: la regla viaja en TODAS las vías de entrevista y cada respuesta lleva su aviso.

Caso real (3-oct-2026): al preguntar «¿qué porcentaje de los vecinos de vuestros barrios piensa lo mismo que vosotros?»,
el perfil «vecinos de barrios periféricos» respondió con cifras inventadas en 4 de 4 intentos («entre un 78 % y un 85 %»,
«4.200 firmas»), cuando sus 8 mensajes no traían ningún porcentaje ni recuento. Aquí no se llama a ningún modelo: se
comprueba qué texto sale hacia él por cada camino y qué trae la respuesta HTTP. Cuánto se inventa de verdad con la regla
puesta lo mide `scripts/entrevista/evaluar_cifras.py`.
"""

import os

import pytest

from app import create_app
from app.api import simulation as simulation_api
from app.config import Config
from app.models.project import ProjectManager
from app.services.interview_guard import (
    INTERVIEW_PROMPT_PREFIX, REGLA_CIFRAS, REPORT_INTERVIEW_PROMPT_PREFIX,
    build_interview_system_prompt, optimize_interview_prompt, with_notice,
)
from app.services.simulation_manager import SimulationManager
from app.services.simulation_runner import SimulationRunner
from app.services.zep_tools import ZepToolsService
from app.utils.cifras import cifras_sin_respaldo, extraer_cifras
from app.utils.fs import atomic_write_json

from test_pipeline import storage  # noqa: F401

TOKEN = "token-entrevista"
PREGUNTA = "¿Qué porcentaje de los vecinos de vuestros barrios piensa lo mismo que vosotros?"
AVISO_ES = "Razonamiento generado: no cite cifras de una entrevista."


# ---------------------------------------------------------------- el texto que sale hacia el modelo
def test_la_regla_dice_lo_que_hay_que_decir():
    for pieza in ("porcentajes", "encuestas", "recuentos", "firmas", "importes", "fechas", "perfil", "memorias",
                  "texto base", "no la tienes", "más o menos", "rango"):
        assert pieza in REGLA_CIFRAS, pieza


def test_la_pregunta_va_detras_de_la_regla_y_sin_tocar():
    prompt = optimize_interview_prompt(PREGUNTA)
    assert prompt.endswith(PREGUNTA)
    assert prompt.startswith(INTERVIEW_PROMPT_PREFIX) and REGLA_CIFRAS in prompt
    assert "sin invocar ninguna herramienta" in prompt          # lo que ya hacía el prefijo sigue ahí


def test_el_prefijo_no_se_duplica_y_lo_vacio_se_queda_vacio():
    una_vez = optimize_interview_prompt(PREGUNTA)
    assert optimize_interview_prompt(una_vez) == una_vez
    assert optimize_interview_prompt("") == "" and optimize_interview_prompt(None) is None


def test_el_agente_de_informes_entrevista_con_la_misma_regla():
    assert REGLA_CIFRAS in REPORT_INTERVIEW_PROMPT_PREFIX
    assert "«Pregunta X:»" in REPORT_INTERVIEW_PROMPT_PREFIX    # y conserva su formato de respuesta


def test_sin_entorno_el_modelo_hace_de_la_persona_con_la_regla_en_el_mensaje_de_sistema():
    sistema = build_interview_system_prompt("vecinos_periferia", "Vecinos de barrios periféricos", "Viven lejos del centro.")
    assert sistema.startswith("Eres vecinos_periferia, Vecinos de barrios periféricos.")
    assert "Viven lejos del centro." in sistema and sistema.rstrip().endswith(REGLA_CIFRAS)


# ---------------------------------------------------------------- el aviso fijo
def test_with_notice_copia_el_resultado_y_no_toca_lo_que_no_es_un_dict():
    original = {"success": True, "result": {"a": 1}}
    con = with_notice(original)
    assert con["notice"] and con["notice"] != "api.interviewNotice"      # la frase traducida, no la clave en crudo
    assert con["result"] == {"a": 1} and "notice" not in original
    assert with_notice(None) is None and with_notice("texto") == "texto"


# ---------------------------------------------------------------- por la API
@pytest.fixture
def client(storage, monkeypatch):
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", TOKEN)
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


def post(client, ruta, **cuerpo):
    return client.post(f"/api/simulation{ruta}", headers={"Authorization": f"Bearer {TOKEN}"}, json=cuerpo)


@pytest.fixture
def sid(storage):
    project = ProjectManager.create_project(name="P", owner_id=None)
    simulation_id = SimulationManager().create_simulation(project_id=project.project_id, graph_id="mirofish_g00000000001").simulation_id
    # Un entorno vivo procede de una preparación con configuración persistida;
    # «a todos» debe conocer el número efectivo de entrevistas antes de enviarlas.
    atomic_write_json(os.path.join(SimulationManager.SIMULATION_DATA_DIR, simulation_id, "simulation_config.json"), {
        "agent_configs": [{"agent_id": 0}, {"agent_id": 1}],
        "reddit_config": {"platform": "reddit"}, "twitter_config": {"platform": "twitter"},
    })
    return simulation_id


@pytest.fixture
def runner(monkeypatch):
    """El entorno de simulación, vivo y falso: guarda los prompts que le llegan."""
    visto = {"prompts": []}

    def agente(cls, simulation_id, agent_id, prompt, platform=None, timeout=60.0):
        visto["prompts"].append(prompt)
        return {"success": True, "result": {"agent_id": agent_id, "response": "No tengo ese dato."}}

    def lote(cls, simulation_id, interviews, platform=None, timeout=120.0):
        visto["prompts"] += [i["prompt"] for i in interviews]
        return {"success": True, "interviews_count": len(interviews), "result": {"results": {}}}

    def todos(cls, simulation_id, prompt, platform=None, timeout=180.0):
        visto["prompts"].append(prompt)
        return {"success": True, "interviews_count": 1, "result": {"results": {}}}

    monkeypatch.setattr(SimulationRunner, "check_env_alive", classmethod(lambda cls, simulation_id: True))
    monkeypatch.setattr(SimulationRunner, "interview_agent", classmethod(agente))
    monkeypatch.setattr(SimulationRunner, "interview_agents_batch", classmethod(lote))
    monkeypatch.setattr(SimulationRunner, "interview_all_agents", classmethod(todos))
    return visto


@pytest.mark.parametrize("ruta, cuerpo", [
    ("/interview", {"agent_id": 0, "prompt": PREGUNTA}),
    ("/interview/batch", {"interviews": [{"agent_id": 0, "prompt": PREGUNTA}, {"agent_id": 1, "prompt": PREGUNTA}]}),
    ("/interview/all", {"prompt": PREGUNTA}),
])
def test_las_tres_rutas_con_entorno_vivo_llevan_la_regla_y_devuelven_el_aviso(client, sid, runner, ruta, cuerpo):
    r = post(client, ruta, simulation_id=sid, **cuerpo)
    datos = r.get_json()
    assert r.status_code == 200 and datos["success"] is True
    assert runner["prompts"] and all(p.startswith(INTERVIEW_PROMPT_PREFIX) and p.endswith(PREGUNTA) for p in runner["prompts"])
    assert datos["data"]["notice"]                                  # y la respuesta de la persona sigue donde estaba
    assert "result" in datos["data"]


def test_el_aviso_sale_en_el_idioma_de_quien_pregunta(client, sid, runner):
    en = client.post("/api/simulation/interview", headers={"Authorization": f"Bearer {TOKEN}", "Accept-Language": "en"},
                     json={"simulation_id": sid, "agent_id": 0, "prompt": PREGUNTA}).get_json()
    es = post(client, "/interview", simulation_id=sid, agent_id=0, prompt=PREGUNTA).get_json()
    assert es["data"]["notice"] == AVISO_ES
    assert en["data"]["notice"] == "Generated reasoning: do not quote figures from an interview."


class ModeloFalso:
    """Guarda lo que se le manda y contesta siempre lo mismo."""
    llamadas = []

    def chat(self, messages, **kwargs):
        ModeloFalso.llamadas.append(messages)
        return "No tengo ese dato."


def test_sin_entorno_el_fallback_con_modelo_lleva_la_regla_y_el_aviso(client, sid, monkeypatch):
    ModeloFalso.llamadas = []
    monkeypatch.setattr(SimulationRunner, "check_env_alive", classmethod(lambda cls, simulation_id: False))
    monkeypatch.setattr(simulation_api, "LLMClient", ModeloFalso)
    monkeypatch.setattr(simulation_api, "_load_simulation_profiles",
                        lambda simulation_id: [{"username": "vecinos", "bio": "Viven en la periferia.", "profession": "Vecinos"}])
    r = post(client, "/interview/batch", simulation_id=sid, interviews=[{"agent_id": 0, "prompt": PREGUNTA}])
    datos = r.get_json()
    assert r.status_code == 200 and datos["data"]["notice"] == AVISO_ES
    sistema, usuario = ModeloFalso.llamadas[0]
    assert sistema["role"] == "system" and REGLA_CIFRAS in sistema["content"] and usuario["content"] == PREGUNTA


def test_el_agente_de_informes_manda_la_regla_a_las_personas(monkeypatch):
    enviados = []

    def lote(cls, simulation_id, interviews, platform=None, timeout=120.0):
        enviados.extend(i["prompt"] for i in interviews)
        return {"success": True, "result": {"results": {"reddit_0": {"response": "No tengo ese dato."}}}}

    monkeypatch.setattr(SimulationRunner, "check_env_alive", classmethod(lambda cls, simulation_id: True))
    monkeypatch.setattr(SimulationRunner, "interview_agents_batch", classmethod(lote))
    servicio = ZepToolsService.__new__(ZepToolsService)            # sin conectar con el grafo: solo se prueba el texto
    perfil = {"realname": "Vecinos", "profession": "Vecinos", "bio": "x"}
    monkeypatch.setattr(servicio, "_load_agent_profiles", lambda sim: [perfil], raising=False)
    monkeypatch.setattr(servicio, "_select_agents_for_interview", lambda **kw: ([perfil], [0], "los únicos"), raising=False)
    monkeypatch.setattr(servicio, "_generate_interview_summary", lambda **kw: "", raising=False)

    resultado = servicio.interview_agents("sim_x", "opinión de los vecinos", custom_questions=[PREGUNTA])

    assert enviados == [f"{REPORT_INTERVIEW_PROMPT_PREFIX}1. {PREGUNTA}"]
    assert resultado.interviewed_count == 1


# ---------------------------------------------------------------- el medidor de cifras
@pytest.mark.parametrize("texto, esperadas", [
    ("Las encuestas rápidas dan entre un 78% y un 85%.", ["78", "85"]),
    ("Más de 1.200 adhesiones y 4.200 firmas.", ["1200", "4200"]),
    ("Unos 12,5 euros, 12.5 si se redondea.", ["12.5"]),
    ("Pasó el 12 de marzo de 2026.", ["12", "2026"]),
    ("Tres de cada cuatro piensa igual; la mitad de los vecinos ni se entera.", ["tres de cada cuatro", "la mitad de los"]),
    ("Ochenta por ciento y miles de firmas.", ["ochenta por ciento", "miles de"]),
    ("Llevan cuatro días y cuarenta minutos de cola; fueron dos reuniones y doscientas firmas.",
     ["4", "40", "2", "200"]),
    ("Dos veces lo dije, tres cosas me preocupan y una vecina se quedó en la parada.", []),   # lenguaje corriente
    ("Pregunta 1: no tengo ese dato.\n2. Tampoco.", []),                        # numerar la respuesta no es una cifra
    ("Nadie lo sabe: gente de cada barrio, la mitad del camino.", []),         # lo que parece cifra y no lo es
    ("", []),
])
def test_extrae_las_cifras_de_un_texto(texto, esperadas):
    assert extraer_cifras(texto) == esperadas


def test_una_cifra_con_respaldo_en_la_memoria_no_cuenta_como_inventada():
    memoria = ["Reunimos a 36 vecinos el 12 de marzo.", "Hay 3 paradas sin marquesina."]
    assert cifras_sin_respaldo("Fuimos 36 el 12 de marzo.", memoria) == []
    assert cifras_sin_respaldo("Fuimos 36, y entre un 78 % y un 85 % lo apoya.", memoria) == ["78", "85"]
    assert cifras_sin_respaldo("Más de 1.200 adhesiones.", ["Reunimos 1200 adhesiones"]) == []     # 1.200 = 1200


def test_una_cifra_que_ya_trae_la_pregunta_no_es_invencion_de_quien_responde():
    assert cifras_sin_respaldo("Del 60 % que dices, no sé.", [PREGUNTA, "¿Qué opinas del 60 % de rechazo?"]) == []


def test_una_cantidad_en_letra_se_respalda_con_su_cifra_y_al_reves():
    assert cifras_sin_respaldo("Tuvimos tres reuniones y llevo doce años.", ["Hemos mantenido 3 reuniones.", "Llevo 12 años aquí."]) == []
    assert cifras_sin_respaldo("Tuvimos 3 reuniones.", ["Hubo tres reuniones técnicas."]) == []      # en letra en la fuente: se ve igual
    assert cifras_sin_respaldo("Tuvimos cuatro reuniones.", ["Hemos mantenido 3 reuniones."]) == ["4"]


def test_la_cifra_verbal_solo_se_respalda_con_la_misma_expresion():
    assert cifras_sin_respaldo("Tres de cada cuatro lo dicen.", ["En el chat se leyó que tres de cada cuatro lo dicen."]) == []
    assert cifras_sin_respaldo("Tres de cada cuatro lo dicen.", ["Solo hablamos del autobús."]) == ["tres de cada cuatro"]
