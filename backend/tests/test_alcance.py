"""Alcance geográfico de la simulación: detección, qué implica cada nivel para a quién se busca, cómo se genera a quien no sale de la
encuesta y qué sabe el informe. Todo con bancos sintéticos y un modelo falso."""

import json
import os
import random
from collections import Counter
from types import SimpleNamespace

import pytest

from app.config import Config
from app.services import poblacion
from app.services.poblacion import alcance as A
from app.services.poblacion.banco import Banco
from app.services.poblacion.filtros import nota_de_alcance, traducir_grupos
from app.services.poblacion.fuentes import FUENTES
from poblacion_fixture import crear_banco


@pytest.fixture()
def con_banco(tmp_path, monkeypatch):
    ruta = crear_banco(str(tmp_path / "banco.sqlite"), n=800)
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", ruta)
    monkeypatch.setattr(Config, "POBLACION_BANCOS_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "POBLACION_DATOS_REALES", False)
    return ruta


def _llm(**kw):
    """Modelo falso que responde a la pregunta de alcance con ese JSON."""
    return lambda prompt: json.dumps(kw)


# ---------------------------------------------------------------- el modelo de datos
def test_alcance_ida_y_vuelta_y_descripcion():
    a = A.Alcance("local", "Vigo", "Galicia", "Pontevedra", motivo="m")
    assert a.descripcion() == "Local · Vigo (Galicia, Pontevedra)"
    assert A.Alcance.de_dict(a.a_dict()) == a
    assert A.Alcance("nacional", "España").descripcion() == "Nacional · España"
    assert A.Alcance("mundial").descripcion() == "Mundial" and A.Alcance().descripcion() == "Sin determinar"
    assert A.Alcance.de_dict({"nivel": "inventado"}).nivel == A.DESCONOCIDO and A.Alcance.de_dict("x") is None


def test_que_niveles_acotan_por_lugar_y_cuales_permiten_anclar():
    assert A.Alcance("local", "Vigo", "Galicia").acota_por_lugar and A.Alcance("regional", "Galicia", "Galicia").acota_por_lugar
    assert not A.Alcance("local", "Marte").acota_por_lugar                              # sin región ni provincia que el banco entienda
    assert not A.Alcance("nacional", "España").acota_por_lugar and not A.Alcance().acota_por_lugar
    assert A.Alcance("nacional").permite_anclar and A.Alcance("local").permite_anclar and A.Alcance().permite_anclar
    assert not A.Alcance("multinacional").permite_anclar and not A.Alcance("mundial").permite_anclar


# ---------------------------------------------------------------- detección
def test_detectar_local_valida_region_y_provincia_con_las_listas_del_banco(con_banco):
    a = A.detectar("auto", "pregunta", "brief", _llm(nivel="local", lugar="Vigo", region="Galicia", provincia="Pontevedra",
                                                      motivo="Una taberna de barrio"))
    assert (a.nivel, a.lugar, a.region, a.provincia, a.origen) == ("local", "Vigo", "Galicia", "Pontevedra", "automatico")
    # una región o provincia que el banco no tiene se descarta: no se inventa
    b = A.detectar("auto", "p", "b", _llm(nivel="local", lugar="Narnia", region="Narnia", provincia="Aslan"))
    assert (b.nivel, b.region, b.provincia) == ("local", None, None) and not b.acota_por_lugar
    # en nacional, multinacional y mundial no hay región ni provincia aunque el modelo las ponga
    c = A.detectar("auto", "p", "b", _llm(nivel="nacional", lugar="España", region="Galicia", provincia="Pontevedra"))
    assert (c.nivel, c.region, c.provincia) == ("nacional", None, None)
    d = A.detectar("auto", "p", "b", _llm(nivel="regional", lugar="Galicia", region="Galicia", provincia="Pontevedra"))
    assert (d.region, d.provincia) == ("Galicia", None)                                  # regional no baja a provincia


def test_el_prompt_lleva_las_listas_y_la_regla_de_la_sede(con_banco):
    visto = {}

    def llm(p):
        visto["p"] = p
        return "{}"

    A.detectar("auto", "¿Qué pasará?", "Una taberna de Vigo", llm)
    p = visto["p"]
    assert "Regiones de España:" in p and "Galicia" in p and "Provincias de España:" in p and "Pontevedra" in p
    assert "dónde vive el PÚBLICO" in p and "Una empresa local que vende por internet a todo el país es nacional" in p
    assert "Una taberna de Vigo" in p and "son de donde VIENEN" in p


def test_detectar_sin_modelo_o_con_fallo_es_desconocido_y_lo_fijado_manda(con_banco):
    assert A.detectar("auto", "p", "b", None).nivel == A.DESCONOCIDO
    assert A.detectar("auto", "", "", _llm(nivel="local")).nivel == A.DESCONOCIDO         # sin texto no se pregunta
    assert A.detectar("auto", "p", "b", lambda p: "no es json").nivel == A.DESCONOCIDO
    assert A.detectar("auto", "p", "b", _llm(nivel="galaxia")).nivel == A.DESCONOCIDO
    def roto(p): raise RuntimeError("boom")
    assert A.detectar(None, "p", "b", roto).nivel == A.DESCONOCIDO
    # la persona lo fijó: manda su nivel aunque el modelo falle, y con origen «pedido»
    f = A.detectar("nacional", "p", "b", roto)
    assert (f.nivel, f.origen) == ("nacional", "pedido")
    g = A.detectar("mundial", "p", "b", _llm(nivel="local", lugar="Vigo", region="Galicia", provincia="Pontevedra"))
    assert (g.nivel, g.region, g.provincia, g.lugar) == ("mundial", None, None, "")      # un lugar local no vale para «mundial»
    h = A.detectar("regional", "p", "b", _llm(nivel="local", lugar="Vigo", region="Galicia", provincia="Pontevedra"))
    assert (h.nivel, h.region, h.provincia) == ("regional", "Galicia", None)             # sí aprovecha la región que ya vio


def test_un_publico_de_varias_regiones_las_conserva_todas(con_banco):
    """El noroeste (Galicia, Asturias, Cantabria): regional, pero con VARIAS comunidades; antes quedaba sin lugar y se buscaba en toda España."""
    a = A.detectar("auto", "p", "b", _llm(nivel="regional", lugar="Noroeste peninsular", regiones=["Galicia", "Madrid", "Narnia", "Galicia"]))
    assert a.nivel == "regional" and a.regiones == ["Galicia", "Madrid"] and a.region is None      # solo las válidas, sin repetir
    assert a.acota_por_lugar and a.lista_regiones == ["Galicia", "Madrid"] and "Galicia, Madrid" in a.descripcion()
    uno = A.detectar("auto", "p", "b", _llm(nivel="regional", lugar="Galicia", region="Galicia", regiones=["Galicia"]))
    assert uno.region == "Galicia" and uno.regiones == []                                          # una sola: como siempre
    assert A.Alcance.de_dict(a.a_dict()) == a
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=a, rng=random.Random(8))
    assert {e.region for e in asig.encuestados} == {"Galicia", "Madrid"}                           # las dos, y ninguna otra
    nacional = A.detectar("auto", "p", "b", _llm(nivel="nacional", lugar="España", regiones=["Galicia", "Madrid"]))
    assert nacional.regiones == [] and not nacional.acota_por_lugar


