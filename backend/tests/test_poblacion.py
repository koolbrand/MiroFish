"""Público con datos reales (CIS): filtrado, muestreo, ficha, vocabulario cerrado y modo apagado.
Todo con un banco sintético inventado (tests/poblacion_fixture.py)."""

import random
from types import SimpleNamespace

import pytest

from app.config import Config
from app.services import poblacion
from app.services.poblacion import ficha as F
from app.services.poblacion.banco import BancoCIS
from app.services.poblacion.filtros import traducir_publico, validar
from poblacion_fixture import crear_banco


@pytest.fixture()
def banco_path(tmp_path):
    return crear_banco(str(tmp_path / "banco.sqlite"))


@pytest.fixture()
def banco(banco_path):
    return BancoCIS(banco_path)


@pytest.fixture()
def con_banco(banco_path, monkeypatch):
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", banco_path)
    monkeypatch.setattr(Config, "POBLACION_CIS", False)
    return banco_path


# ---------------------------------------------------------------- banco / filtrado
def test_disponible_solo_si_existe_y_tiene_gente(tmp_path, banco_path):
    assert BancoCIS.disponible(banco_path)
    assert not BancoCIS.disponible(str(tmp_path / "no_existe.sqlite"))
    assert not BancoCIS.disponible(None)
    vacio = tmp_path / "vacio.sqlite"
    from app.services.poblacion import banco as B
    c = B.abrir(str(vacio)); B.crear_esquema(c); c.close()
    assert not BancoCIS.disponible(str(vacio))


def test_filtrado_por_sexo_y_edad(banco):
    seg = banco.segmento({"sexo": ["Mujer"], "edad_min": 40, "edad_max": 60}, minimo=1)
    assert seg.ids and not seg.relajado
    for i in seg.ids:
        e = banco.encuestado(i)
        assert e.sexo == "Mujer" and 40 <= e.edad <= 60


def test_segmento_corto_se_relaja_y_lo_dice(banco):
    seg = banco.segmento({"sexo": ["Mujer"], "ccaa": ["Galicia"], "estudios": ["universitarios"],
                          "tramo": ["25-34"], "estcivil": ["casado"], "tamuni": ["rural"]}, minimo=30)
    assert seg.relajado
    assert len(seg.ids) >= 30
    assert seg.avisos and "filtro" in seg.avisos[0]
    assert set(seg.filtros_aplicados) < set(seg.filtros_pedidos)


def test_los_pesos_de_cada_estudio_suman_uno(banco):
    seg = banco.segmento({}, minimo=1)
    assert sum(seg.pesos) == pytest.approx(2.0)   # dos estudios sintéticos


# ---------------------------------------------------------------- muestreo
def test_muestreo_sin_repetir_y_respeta_excluidos(banco):
    seg = banco.segmento({}, minimo=1)
    a = banco.muestrear(seg, 40, rng=random.Random(1))
    assert len(a) == len(set(a)) == 40
    b = banco.muestrear(seg, 40, excluidos=set(a), rng=random.Random(2))
    assert not set(a) & set(b)


def test_muestreo_devuelve_menos_si_no_hay_casos(banco):
    seg = banco.segmento({"sexo": ["Hombre"]}, minimo=1)
    assert len(banco.muestrear(seg, 10_000)) == len(seg.ids)


def test_muestreo_es_ponderado(banco):
    from app.services.poblacion.banco import Segmento
    seg = Segmento([1, 2], [0.99, 0.01], {}, {}, False, [])
    veces = sum(1 for s in range(400) if banco.muestrear(seg, 1, rng=random.Random(s)) == [1])
    assert veces > 340


def test_asignar_no_repite_a_nadie_y_completa_si_el_segmento_se_agota(con_banco):
    asig = poblacion.asignar(30, "", llm=None, rng=random.Random(3))
    ids = [e.id for e in asig.encuestados]
    assert len(ids) == len(set(ids)) == 30
    # un llm que pide un segmento diminuto: se completa con población general y se avisa
    asig = poblacion.asignar(100, "x", llm=lambda p: '{"sexo": ["Mujer"], "tramo": ["65+"]}', rng=random.Random(3))
    assert len({e.id for e in asig.encuestados}) == len(asig.encuestados) == 100
    assert any("completó" in a for a in asig.segmento.avisos)


def test_reparto_suma_cien_aprox(con_banco):
    r = poblacion.asignar(40, "", rng=random.Random(5)).reparto()
    assert r["n"] == 40
    assert abs(sum(r["sexo"].values()) - 100) <= 2