def test_detectar_multinacional_guarda_los_lugares(con_banco):
    a = A.detectar("auto", "p", "b", _llm(nivel="multinacional", lugar="España y Portugal", lugares=["España", "Portugal"]))
    assert a.nivel == "multinacional" and a.lugares == ["España", "Portugal"] and a.descripcion().startswith("Multinacional")


# ---------------------------------------------------------------- lo que implica cada nivel
def test_pistas_para_las_personas_que_no_salen_de_la_encuesta():
    assert A.pista_para_persona(None) == "" and A.pista_para_persona(A.Alcance()) == ""
    assert "LOCAL (Vigo)" in A.pista_para_persona(A.Alcance("local", "Vigo", "Galicia", "Pontevedra"))
    assert "REGIONAL (Galicia)" in A.pista_para_persona(A.Alcance("regional", "Galicia", "Galicia"))
    nac = A.pista_para_persona(A.Alcance("nacional", "España"))
    assert "NACIONAL (España)" in nac and "varía el lugar" in nac and "no la sitúes en la ciudad de la sede" in nac
    # mundial: cada persona recibe una cultura distinta, repartidas a propósito (no la estadounidense por defecto)
    pistas = {A.pista_para_persona(A.Alcance("mundial"), i) for i in range(10)}
    assert len(pistas) == 10 and any("Asia oriental" in p for p in pistas) and any("Latinoamérica" in p for p in pistas)
    multi = A.Alcance("multinacional", "España y Portugal", lugares=["España", "Portugal"])
    assert "«España»" in A.pista_para_persona(multi, 0) and "«Portugal»" in A.pista_para_persona(multi, 1)
    assert "«España»" in A.pista_para_persona(multi, 2)                                  # y vuelve a empezar


def test_texto_del_informe_segun_el_alcance():
    assert A.texto_para_informe(None) == "" and A.texto_para_informe(A.Alcance()) == ""
    loc = A.texto_para_informe(A.Alcance("local", "Vigo", "Galicia"))
    assert "Local · Vigo" in loc and "no las extrapoles al país" in loc
    assert "no atribuyas lo observado a una ciudad concreta" in A.texto_para_informe(A.Alcance("nacional", "España"))
    assert "no generalices a un solo país" in A.texto_para_informe(A.Alcance("mundial"))
    assert "otras regiones" in A.texto_para_informe(A.Alcance("regional", "Galicia", "Galicia"))


def test_el_traductor_de_filtros_sabe_del_alcance():
    assert nota_de_alcance(None) == ""
    assert "ya acota a TODOS los grupos" in nota_de_alcance(A.Alcance("local", "Vigo", "Galicia"))
    assert "NO filtres por región" in nota_de_alcance(A.Alcance("nacional", "España"))
    visto = {}
    traducir_grupos([{"clave": "a", "nombre": "X", "descripcion": ""}], "", lambda p: visto.setdefault("p", p) and "{}",
                    FUENTES["cis"], A.Alcance("nacional", "España"))
    assert "Alcance de la simulación: NACIONAL o mayor" in visto["p"]


# ---------------------------------------------------------------- el banco: el lugar se suelta el último
def test_el_lugar_se_suelta_el_ultimo_y_basta_con_diez_casos(con_banco):
    banco = Banco(con_banco, FUENTES["cis"])
    filtros = {"sexo": ["Mujer"], "region": ["Galicia"], "estudios": ["universitarios"], "tramo": ["25-34"],
               "estcivil": ["casado"], "tamuni": ["rural"]}
    prot = banco.segmento(filtros)                                    # el lugar está protegido por defecto
    assert "region" in prot.filtros_aplicados and prot.filtros_aplicados["region"] == ["Galicia"]
    assert len(prot.ids) >= 10 and all(banco.encuestado(i).region == "Galicia" for i in prot.ids[:20])
    libre = banco.segmento(filtros, proteger=())                      # sin proteger, la región se relaja como cualquier otro
    assert len(libre.ids) >= 30
    # la provincia se suelta antes que la región
    seg = banco.segmento({"region": ["Galicia"], "subregion": ["Pontevedra"], "sexo": ["Mujer"], "tramo": ["65+"],
                          "estudios": ["primarios"], "sitlab": ["parado"]})
    assert seg.filtros_aplicados.get("region") == ["Galicia"]
    assert "subregion" not in seg.filtros_aplicados or len(seg.ids) >= 10


# ---------------------------------------------------------------- la asignación según el alcance
GRUPOS = [poblacion.Grupo("a", "Clientes habituales", "Gente que toma café", 10),
          poblacion.Grupo("b", "Gente del barrio", "Vecinos", 10),
          poblacion.Grupo("c", "Quienes cuidan el precio", "Miran lo que gastan", 10)]


def test_local_busca_gente_de_ese_lugar(con_banco):
    al = A.Alcance("local", "Vigo", "Galicia", "Pontevedra")
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=al, rng=random.Random(1))
    assert {e.region for e in asig.encuestados} == {"Galicia"} and {e.subregion for e in asig.encuestados} == {"Pontevedra"}
    r = asig.resumen()
    assert r["alcance"]["nivel"] == "local" and r["alcance"]["etiqueta"] == "Local · Vigo (Galicia, Pontevedra)"


def test_regional_busca_la_region_entera(con_banco):
    al = A.Alcance("regional", "Galicia", "Galicia")
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=al, rng=random.Random(2))
    assert {e.region for e in asig.encuestados} == {"Galicia"}
    assert len({e.subregion for e in asig.encuestados}) == 2                       # Pontevedra y Coruña (A): sin acotar a una provincia


def test_nacional_busca_gente_de_todo_el_pais(con_banco):
    """Una persona de Extremadura puede opinar de algo del País Vasco si el problema es nacional."""
    for al in (A.Alcance("nacional", "España"), A.Alcance(), None):
        asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=al, rng=random.Random(3))
        assert len({e.region for e in asig.encuestados}) >= 3


def test_el_lugar_del_modelo_solo_vale_si_el_banco_lo_conoce(con_banco):
    al = A.Alcance("local", "Vigo", "Extremadura-que-no-existe", "Provincia-que-no-existe")
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=al, rng=random.Random(4))
    assert len({e.region for e in asig.encuestados}) >= 3                          # no se aplicó: gente de todo el país


def test_un_grupo_que_se_define_por_otro_lugar_conserva_el_suyo(con_banco):
    al = A.Alcance("local", "Vigo", "Galicia", "Pontevedra")
    llm = lambda p: json.dumps({"a": {"region": ["Cataluña"]}, "b": {}, "c": {}})   # noqa: E731
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", llm, fuente=FUENTES["cis"], alcance=al, rng=random.Random(5))
    assert {e.region for e in asig.de_grupo("a")} == {"Cataluña"} and {e.region for e in asig.de_grupo("b")} == {"Galicia"}


def test_si_el_lugar_se_agota_se_completa_con_gente_de_la_misma_region(con_banco):
    al = A.Alcance("local", "Vigo", "Galicia", "Pontevedra")
    grupos = [poblacion.Grupo("a", "Muchos", "x", 120)]                            # más que los de Pontevedra del banco
    asig = poblacion.asignar_por_grupos(grupos, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=al, rng=random.Random(6))
    regiones = Counter(e.region for e in asig.encuestados)
    assert regiones["Galicia"] == 120 or regiones["Galicia"] > 100                  # primero Galicia entera, solo después el resto
    assert any("de la misma región" in a for a in asig.resumen()["avisos"])