# ---------------------------------------------------------------- ficha
def test_ficha_prioriza_no_politicas_y_respeta_el_tope(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    ficha = F.construir_ficha(e)
    assert "Datos sociodemográficos" in ficha and f"{e.edad} años" in ficha
    assert ficha.index("confía en sus vecinos") < ficha.index("partido")
    corta = F.construir_ficha(e, max_chars=330)
    assert len(corta) <= 330 and "Datos sociodemográficos" in corta


def test_ficha_recorta_respuestas_larguisimas(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = [{"pregunta": "P", "respuesta": "x" * 900, "politica": 0}]
    assert len(F.construir_ficha(e)) < 600


def test_hechos_de_memoria_y_genero(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    hechos = F.hechos_memoria(e, maximo=3)
    assert len(hechos) == 3 and all("respondió" in h for h in hechos)
    assert F.genero_oasis(e) in ("male", "female")


# ---------------------------------------------------------------- vocabulario cerrado
def test_validar_descarta_lo_que_no_esta_en_el_vocabulario():
    assert validar({"sexo": "Mujer", "ccaa": ["Galicia", "Narnia"], "ingresos": ["altos"], "edad_min": "30"}) == \
        {"sexo": ["Mujer"], "ccaa": ["Galicia"], "edad_min": 30}
    assert validar({"edad_min": 70, "edad_max": 30}) == {}
    assert validar({"edad_min": 5}) == {}
    assert validar("basura") == {}


def test_traducir_publico_tolera_prosa_y_fallos():
    ok = traducir_publico("madres gallegas de 35 a 50", lambda p: 'Claro: {"sexo": ["Mujer"], "ccaa": ["Galicia"], "edad_min": 35, "edad_max": 50}')
    assert ok == {"sexo": ["Mujer"], "ccaa": ["Galicia"], "edad_min": 35, "edad_max": 50}
    assert traducir_publico("x", lambda p: "no es json") == {}
    def roto(p): raise RuntimeError("boom")
    assert traducir_publico("x", roto) == {}
    assert traducir_publico("", lambda p: "{}") == {}
    assert traducir_publico("x", None) == {}


# ---------------------------------------------------------------- modo apagado y generador
def test_modo_activo_exige_banco_y_respeta_el_interruptor(con_banco, monkeypatch, tmp_path):
    assert not poblacion.modo_activo()                 # POBLACION_CIS apagado y sin petición
    assert poblacion.modo_activo(True)
    assert not poblacion.modo_activo(False)
    monkeypatch.setattr(Config, "POBLACION_CIS", True)
    assert poblacion.modo_activo()
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", str(tmp_path / "no.sqlite"))
    assert not poblacion.modo_activo(True)             # sin banco, nunca


class _LLMFalso:
    """Cliente OpenAI mínimo: devuelve un perfil JSON fijo y guarda los prompts que recibe."""
    def __init__(self):
        self.prompts = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.prompts.append(kw["messages"][-1]["content"])
        contenido = '{"bio": "Bio", "persona": "Persona redactada", "profession": "jubilado", "interested_topics": ["salud"], "age": 3, "gender": "male", "mbti": "INTJ", "country": "Japón"}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido), finish_reason="stop")])


def _generador():
    from app.services.oasis_profile_generator import OasisProfileGenerator
    g = OasisProfileGenerator.__new__(OasisProfileGenerator)
    g.api_key, g.base_url, g.model_name = "k", "http://x", "m"
    g.client, g.graph_id, g.zep_client = _LLMFalso(), None, None
    return g


def _entidad(i, publico=True):
    from app.services.zep_entity_reader import EntityNode
    return EntityNode(uuid=f"u{i}", name=f"Persona {i}", labels=["Entity", "Person"], summary="Un público",
                      attributes={"__simuloo_individual": True} if publico else {})


def test_anclado_toma_edad_genero_region_del_dato_real(con_banco):
    g = _generador()
    enc = BancoCIS(con_banco).encuestado(BancoCIS(con_banco).segmento({}, minimo=1).ids[0])
    p = g.generate_profile_from_entity(_entidad(1), 1, encuestado=enc)
    assert p.age == enc.edad and p.gender == F.genero_oasis(enc)
    assert p.country == "España" and p.mbti is None                      # no se inventa el MBTI ni el país
    assert (p.data_source, p.data_ref) == ("CIS", enc.estudio)
    assert p.memory_facts and "respondió" in p.memory_facts[0]
    prompt = g.client.prompts[-1]
    assert "DATA SHEET" in prompt and f"{enc.edad} años" in prompt and "do NOT contradict" in prompt
    assert p.to_reddit_format()["data_source"] == "CIS"


def test_modo_apagado_es_identico_a_hoy(con_banco):
    g = _generador()
    enc = BancoCIS(con_banco).encuestado(BancoCIS(con_banco).segmento({}, minimo=1).ids[0])
    sin = g.generate_profile_from_entity(_entidad(1), 1)                 # sin encuestado
    assert sin.data_source is None and sin.memory_facts == [] and sin.age == 3 and sin.mbti == "INTJ"
    assert "data_source" not in sin.to_reddit_format()
    assert "DATA SHEET" not in g.client.prompts[-1]
    # una entidad que no es público no se ancla aunque llegue un encuestado
    emp = g.generate_profile_from_entity(_entidad(2, publico=False), 2, encuestado=enc)
    assert emp.data_source is None


def test_generar_lote_ancla_solo_al_publico_y_no_repite(con_banco, tmp_path, monkeypatch):
    g = _generador()
    ents = [_entidad(0), _entidad(1, publico=False), _entidad(2), _entidad(3)]
    ruta = str(tmp_path / "poblacion_cis.json")
    perfiles = g.generate_profiles_from_entities(ents, parallel_count=1, poblacion_cis=True,
                                                 publico_descripcion="", poblacion_resumen_path=ruta)
    assert [p.data_source for p in perfiles] == ["CIS", None, "CIS", "CIS"]
    import json
    resumen = json.load(open(ruta, encoding="utf-8"))
    assert resumen["reparto"]["n"] == 3 and resumen["fuente"] == "Fuente de datos: CIS"
    # apagado: nadie anclado y no se escribe el resumen
    perfiles = g.generate_profiles_from_entities(ents, parallel_count=1, poblacion_cis=False)
    assert all(p.data_source is None for p in perfiles)


def test_cita_de_simulacion(con_banco, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path))
    assert poblacion.cita_de_simulacion("sim_x") == ""
    (tmp_path / "sim_x").mkdir()
    (tmp_path / "sim_x" / "poblacion_cis.json").write_text('{"estudios": ["3535"]}', encoding="utf-8")
    assert poblacion.cita_de_simulacion("sim_x") == "Fuente de datos: CIS (estudio 3535)"


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


def test_api_estado_sin_banco(cliente, monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", str(tmp_path / "no.sqlite"))
    d = cliente.get("/api/simulation/poblacion/estado", headers=H).get_json()["data"]
    assert d["disponible"] is False and d["estudios"] == []


def test_api_estado_con_banco_y_por_defecto(cliente, con_banco, monkeypatch):
    monkeypatch.setattr(Config, "POBLACION_CIS", True)
    d = cliente.get("/api/simulation/poblacion/estado", headers=H).get_json()["data"]
    assert d["disponible"] and d["por_defecto"] is True and len(d["estudios"]) == 2
    assert d["fuente"] == "Fuente de datos: CIS"


def test_api_poblacion_de_una_simulacion(cliente, storage, monkeypatch):   # noqa: F811
    sid = "sim_abc123"
    assert cliente.get(f"/api/simulation/{sid}/poblacion", headers=H).get_json() == {"success": True, "data": None}
    import json, os
    carpeta = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sid)
    os.makedirs(carpeta, exist_ok=True)
    json.dump({"estudios": ["3535"], "reparto": {"n": 5}}, open(os.path.join(carpeta, "poblacion_cis.json"), "w"))
    d = cliente.get(f"/api/simulation/{sid}/poblacion", headers=H).get_json()["data"]
    assert d["estudios"] == ["3535"]
    assert cliente.get("/api/simulation/malo/poblacion", headers=H).status_code in (400, 404)


def test_pdf_lleva_la_fuente_en_pie_y_nota():
    from app.services import report_pdf as rp
    html = rp.build_html(title="T", summary="", question="", body_html="<p>x</p>", locale="es",
                         meta={"fuente_datos": "Fuente de datos: CIS (estudio 3535)"})
    assert html.count("Fuente de datos: CIS (estudio 3535)") == 2     # pie de página (@bottom-center) y nota
    sin = rp.build_html(title="T", summary="", question="", body_html="<p>x</p>", locale="es", meta={})
    assert "Fuente de datos" not in sin