# ---------------------------------------------------------------- el generador
class _LLMFalso:
    def __init__(self, alcance=None):
        self.prompts = []
        self.alcance = alcance if alcance is not None else {"nivel": "nacional", "lugar": "España", "motivo": "x"}
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        p = kw["messages"][-1]["content"]
        self.prompts.append(p)
        if "Decide el ALCANCE GEOGRÁFICO" in p:
            c = json.dumps(self.alcance)
        elif "Decide de qué país es el PÚBLICO" in p:
            c = '{"pais": "ES", "motivo": "España"}'
        elif "traduce la descripción" in p:
            c = "{}"
        elif "elige hasta" in p:
            c = '{"indices": [0, 1]}'
        else:
            c = ('{"bio": "Bio", "persona": "Persona", "profession": "jubilado", "interested_topics": ["salud"], "age": 3, '
                 '"gender": "male", "mbti": "INTJ", "country": "Japón"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=c), finish_reason="stop")])


def _generador(alcance=None):
    from app.services.oasis_profile_generator import OasisProfileGenerator
    g = OasisProfileGenerator.__new__(OasisProfileGenerator)
    g.api_key, g.base_url, g.model_name = "k", "http://x", "m"
    g.client, g.graph_id, g.zep_client = _LLMFalso(alcance), None, None
    return g


def _entidad(i, grupo="G"):
    from app.services.zep_entity_reader import EntityNode
    return EntityNode(uuid=f"u{i}", name=f"Persona {i}", labels=["Entity", "Person"], summary="Un público",
                      attributes={"__simuloo_individual": True, "__simuloo_group": grupo, "__simuloo_topic": "Subir el café"})


def test_el_lote_decide_y_guarda_el_alcance_aunque_no_haya_datos_reales(con_banco, tmp_path):
    g = _generador({"nivel": "local", "lugar": "Vigo", "region": "Galicia", "provincia": "Pontevedra", "motivo": "taberna"})
    ruta = str(tmp_path / A.FICHERO)
    perfiles = g.generate_profiles_from_entities([_entidad(0), _entidad(1)], parallel_count=1, poblacion_datos=False,
                                                 pregunta="¿Subir el café?", publico_descripcion="Cafetería de Vigo",
                                                 alcance_path=ruta)
    guardado = json.load(open(ruta, encoding="utf-8"))
    assert guardado["nivel"] == "local" and guardado["region"] == "Galicia" and guardado["etiqueta"].startswith("Local · Vigo")
    # las personas que no salen de la encuesta reciben la pista del lugar en el prompt
    persona = [p for p in g.client.prompts if "Alcance de la simulación: LOCAL (Vigo)" in p]
    assert len(persona) == 2 and all(p.data_source is None for p in perfiles)


def test_alcance_local_con_datos_reales_busca_gente_del_lugar(con_banco, tmp_path):
    g = _generador({"nivel": "local", "lugar": "Vigo", "region": "Galicia", "provincia": "Pontevedra", "motivo": "taberna"})
    ruta = str(tmp_path / "poblacion.json")
    perfiles = g.generate_profiles_from_entities([_entidad(i) for i in range(4)], parallel_count=1, poblacion_datos=True,
                                                 poblacion_pais="ES", pregunta="¿Subir el café?", publico_descripcion="Vigo",
                                                 poblacion_resumen_path=ruta)
    r = json.load(open(ruta, encoding="utf-8"))
    assert r["alcance"]["nivel"] == "local" and set(r["reparto"]["region"]) == {"Galicia"}
    assert all(p.data_source == "CIS" for p in perfiles)


def test_alcance_mundial_no_ancla_a_la_encuesta_de_un_pais_y_reparte_culturas(con_banco, tmp_path):
    g = _generador({"nivel": "mundial", "lugar": "", "motivo": "app global"})
    ruta = str(tmp_path / "poblacion.json")
    perfiles = g.generate_profiles_from_entities([_entidad(i, grupo=f"G{i}") for i in range(3)], parallel_count=1,
                                                 poblacion_datos=True, pregunta="¿App global?",
                                                 publico_descripcion="Todo el mundo", poblacion_resumen_path=ruta)
    r = json.load(open(ruta, encoding="utf-8"))
    assert r["sin_datos"] is True and "alcance es mundial" in r["motivo"] and r["pais_decidido_por"] == "alcance"
    assert all(p.data_source is None for p in perfiles)
    culturas = [p for p in g.client.prompts if "Alcance de la simulación: MUNDIAL" in p]
    import re
    assert len(culturas) == 3 and len({re.search(r"procede de «([^»]+)»", c).group(1) for c in culturas}) == 3   # una cultura por persona


def test_alcance_pedido_manda_sobre_el_del_modelo(con_banco, tmp_path):
    g = _generador({"nivel": "local", "lugar": "Vigo", "region": "Galicia", "provincia": "Pontevedra", "motivo": "taberna"})
    ruta = str(tmp_path / A.FICHERO)
    g.generate_profiles_from_entities([_entidad(0)], parallel_count=1, poblacion_datos=False, pregunta="p",
                                      publico_descripcion="d", alcance_pedido="nacional", alcance_path=ruta)
    guardado = json.load(open(ruta, encoding="utf-8"))
    assert guardado["nivel"] == "nacional" and guardado["origen"] == "pedido" and guardado["region"] is None


def test_el_informe_recibe_el_alcance_en_sus_prompts(con_banco, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path))
    os.makedirs(tmp_path / "sim_abc")
    A.guardar(str(tmp_path / "sim_abc" / A.FICHERO), A.Alcance("local", "Vigo", "Galicia", "Pontevedra"))
    from app.services.report_agent import ReportAgent
    ag = ReportAgent.__new__(ReportAgent)
    ag.alcance_texto = A.texto_para_informe(A.cargar("sim_abc"))
    nota = ag._nota_de_alcance()
    assert "[Alcance geográfico]" in nota and "Local · Vigo" in nota and "no las extrapoles al país" in nota
    ag.alcance_texto = ""
    assert ag._nota_de_alcance() == ""                                              # sin alcance decidido, el informe sale como siempre


# ---------------------------------------------------------------- API
from test_pipeline import storage  # noqa: E402,F401


@pytest.fixture()
def cliente(storage, monkeypatch):   # noqa: F811
    from app import create_app
    monkeypatch.setattr(Config, "API_AUTH_REQUIRED", True)
    monkeypatch.setattr(Config, "API_AUTH_TOKEN", "tok")
    app = create_app()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = False
    return app.test_client()


H = {"Authorization": "Bearer tok"}


def test_api_alcance_de_una_simulacion(cliente, storage):   # noqa: F811
    sid = "sim_alc123"
    assert cliente.get(f"/api/simulation/{sid}/alcance", headers=H).get_json() == {"success": True, "data": None}
    carpeta = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sid)
    os.makedirs(carpeta, exist_ok=True)
    A.guardar(os.path.join(carpeta, A.FICHERO), A.Alcance("regional", "Galicia", "Galicia", motivo="x"))
    d = cliente.get(f"/api/simulation/{sid}/alcance", headers=H).get_json()["data"]
    assert d["nivel"] == "regional" and d["etiqueta"] == "Regional · Galicia"
    assert cliente.get("/api/simulation/malo/alcance", headers=H).status_code in (400, 404)


def test_el_estado_de_una_regeneracion_en_curso_no_dice_listo_por_los_ficheros_viejos(cliente, storage, monkeypatch):   # noqa: F811
    """«Volver a generar» sobre una simulación ya preparada se daba por terminado a los 2 s, con los datos de antes."""
    from app.api import simulation as api
    from app.models.task import TaskManager, TaskStatus
    sid = "sim_regen1"
    monkeypatch.setattr(api, "_check_simulation_prepared", lambda s: (True, {"viejo": True}))
    tm = TaskManager()
    tarea = tm.create_task(task_type="simulation_prepare", metadata={"simulation_id": sid})
    tm.update_task(tarea, status=TaskStatus.PROCESSING, progress=15, message="regenerando")
    d = cliente.post("/api/simulation/prepare/status", json={"task_id": tarea, "simulation_id": sid}, headers=H).get_json()["data"]
    assert d["status"] == "processing" and d["already_prepared"] is False and d["progress"] == 15
    tm.update_task(tarea, status=TaskStatus.COMPLETED, progress=100, message="listo")
    d = cliente.post("/api/simulation/prepare/status", json={"task_id": tarea, "simulation_id": sid}, headers=H).get_json()["data"]
    assert d["status"] in ("ready", "completed")                                       # terminada: ahora sí vale lo preparado
    # sin tarea, un público ya preparado sigue dando «listo» (volver a abrir una simulación)
    d = cliente.post("/api/simulation/prepare/status", json={"simulation_id": sid}, headers=H).get_json()["data"]
    assert d["status"] == "ready" and d["already_prepared"] is True


# ---------------------------------------------------------------- Jev: decisiones cerradas y rápidas (el modelo grande, de respaldo)
from app.services.poblacion import jev as J          # noqa: E402
from app.services.poblacion import pais as P          # noqa: E402


class _JevFalso:
    """Sustituye a jev.preguntar: devuelve respuestas fijas según el id de cada pregunta y recuerda lo que se le preguntó."""
    def __init__(self, nivel="local", confianza=0.9, regiones=(), provincia="ninguna", prob_prov=0.9, noul=None):
        self.nivel, self.confianza, self.regiones, self.provincia, self.prob_prov = nivel, confianza, set(regiones), provincia, prob_prov
        self.noul = noul or {}
        self.llamadas = []

    def __call__(self, state, preguntas):
        self.llamadas.append((state, preguntas))
        out = {}
        for k in preguntas:
            if k == "nivel":
                out[k] = {"choice": self.nivel, "confidence": self.confianza, "probabilities": {self.nivel: self.confianza}}
            elif k == "provincia":
                out[k] = {"choice": self.provincia, "confidence": 0.9, "probabilities": {self.provincia: self.prob_prov}}
            elif k.startswith("region::"):
                out[k] = {"noul": 0.9 if k.split("::")[1] in self.regiones else 0.05}
            else:
                out[k] = {"noul": self.noul.get(k, 0.05)}
        return out


@pytest.fixture()
def con_jev(monkeypatch):
    monkeypatch.setattr(J, "disponible", lambda: True)
    return monkeypatch


def _sin_llm(prompt):                                  # si Jev decide, el modelo grande NO se llama
    raise AssertionError("no debía llamarse al modelo grande")


def test_con_jev_el_alcance_local_se_decide_sin_llamar_al_modelo_grande(con_banco, con_jev):
    falso = _JevFalso("local", regiones=["Galicia"], provincia="Pontevedra")
    con_jev.setattr(J, "preguntar", falso)
    a = A.detectar("auto", "pregunta", "Una taberna de Vigo", _sin_llm)
    # Jev no extrae el nombre del sitio: nunca se pasa la provincia por «el lugar» (era Vigo y salía Pontevedra)
    assert (a.nivel, a.region, a.provincia, a.lugar) == ("local", "Galicia", "Pontevedra", "") and "Jev" in a.motivo
    assert a.descripcion() == "Local · Galicia, Pontevedra"
    state, preguntas = falso.llamadas[0]
    assert state["brief"] == "Una taberna de Vigo" and "nivel" in preguntas and "provincia" in preguntas
    assert {"region::Galicia", "region::Madrid"} <= set(preguntas)                    # una pregunta de sí o no por región del banco
    assert "son de donde VIENEN" in preguntas["nivel"]["instructions"]
    assert preguntas["nivel"]["criteria"].keys() == set(A.NIVELES)                    # las cinco opciones


def test_con_jev_la_provincia_dice_la_region_si_no_se_marco_ninguna(con_banco, con_jev):
    con_jev.setattr(J, "preguntar", _JevFalso("local", regiones=[], provincia="Pontevedra"))
    a = A.detectar("auto", "p", "b", _sin_llm)
    assert (a.region, a.provincia) == ("Galicia", "Pontevedra")                       # la región sale del propio banco


def test_con_jev_varias_regiones_enteras_y_nacional_sin_lugar(con_banco, con_jev):
    con_jev.setattr(J, "preguntar", _JevFalso("regional", regiones=["Galicia", "Madrid"]))
    a = A.detectar("auto", "p", "b", _sin_llm)
    assert a.nivel == "regional" and a.regiones == ["Galicia", "Madrid"] and a.region is None and a.provincia is None
    con_jev.setattr(J, "preguntar", _JevFalso("nacional", regiones=["Galicia"], provincia="Pontevedra"))
    n = A.detectar("auto", "p", "b", _sin_llm)
    assert (n.nivel, n.region, n.regiones, n.provincia, n.lugar) == ("nacional", None, [], None, "")   # el país no sale del número de bancos
    con_jev.setattr(J, "preguntar", _JevFalso("mundial"))
    assert A.detectar("auto", "p", "b", _sin_llm).nivel == "mundial"


def test_si_jev_duda_falla_o_es_multinacional_decide_el_modelo_grande(con_banco, con_jev):
    visto = []
    llm = lambda p: visto.append(p) or json.dumps({"nivel": "nacional", "lugar": "España", "motivo": "modelo grande"})   # noqa: E731
    con_jev.setattr(J, "preguntar", _JevFalso("local", confianza=0.4, regiones=["Galicia"]))
    assert A.detectar("auto", "p", "b", llm).motivo == "modelo grande"               # poca confianza → respaldo
    con_jev.setattr(J, "preguntar", lambda s, q: None)                                # Jev caído → respaldo
    assert A.detectar("auto", "p", "b", llm).motivo == "modelo grande"
    con_jev.setattr(J, "preguntar", _JevFalso("multinacional"))                       # hacen falta los países por su nombre
    assert A.detectar("auto", "p", "b", llm).motivo == "modelo grande"
    assert len(visto) == 3


def test_jev_no_se_pregunta_si_la_persona_fijo_un_alcance_sin_lugar(con_banco, con_jev):
    con_jev.setattr(J, "preguntar", lambda s, q: (_ for _ in ()).throw(AssertionError("no debía preguntarse a Jev")))
    assert A.detectar("mundial", "p", "b", _sin_llm).origen == "pedido"
    n = A.detectar("nacional", "p", "b", _sin_llm)
    assert (n.nivel, n.lugar, n.origen) == ("nacional", "", "pedido")                  # un público mexicano no es «España» por tener solo ese banco


def test_el_cliente_de_jev_trocea_y_si_un_trozo_falla_no_devuelve_nada(monkeypatch):
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", "clave-falsa")
    monkeypatch.setattr(Config, "JEV_ENTITY_FILTER", True)
    pedidos = []

    def post(cliente, state, preguntas):
        pedidos.append(len(preguntas))
        return None if len(pedidos) == 2 else {k: {"noul": 1.0} for k in preguntas}

    monkeypatch.setattr(J, "_post", post)
    r = J.preguntar("estado", {f"q{i}": J.noul("x") for i in range(J.MAX_POR_PETICION + 5)})
    assert pedidos == [J.MAX_POR_PETICION, 5] and r is None                           # el segundo trozo falló: respuesta a medias, no vale
    pedidos.clear()
    ok = J.preguntar("estado", {f"q{i}": J.noul("x") for i in range(7)})
    assert len(ok) == 7 and pedidos == [7]
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", None)
    assert J.preguntar("estado", {"q": J.noul("x")}) is None                           # sin clave: camino lento


def test_preguntas_relevantes_con_jev_ordena_por_probabilidad_y_pide_al_menos_cinco(con_banco, con_jev):
    banco = Banco(con_banco, FUENTES["cis"])
    cat = banco.catalogo()
    assert len(cat) == 3
    visto = {}
    # tres preguntas en el banco sintético: con menos de 5 elegidas Jev no basta y se pasa al modelo grande
    # la pregunta «¿el tema es político?» también pasa por Jev: aquí, que no (es un café); y el resto, todo «sí»
    def jev(state, q):
        if "q0" in q:
            visto.setdefault("q", q)
        return {k: {"noul": 0.05 if k == "politico" else 0.9} for k in q}

    con_jev.setattr(J, "preguntar", jev)
    llm = lambda p: '{"indices": [2]}'                                               # noqa: E731
    assert poblacion.preguntas_relevantes(banco, "Subir el café", llm) == [cat[2]]
    assert all(f"«{q}»" in visto["q"][f"q{i}"]["instructions"] for i, q in enumerate(cat))   # la pregunta de la encuesta va en la pregunta a Jev


def test_el_pais_se_decide_con_jev_o_cae_al_modelo_grande(con_banco, con_jev):
    es = lambda sí: _JevFalso(noul={"pais::ES": sí})                                   # noqa: E731
    con_jev.setattr(J, "preguntar", es(0.9))
    d = P.detectar("auto", "pregunta", "brief", _sin_llm)
    assert d.fuente is not None and d.pais == "ES" and d.origen == "automatico" and "Jev" in d.motivo
    con_jev.setattr(J, "preguntar", es(0.02))
    d = P.detectar("auto", "pregunta", "brief", _sin_llm)
    assert d.fuente is None and d.origen == "ninguno"                                  # un no claro: público de otro sitio
    con_jev.setattr(J, "preguntar", es(0.5))                                           # duda → decide el modelo grande
    d = P.detectar("auto", "pregunta", "brief", lambda p: '{"pais": "ES", "motivo": "modelo grande"}')
    assert d.fuente is not None and d.motivo == "modelo grande"


# ---------------------------------------------------------------- correcciones de la revisión adversarial (3-oct-2026)
def test_sin_nombre_de_sitio_la_pista_y_el_informe_dicen_la_zona_real_no_un_parentesis_vacio():
    zona = A.Alcance("local", "", "Galicia", "Pontevedra")
    pista = A.pista_para_persona(zona)
    assert "LOCAL (Galicia, Pontevedra)" in pista and "al que se refiere el estudio" in pista
    informe = A.texto_para_informe(zona)
    assert "Local · Galicia, Pontevedra" in informe and "mercado local (Galicia, Pontevedra)" in informe
    sin_nada = A.texto_para_informe(A.Alcance("local"))
    assert "()" not in sin_nada and "(:" not in sin_nada and "ese lugar" in A.pista_para_persona(A.Alcance("local"))
    # sin lugar, el país del que habla el estudio (no «España» ni «de el país»)
    assert "el país del que habla el estudio" in A.pista_para_persona(A.Alcance("nacional"))


def test_el_informe_local_no_manda_inventar_competencia_ni_estacionalidad():
    t = A.texto_para_informe(A.Alcance("local", "Vigo", "Galicia"))
    assert "solo con lo que muestren la simulación y los documentos" in t and "no inventes datos de competencia" in t
    assert "competencia cercana" not in t and "estacionalidad del sitio" not in t


def test_con_jev_una_provincia_clara_manda_sobre_un_si_suelto_a_otra_region(con_banco, con_jev):
    # Jev dice Pontevedra con claridad y, por ruido, «sí» a Madrid: la región es la de la provincia, no se mezcla otra comunidad
    con_jev.setattr(J, "preguntar", _JevFalso("local", regiones=["Madrid"], provincia="Pontevedra"))
    a = A.detectar("auto", "p", "b", _sin_llm)
    assert (a.region, a.provincia, a.regiones) == ("Galicia", "Pontevedra", [])
    con_jev.setattr(J, "preguntar", _JevFalso("local", regiones=["Galicia", "Madrid"], provincia="Pontevedra"))
    assert A.detectar("auto", "p", "b", _sin_llm).region == "Galicia"                 # si una de las regiones sí es la suya, esa


def test_si_la_persona_fija_local_o_regional_se_sigue_preguntando_a_jev_donde(con_banco, con_jev):
    """Antes, fijar «local» con un brief que Jev veía nacional perdía el lugar y no se filtraba nada."""
    falso = _JevFalso("nacional", regiones=["Galicia"], provincia="Pontevedra")
    con_jev.setattr(J, "preguntar", falso)
    a = A.detectar("local", "p", "Taberna de Vigo", _sin_llm)
    assert (a.nivel, a.region, a.provincia, a.origen) == ("local", "Galicia", "Pontevedra", "pedido")
    assert "nivel" not in falso.llamadas[0][1]                                        # el nivel ya lo fijó la persona: no se pregunta
    b = A.detectar("regional", "p", "Taberna de Vigo", _sin_llm)
    assert (b.nivel, b.region, b.provincia) == ("regional", "Galicia", None)


def test_si_la_persona_fija_multinacional_los_paises_los_extrae_el_modelo_grande(con_banco, con_jev):
    con_jev.setattr(J, "preguntar", lambda s, q: (_ for _ in ()).throw(AssertionError("Jev no extrae países")))
    llm = _llm(nivel="multinacional", lugar="Iberia", lugares=["España", "Portugal"])
    a = A.detectar("multinacional", "p", "b", llm)
    assert (a.nivel, a.lugares, a.origen) == ("multinacional", ["España", "Portugal"], "pedido")   # antes se repartían las 10 culturas


def test_la_provincia_sin_region_deriva_la_region_del_banco_y_filtra(con_banco):
    # el modelo grande da provincia y no región: antes «acotaba» y no filtraba nada (gente de toda España para un proyecto de Vigo)
    a = A.detectar("auto", "p", "b", _llm(nivel="local", lugar="Vigo", region=None, provincia="Pontevedra"))
    assert (a.region, a.provincia) == ("Galicia", "Pontevedra")
    sin_region = A.Alcance("local", "Vigo", None, "Pontevedra")                       # alcance guardado de antes, solo con provincia
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", lambda p: "{}", fuente=FUENTES["cis"], alcance=sin_region, rng=random.Random(11))
    assert {e.region for e in asig.encuestados} == {"Galicia"} and {e.subregion for e in asig.encuestados} == {"Pontevedra"}


def test_un_grupo_con_la_misma_region_del_alcance_tambien_recibe_la_provincia(con_banco):
    al = A.Alcance("local", "Vigo", "Galicia", "Pontevedra")
    llm = lambda p: json.dumps({"a": {"region": ["Galicia"]}, "b": {}, "c": {}})      # noqa: E731
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", llm, fuente=FUENTES["cis"], alcance=al, rng=random.Random(12))
    assert {e.subregion for e in asig.de_grupo("a")} == {"Pontevedra"}                # antes salía de toda Galicia


def test_los_visitantes_de_fuera_no_se_fuerzan_al_lugar_del_alcance(con_banco):
    al = A.Alcance("local", "Santiago", "Galicia", "Coruña (A)")
    llm = lambda p: json.dumps({"a": {"fuera_del_lugar": True}, "b": {}, "c": {}})    # noqa: E731
    asig = poblacion.asignar_por_grupos(GRUPOS, "brief", llm, fuente=FUENTES["cis"], alcance=al, rng=random.Random(13))
    assert len({e.region for e in asig.de_grupo("a")}) >= 3                          # peregrinos: de todo el país
    assert {e.region for e in asig.de_grupo("b")} == {"Galicia"}                      # los vecinos, de allí
    assert "_fuera_del_lugar" not in json.dumps(asig.resumen())                        # la marca interna no sale al resumen
    assert "fuera_del_lugar" in nota_de_alcance(al)                                   # y el traductor sabe que puede marcarlo


def test_el_modelo_grande_con_tipos_raros_no_rompe_la_deteccion(con_banco):
    # `lugares` como texto se partía en letras y `regiones` no iterable abortaba detectar()
    a = A.detectar("auto", "p", "b", _llm(nivel="multinacional", lugar="x", lugares="España y Portugal", regiones=5))
    assert a.nivel == "multinacional" and a.lugares == ["España y Portugal"]
    b = A.detectar("auto", "p", "b", _llm(nivel="regional", lugar="Galicia", region="Galicia", regiones={"a": 1}))
    assert (b.nivel, b.region) == ("regional", "Galicia")
    c = A.detectar("auto", "p", "b", _llm(nivel="multinacional", lugares=[None, {"x": 1}, "Portugal", 3]))
    assert c.lugares == ["Portugal", "3"]


def test_las_culturas_se_reparten_por_orden_entre_las_personas_del_publico(con_banco, tmp_path):
    """Con un índice de entidad del grafo (instituciones, otros nodos en medio), tres personas podían caer en la misma cultura."""
    from app.services.zep_entity_reader import EntityNode
    g = _generador({"nivel": "mundial", "lugar": "", "motivo": "app global"})
    otras = lambda i: EntityNode(uuid=f"o{i}", name=f"Otro {i}", labels=["Entity", "Org"], summary="x", attributes={})   # noqa: E731
    entidades = [otras(0), _entidad(1, "G1"), otras(2), otras(3), _entidad(4, "G2"), otras(5), _entidad(6, "G3")]
    g.generate_profiles_from_entities(entidades, parallel_count=1, poblacion_datos=False, pregunta="¿App?", publico_descripcion="Mundo")
    import re
    culturas = [re.search(r"procede de «([^»]+)»", p).group(1) for p in g.client.prompts if "Alcance de la simulación: MUNDIAL" in p]
    assert len(culturas) == 3 and culturas == list(A.CULTURAS[:3])                    # 0, 1, 2 entre las del público, en orden


def test_con_alcance_mundial_la_persona_no_se_sitúa_en_el_pais_del_tema(con_banco):
    g = _generador({"nivel": "mundial", "lugar": "", "motivo": "app global"})
    g.generate_profiles_from_entities([_entidad(0)], parallel_count=1, poblacion_datos=False, pregunta="¿App?", publico_descripcion="Mundo")
    p = [x for x in g.client.prompts if "Alcance de la simulación: MUNDIAL" in x][0]
    assert "vive en el país o la región de los que habla ese tema" not in p and "procede de «" in p
    g2 = _generador({"nivel": "local", "lugar": "Vigo", "region": "Galicia", "provincia": "Pontevedra", "motivo": "x"})
    g2.generate_profiles_from_entities([_entidad(0)], parallel_count=1, poblacion_datos=False, pregunta="¿Café?", publico_descripcion="Vigo")
    assert any("vive en el país o la región de los que habla ese tema" in x for x in g2.client.prompts)


def test_un_pais_elegido_a_mano_manda_sobre_un_alcance_mundial_deducido(con_banco, tmp_path):
    g = _generador({"nivel": "mundial", "lugar": "", "motivo": "app global"})
    ruta, ruta_alc = str(tmp_path / "poblacion.json"), str(tmp_path / A.FICHERO)
    perfiles = g.generate_profiles_from_entities([_entidad(i, grupo=f"G{i}") for i in range(3)], parallel_count=1,
                                                 poblacion_datos=True, poblacion_pais="ES", pregunta="¿App?",
                                                 publico_descripcion="Todo el mundo", poblacion_resumen_path=ruta,
                                                 alcance_path=ruta_alc)
    guardado = json.load(open(ruta_alc, encoding="utf-8"))
    assert guardado["nivel"] == "nacional" and guardado["lugar"] == "España" and guardado["origen"] == "pedido"
    assert all(p.data_source == "CIS" for p in perfiles)                               # personas e informe, de acuerdo


def test_con_alcance_mundial_no_se_gasta_la_deteccion_del_pais(con_banco):
    g = _generador({"nivel": "mundial", "lugar": "", "motivo": "app global"})
    g.generate_profiles_from_entities([_entidad(0)], parallel_count=1, poblacion_datos=True, pregunta="¿App?", publico_descripcion="Mundo")
    assert not any("Decide de qué país es el PÚBLICO" in p for p in g.client.prompts)


def test_nacional_toma_el_pais_de_la_deteccion_del_pais_no_del_numero_de_bancos(con_banco, tmp_path):
    g = _generador({"nivel": "nacional", "lugar": "", "motivo": "x"})
    ruta_alc = str(tmp_path / A.FICHERO)
    g.generate_profiles_from_entities([_entidad(0), _entidad(1)], parallel_count=1, poblacion_datos=True, pregunta="¿Café?",
                                      publico_descripcion="Todo el país", alcance_path=ruta_alc)
    assert json.load(open(ruta_alc, encoding="utf-8"))["lugar"] == "España"           # la detección de país confirmó España
    g2 = _generador({"nivel": "nacional", "lugar": "", "motivo": "x"})
    ruta2 = str(tmp_path / "otro.json")
    g2.generate_profiles_from_entities([_entidad(0)], parallel_count=1, poblacion_datos=False, pregunta="¿Café?",
                                       publico_descripcion="Todo México", alcance_path=ruta2)
    assert json.load(open(ruta2, encoding="utf-8"))["lugar"] == ""                    # sin datos reales, ningún país inventado


def test_jev_no_reintenta_un_4xx_y_tras_un_fallo_del_servicio_no_vuelve_a_esperar(monkeypatch):
    import httpx
    monkeypatch.setattr(Config, "TYPESAFE_API_KEY", "clave-falsa")
    monkeypatch.setattr(Config, "JEV_ENTITY_FILTER", True)
    monkeypatch.setattr(J, "_caido_hasta", 0.0)
    monkeypatch.setattr(J.time, "sleep", lambda s: None)
    llamadas = []

    class Cliente:
        def __init__(self, estado):
            self.estado = estado

        def post(self, url, json=None):
            llamadas.append(self.estado)
            if self.estado == "red":
                raise httpx.ConnectTimeout("lento")
            return httpx.Response(self.estado, json={"error": "x"}, request=httpx.Request("POST", url))

    assert J._post(Cliente(400), "s", {"q": J.noul("x")}) is None and llamadas == [400]      # no se repite una petición mala
    assert J.disponible()                                                                  # y no apaga Jev: era un error nuestro
    llamadas.clear()
    assert J._post(Cliente("red"), "s", {"q": J.noul("x")}) is None and len(llamadas) == 3  # el servicio no responde: 3 intentos
    assert not J.disponible()                                                              # las decisiones siguientes van directas al modelo grande
    monkeypatch.setattr(J, "_caido_hasta", 0.0)
    assert J.disponible()


def test_con_pocas_personas_las_primeras_culturas_ya_incluyen_oriente_y_occidente():
    """Con 3 personas solo se usan las 3 primeras culturas: antes eran Europa, Norteamérica y Latinoamérica (todo occidental)."""
    assert len(set(A.CULTURAS)) == len(A.CULTURAS) == 10
    assert A.CULTURAS[:3] == ("Europa occidental", "Asia oriental", "Latinoamérica")
    assert any("Asia" in A.pista_para_persona(A.Alcance("mundial"), i) for i in range(3))
    assert any("Asia oriental" in A.pista_para_persona(A.Alcance("mundial"), i) for i in range(2))


def test_api_prepare_acepta_audience_size_acotado():
    """`audience_size` llega al gestor solo si es un entero de 5 a 150; cualquier otra cosa se ignora."""
    from app.api.simulation import _normalizar_audience_size as norm
    assert [norm(x) for x in (70, 5, 150, 4, 151, True, "70", 70.0, None, -3)] == [70, 5, 150, None, None, None, None, None, None, None]
