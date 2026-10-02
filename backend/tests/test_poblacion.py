"""Público con datos reales POR PAÍS: bancos, filtrado, muestreo, asignación por grupos, detección del país, ficha,
vocabulario cerrado, anti-estereotipo y modo apagado. Todo con bancos sintéticos inventados (tests/poblacion_fixture.py)."""

import json
import os
import random
from collections import Counter
from types import SimpleNamespace

import pytest

from app.config import Config
from app.services import poblacion
from app.services.poblacion import ficha as F
from app.services.poblacion.banco import Banco
from app.services.poblacion.filtros import traducir_grupos, traducir_publico, validar
from app.services.poblacion.fuentes import FUENTES, olvidar
from poblacion_fixture import crear_banco, registrar_pais_sintetico


@pytest.fixture()
def banco_path(tmp_path):
    # 600 personas: los segmentos estrechos («mujeres de 25 a 40») deben llegar a los 30 casos sin que se relajen
    return crear_banco(str(tmp_path / "banco.sqlite"), n=600)


@pytest.fixture()
def banco(banco_path):
    return Banco(banco_path, FUENTES["cis"])


@pytest.fixture()
def con_banco(banco_path, monkeypatch, tmp_path):
    """Solo España (CIS sintético). Apagado por defecto, como en producción."""
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", banco_path)
    monkeypatch.setattr(Config, "POBLACION_BANCOS_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "POBLACION_DATOS_REALES", False)
    return banco_path


@pytest.fixture()
def dos_paises(con_banco, tmp_path):
    """España (CIS) y Estados Unidos (GSS), cada uno con su banco. En EE. UU. las mujeres de 25–64 son sobre todo
    «labores del hogar» y en España sobre todo «trabaja»: sirve para comprobar que cada país habla con sus datos."""
    registrar_pais_sintetico(tmp_path, n=400, semilla=11, sitlab_mujeres=["labores_hogar"] * 3 + ["trabaja"])
    os.remove(con_banco)                                   # se rehace el de España con su propia distribución
    crear_banco(con_banco, n=400, semilla=7, sitlab_mujeres=["trabaja"] * 3 + ["labores_hogar"])
    yield tmp_path
    olvidar("gss")


# ---------------------------------------------------------------- registro de fuentes
def test_disponibles_solo_las_que_tienen_banco(con_banco, tmp_path):
    assert [f.id for f in poblacion.disponibles()] == ["cis"]
    registrar_pais_sintetico(tmp_path)
    try:
        assert [f.id for f in poblacion.disponibles()] == ["cis", "gss"]
        assert poblacion.fuente_de_pais("us").id == "gss" and poblacion.fuente_de_pais("ES").id == "cis"
        assert poblacion.fuente_de_pais("FR") is None and poblacion.fuente_de_pais(None) is None
    finally:
        olvidar("gss")
    assert poblacion.fuente_de_pais("US") is None


def test_toda_fuente_nace_como_uso_interno_y_cita_su_nombre():
    cis = FUENTES["cis"]
    assert cis.uso_interno and cis.cita == "Fuente de datos: CIS" and cis.pais == "ES"
    assert "Comunidad autónoma" == cis.etiqueta_region


def test_el_banco_deja_escrito_de_que_fuente_y_pais_es(banco_path):
    fila = {k: v for k, v in Banco(banco_path).conn.execute("SELECT k, v FROM meta").fetchall()}
    assert fila == {"fuente": "cis", "pais": "ES"}


# ---------------------------------------------------------------- banco / filtrado
def test_disponible_solo_si_existe_y_tiene_gente(tmp_path, banco_path):
    assert Banco.disponible(banco_path)
    assert not Banco.disponible(str(tmp_path / "no_existe.sqlite"))
    assert not Banco.disponible(None)
    vacio = tmp_path / "vacio.sqlite"
    from app.services.poblacion import banco as B
    c = B.abrir(str(vacio)); B.crear_esquema(c); c.close()
    assert not Banco.disponible(str(vacio))


def test_filtrado_por_sexo_y_edad(banco):
    seg = banco.segmento({"sexo": ["Mujer"], "edad_min": 40, "edad_max": 60}, minimo=1)
    assert seg.ids and not seg.relajado
    for i in seg.ids:
        e = banco.encuestado(i)
        assert e.sexo == "Mujer" and 40 <= e.edad <= 60


def test_segmento_corto_se_relaja_y_lo_dice(banco):
    seg = banco.segmento({"sexo": ["Mujer"], "region": ["Galicia"], "estudios": ["universitarios"],
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


# ---------------------------------------------------------------- asignación por grupos
def test_asignar_no_repite_a_nadie_y_completa_si_el_segmento_se_agota(con_banco):
    asig = poblacion.asignar(30, "", llm=None, rng=random.Random(3))
    ids = [e.id for e in asig.encuestados]
    assert len(ids) == len(set(ids)) == 30
    # un llm que pide un segmento diminuto: se completa con población general y se avisa
    asig = poblacion.asignar(100, "x", llm=lambda p: '{"publico": {"sexo": ["Mujer"], "tramo": ["65+"]}}',
                             rng=random.Random(3))
    assert len({e.id for e in asig.encuestados}) == len(asig.encuestados) == 100
    assert any("completó" in a for a in asig.resumen()["avisos"])


def test_cada_grupo_recibe_a_los_suyos_y_nadie_se_repite(con_banco):
    grupos = [poblacion.Grupo("g_jub", "Jubilados", "Personas jubiladas", 5),
              poblacion.Grupo("g_muj", "Madres jóvenes", "Madres de 25 a 40 años", 5),
              poblacion.Grupo("g_gen", "Vecinos", "El barrio en general", 8)]
    llm = lambda p: json.dumps({"g_jub": {"sitlab": ["jubilado"]},                    # noqa: E731
                                "g_muj": {"sexo": ["Mujer"], "edad_min": 25, "edad_max": 40}, "g_gen": {}})
    asig = poblacion.asignar_por_grupos(grupos, "barrio", llm, fuente=FUENTES["cis"], rng=random.Random(4))
    assert all(e.sitlab == "jubilado" for e in asig.de_grupo("g_jub")) and len(asig.de_grupo("g_jub")) == 5
    assert all(e.sexo == "Mujer" and 25 <= e.edad <= 40 for e in asig.de_grupo("g_muj"))
    ids = [e.id for e in asig.encuestados]
    assert len(ids) == len(set(ids)) == 18
    assert asig.resumen()["reparto"]["n"] == 18 and len(asig.resumen()["grupos"]) == 3


def test_los_segmentos_estrechos_eligen_primero(con_banco):
    """Un grupo común no le puede quitar la gente a uno raro: el raro elige antes."""
    raro = poblacion.Grupo("raro", "Mayores de 80", "", 3)
    comun = poblacion.Grupo("comun", "Todos", "", 100)
    llm = lambda p: json.dumps({"raro": {"edad_min": 80}, "comun": {}})              # noqa: E731
    asig = poblacion.asignar_por_grupos([comun, raro], "", llm, fuente=FUENTES["cis"], rng=random.Random(9))
    assert len(asig.de_grupo("raro")) == 3 and all(e.edad >= 80 for e in asig.de_grupo("raro"))


def test_sin_banco_del_pais_no_se_ancla(con_banco):
    g = [poblacion.Grupo("g", "X", "", 3)]
    assert poblacion.asignar_por_grupos(g, "", None, pais="FR") is None                # país sin banco
    assert poblacion.asignar_por_grupos(g, "", None, pais=None) is None                # sin país ni LLM: no se adivina
    assert poblacion.asignar_por_grupos([], "", None, pais="ES") is None


# ---------------------------------------------------------------- país: cada uno habla con sus datos
def test_detectar_respeta_lo_pedido_y_solo_ofrece_paises_con_banco(dos_paises):
    d = poblacion.detectar("US", "", "", None)
    assert d.fuente.id == "gss" and d.origen == "pedido" and d.pais == "US"
    d = poblacion.detectar("FR", "", "", None)
    assert d.fuente is None and "FR" in d.motivo
    d = poblacion.detectar(None, "", "", None)
    assert d.fuente is None                                                              # sin texto ni LLM no se adivina


def test_detectar_automatico_pregunta_al_modelo_y_no_inventa(dos_paises):
    visto = {}

    def llm(prompt):
        visto["p"] = prompt
        return 'Claro: {"pais": "US", "motivo": "El brief habla de amas de casa de Ohio."}'

    d = poblacion.detectar("auto", "¿Comprarían el producto?", "Amas de casa de Ohio", llm)
    assert d.fuente.id == "gss" and d.origen == "automatico" and "Ohio" in d.motivo
    assert "US: Estados Unidos" in visto["p"] and "ES: España" in visto["p"]            # solo la lista de los que tienen banco
    assert "No supongas el país por el idioma" in visto["p"]
    # el modelo devuelve un país sin banco, null, basura o falla → ninguno (mejor no anclar que anclar a la gente equivocada)
    for respuesta in ('{"pais": "FR"}', '{"pais": null, "motivo": "varios países"}', "no sé", ""):
        assert poblacion.detectar("auto", "p", "c", lambda p, r=respuesta: r).fuente is None
    def roto(p): raise RuntimeError("boom")
    assert poblacion.detectar("auto", "p", "c", roto).fuente is None


def test_cada_pais_usa_su_banco_y_sus_regiones(dos_paises):
    g = [poblacion.Grupo("g", "Público", "", 10)]
    us = poblacion.asignar_por_grupos(g, "", None, pais="US", rng=random.Random(1))
    es = poblacion.asignar_por_grupos(g, "", None, pais="ES", rng=random.Random(1))
    assert {e.region for e in us.encuestados} <= {"Texas", "Ohio", "California", "Florida"}
    assert {e.region for e in es.encuestados} <= {"Madrid", "Galicia", "Cataluña", "Andalucía"}
    assert us.resumen()["pais"] == "US" and us.resumen()["etiqueta_region"] == "Estado"
    assert es.resumen()["pais_nombre"] == "España" and es.resumen()["cita"] == "Fuente de datos: CIS"


def test_la_misma_descripcion_da_gente_distinta_segun_el_pais(dos_paises):
    """«Mujeres de 25 a 64»: en el banco de EE. UU. son sobre todo amas de casa y en el de España sobre todo
    trabajadoras. El filtro no dice nada de la situación laboral: la pone el dato de cada país, no un tópico."""
    llm = lambda p: '{"g": {"sexo": ["Mujer"], "edad_min": 25, "edad_max": 64}}'          # noqa: E731
    g = [poblacion.Grupo("g", "Mujeres adultas", "Mujeres de 25 a 64 años", 40)]
    frac = {}
    for pais in ("US", "ES"):
        asig = poblacion.asignar_por_grupos(g, "", llm, pais=pais, rng=random.Random(5))
        c = Counter(e.sitlab for e in asig.encuestados)
        frac[pais] = c["labores_hogar"] / 40
    assert frac["US"] - frac["ES"] > 0.25, frac


def test_el_resumen_no_mezcla_paises_ni_pierde_el_origen_de_la_decision(dos_paises):
    d = poblacion.detectar("auto", "p", "c", lambda p: '{"pais": "ES", "motivo": "Público de Madrid"}')
    asig = poblacion.asignar_por_grupos([poblacion.Grupo("g", "X", "", 4)], "c", None, fuente=d.fuente,
                                        deteccion=d, rng=random.Random(2))
    r = asig.resumen()
    assert r["pais"] == "ES" and r["pais_decidido_por"] == "automatico" and r["pais_motivo"] == "Público de Madrid"
    assert r["uso_interno"] is True


# ---------------------------------------------------------------- ficha
def test_ficha_prioriza_no_politicas_y_respeta_el_tope(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    ficha = F.construir_ficha(e)
    assert "Datos sociodemográficos" in ficha and f"{e.edad} años" in ficha
    assert ficha.index("confía en sus vecinos") < ficha.index("partido")
    corta = F.construir_ficha(e, max_chars=330)
    assert len(corta) <= 330 and "Datos sociodemográficos" in corta


def test_ficha_nombra_la_region_como_se_llama_en_cada_pais(dos_paises):
    es = Banco(Config.POBLACION_BANCO_PATH, FUENTES["cis"])
    us = poblacion.abrir_banco(FUENTES["gss"])
    e_es, e_us = es.encuestado(es.segmento({}, minimo=1).ids[0]), us.encuestado(us.segmento({}, minimo=1).ids[0])
    assert "Comunidad autónoma:" in F.construir_ficha(e_es, fuente=FUENTES["cis"])
    assert "Estado:" in F.construir_ficha(e_us, fuente=FUENTES["gss"])


def test_las_preguntas_con_nombre_propio_van_al_final_de_la_ficha(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = [{"pregunta": "Sara Aagesen", "respuesta": "No conoce", "politica": 0},
                    {"pregunta": "José Manuel Albares", "respuesta": "Conoce", "politica": 0},
                    {"pregunta": "Grado de preocupación por el cambio climático", "respuesta": "Bastante", "politica": 0},
                    {"pregunta": "La bandera", "respuesta": "Mucho", "politica": 0}]
    orden = [r["pregunta"] for r in F.respuestas_priorizadas(e)]
    assert orden[0] == "Grado de preocupación por el cambio climático"
    assert set(orden[1:]) == {"Sara Aagesen", "José Manuel Albares", "La bandera"}   # sin enunciado propio: ambiguas


def test_el_tema_de_la_simulacion_manda_en_la_ficha_y_lo_politico_tiene_tope(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = (
        [{"pregunta": f"Valoración de la política número {i} del partido", "respuesta": "Mala", "politica": 1} for i in range(8)]
        + [{"pregunta": "Grado de preocupación por los incendios forestales", "respuesta": "Mucho", "politica": 0},
           {"pregunta": "Frecuencia con la que compra productos de limpieza para el hogar", "respuesta": "A diario", "politica": 0},
           {"pregunta": "Opinión sobre el precio de los productos de limpieza", "respuesta": "Caros", "politica": 0}])
    orden = [r["pregunta"] for r in F.respuestas_priorizadas(e, tema="Un nuevo producto de limpieza para el hogar")]
    assert set(orden[:2]) == {"Frecuencia con la que compra productos de limpieza para el hogar",
                              "Opinión sobre el precio de los productos de limpieza"}
    assert orden[2] == "Grado de preocupación por los incendios forestales"
    assert len(orden) == 3 + F.MAX_AL_FINAL                       # ocho políticas, pero solo entran cuatro
    sin_tema = [r["pregunta"] for r in F.respuestas_priorizadas(e)]
    assert sin_tema[0] == "Grado de preocupación por los incendios forestales"   # sin tema, el orden del estudio
    assert "limpieza" in F.construir_ficha(e, tema="producto de limpieza").split("incendios")[0]


def test_el_catalogo_son_las_preguntas_de_uso_general_no_politicas(banco):
    cat = banco.catalogo()
    assert set(cat) == {"¿Cuánto confía en sus vecinos?", "¿Con qué frecuencia hace deporte?", "¿Cómo valora su salud?"}


def test_preguntas_relevantes_solo_elige_de_la_lista_y_nunca_rompe(banco):
    cat = banco.catalogo()
    assert poblacion.preguntas_relevantes(banco, "tema", lambda p: '{"indices": [1, 0, 1, 99, "x", -1]}') == [cat[1], cat[0]]
    visto = {}
    poblacion.preguntas_relevantes(banco, "Subir el café a 3,50", lambda p: visto.setdefault("p", p) and '{"indices": []}')
    assert "Subir el café a 3,50" in visto["p"] and f"0. {cat[0]}" in visto["p"]
    assert "DESCARTA las preguntas sobre noticias o sucesos concretos" in visto["p"]
    assert poblacion.preguntas_relevantes(banco, "tema", None) == []
    assert poblacion.preguntas_relevantes(banco, "", lambda p: '{"indices": [0]}') == []
    assert poblacion.preguntas_relevantes(banco, "tema", lambda p: "no es json") == []
    def roto(p): raise RuntimeError("boom")
    assert poblacion.preguntas_relevantes(banco, "tema", roto) == []


def test_las_preguntas_relevantes_van_primero_en_la_ficha(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = [{"pregunta": "Grado de preocupación por los incendios forestales", "respuesta": "Mucho", "politica": 0},
                    {"pregunta": "Valoración de la situación económica personal actual", "respuesta": "Buena", "politica": 0},
                    {"pregunta": "Nivel de ingresos netos del hogar", "respuesta": "De 1.100 a 1.800 €", "politica": 0}]
    rel = ["Nivel de ingresos netos del hogar", "Valoración de la situación económica personal actual"]
    assert [r["pregunta"] for r in F.respuestas_priorizadas(e, relevantes=rel)] == [
        "Nivel de ingresos netos del hogar", "Valoración de la situación económica personal actual",
        "Grado de preocupación por los incendios forestales"]
    ficha = F.construir_ficha(e, relevantes=rel)
    assert ficha.index("ingresos") < ficha.index("incendios")
    assert F.hechos_memoria(e, relevantes=rel)[0].startswith("A la pregunta «Nivel de ingresos")


def test_con_preguntas_relevantes_solo_entran_unas_pocas_de_las_demas(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = [{"pregunta": "Nivel de ingresos netos del hogar", "respuesta": "x", "politica": 0}] + [
        {"pregunta": f"Grado de preocupación por el suceso número {i} del verano", "respuesta": "Mucho", "politica": 0}
        for i in range(10)]
    orden = F.respuestas_priorizadas(e, relevantes=["Nivel de ingresos netos del hogar"])
    assert len(orden) == 1 + F.MAX_OTROS and orden[0]["pregunta"] == "Nivel de ingresos netos del hogar"
    assert len(F.respuestas_priorizadas(e)) == 11                                   # sin relevantes, todas (hasta el tope de la ficha)


def test_el_fichero_final_de_perfiles_conserva_la_marca_de_dato_real(con_banco, tmp_path):
    """Lo destapó la prueba completa en producción: el guardado final tiraba data_source y las respuestas."""
    g = _generador()
    enc = _un_encuestado(con_banco)
    anclada = g.generate_profile_from_entity(_entidad(1), 1, encuestado=enc, fuente=FUENTES["cis"])
    libre = g.generate_profile_from_entity(_entidad(2), 2)
    ruta = str(tmp_path / "reddit_profiles.json")
    g._save_reddit_json([anclada, libre], ruta)
    a, b = json.load(open(ruta, encoding="utf-8"))
    assert a["data_source"] == "CIS" and a["data_ref"] == enc.estudio and a["memory_facts"]
    assert "data_source" not in b and "memory_facts" not in b                      # sin datos reales, el fichero es el de siempre
    assert a["age"] == enc.edad and a["user_id"] == 1                              # y los campos que OASIS necesita siguen ahí


def test_llm_texto_repite_con_mas_espacio_si_el_modelo_devuelve_vacio(con_banco):
    """Un modelo de razonamiento puede gastar todo el presupuesto pensando y devolver contenido vacío."""
    g = _generador()
    llamadas = []

    def create(**kw):
        llamadas.append(kw["max_tokens"])
        contenido = "" if len(llamadas) == 1 else '{"indices": [1]}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido), finish_reason="stop")])

    g.client.chat.completions.create = create
    assert g._llm_texto("pregunta") == '{"indices": [1]}'
    assert llamadas == [4096, 16384]                                                # la segunda con el cuádruple de espacio


def test_una_institucion_no_se_ancla_a_un_encuestado(con_banco, tmp_path):
    """Lo destapó la prueba en producción: «Universidad de Vigo» salía como una jubilada de 80 años."""
    from app.services.zep_entity_reader import EntityNode
    g = _generador()
    uni = EntityNode(uuid="u9", name="Universidad de Vigo", labels=["Entity", "University"], summary="Universidad pública",
                     attributes={"__simuloo_individual": True, "__simuloo_group": "U"})
    persona = _entidad(1, grupo="P")
    perfiles = g.generate_profiles_from_entities([uni, persona], parallel_count=1, poblacion_datos=True,
                                                 poblacion_pais="ES", pregunta="x", publico_descripcion="y",
                                                 poblacion_resumen_path=str(tmp_path / "poblacion.json"))
    assert perfiles[0].data_source is None and perfiles[1].data_source == "CIS"
    r = json.load(open(tmp_path / "poblacion.json", encoding="utf-8"))
    assert [x["nombre"] for x in r["grupos"]] == ["Persona 1"]                       # la institución ni cuenta como grupo


def test_el_lote_elige_las_preguntas_relevantes_una_vez_y_las_guarda(con_banco, tmp_path):
    g = _generador()
    ruta = str(tmp_path / "poblacion.json")
    g.generate_profiles_from_entities([_entidad(0, grupo="A"), _entidad(1, grupo="A")], parallel_count=1,
                                      poblacion_datos=True, poblacion_pais="ES", pregunta="¿Subir el precio?",
                                      publico_descripcion="Clientes", poblacion_resumen_path=ruta)
    elegir = [p for p in g.client.prompts if "elige hasta" in p]
    assert len(elegir) == 1                                                        # una sola llamada para toda la simulación
    r = json.load(open(ruta, encoding="utf-8"))
    assert len(r["preguntas_relevantes"]) == 2


def test_la_ficha_no_lleva_la_provincia(banco):
    """Minimización: la provincia está en el banco ('Subregión X') pero no sale hacia el modelo."""
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    assert e.subregion == "Subregión X"
    ficha = F.construir_ficha(e)
    assert "Subregión X" not in ficha and e.region in ficha


def test_ficha_recorta_respuestas_larguisimas(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    e.respuestas = [{"pregunta": "P", "respuesta": "x" * 900, "politica": 0}]
    assert len(F.construir_ficha(e)) < 600


def test_hechos_de_memoria_y_genero(banco):
    e = banco.encuestado(banco.segmento({}, minimo=1).ids[0])
    hechos = F.hechos_memoria(e, maximo=3)
    assert len(hechos) == 3 and all("respondió" in h for h in hechos)
    assert F.genero_oasis(e) in ("male", "female")


# ---------------------------------------------------------------- vocabulario cerrado y anti-estereotipo
def test_validar_descarta_lo_que_no_esta_en_el_vocabulario():
    cis = FUENTES["cis"]
    assert validar({"sexo": "Mujer", "region": ["Galicia", "Narnia"], "ingresos": ["altos"], "edad_min": "30"}, cis) == \
        {"sexo": ["Mujer"], "region": ["Galicia"], "edad_min": 30}
    assert validar({"edad_min": 70, "edad_max": 30}, cis) == {}
    assert validar({"edad_min": 5}, cis) == {}
    assert validar("basura", cis) == {}


def test_validar_usa_las_regiones_de_la_fuente(dos_paises):
    crudo = {"region": ["Texas", "Madrid"]}
    assert validar(crudo, FUENTES["gss"]) == {"region": ["Texas"]}
    assert validar(crudo, FUENTES["cis"]) == {"region": ["Madrid"]}
    assert validar(crudo, None) == {}                                                    # sin fuente no hay regiones válidas


def test_traducir_publico_tolera_prosa_y_fallos():
    cis = FUENTES["cis"]
    ok = traducir_publico("madres gallegas de 35 a 50", lambda p: 'Claro: {"sexo": ["Mujer"], "region": ["Galicia"], "edad_min": 35, "edad_max": 50}', cis)
    assert ok == {"sexo": ["Mujer"], "region": ["Galicia"], "edad_min": 35, "edad_max": 50}
    assert traducir_publico("x", lambda p: "no es json", cis) == {}
    def roto(p): raise RuntimeError("boom")
    assert traducir_publico("x", roto, cis) == {}
    assert traducir_publico("", lambda p: "{}", cis) == {}
    assert traducir_publico("x", None, cis) == {}


def test_traducir_grupos_una_llamada_y_claves_que_faltan_quedan_sin_filtros():
    vistos = []

    def llm(prompt):
        vistos.append(prompt)
        return '{"a": {"sitlab": ["jubilado"], "rubbish": 1}}'

    r = traducir_grupos([{"clave": "a", "nombre": "Jubilados", "descripcion": ""},
                         {"clave": "b", "nombre": "Otros", "descripcion": ""}], "contexto", llm, FUENTES["cis"])
    assert r == {"a": {"sitlab": ["jubilado"]}, "b": {}} and len(vistos) == 1


def test_el_filtro_solo_acota_lo_que_el_texto_dice_y_nombra_el_pais(dos_paises):
    """La regla antiestereotipo vive en el prompt: filtrar solo por lo explícito, nunca deducir de aficiones."""
    vistos = []
    traducir_grupos([{"clave": "a", "nombre": "Amantes del café", "descripcion": "les gusta el café"}], "",
                    lambda p: vistos.append(p) or "{}", FUENTES["gss"])
    p = vistos[0]
    assert "NO deduzcas edad, sexo, estudios ni ingresos de aficiones" in p
    assert "Un LUGAR nombrado" in p and "la región de la lista que lo contiene" in p
    assert "Estados Unidos (GSS)" in p
    assert "Texas" in p and "Galicia" not in p                                           # las regiones válidas son las de ese país


# ---------------------------------------------------------------- modo apagado y generador
def test_modo_activo_exige_banco_y_respeta_el_interruptor(con_banco, monkeypatch, tmp_path):
    assert not poblacion.modo_activo()                 # interruptor apagado y sin petición
    assert poblacion.modo_activo(True)
    assert not poblacion.modo_activo(False)
    monkeypatch.setattr(Config, "POBLACION_DATOS_REALES", True)
    assert poblacion.modo_activo()
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", str(tmp_path / "no.sqlite"))
    assert not poblacion.modo_activo(True)             # sin banco, nunca


class _LLMFalso:
    """Cliente OpenAI mínimo: devuelve un perfil JSON fijo (o el que le digan) y guarda los prompts que recibe."""
    def __init__(self, detector=None):
        self.prompts = []
        self.detector = detector
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        prompt = kw["messages"][-1]["content"]
        self.prompts.append(prompt)
        if "Decide de qué país es el PÚBLICO" in prompt:
            contenido = self.detector or '{"pais": null, "motivo": "no claro"}'
        elif "traduce la descripción" in prompt:
            contenido = "{}"
        elif "elige hasta" in prompt:
            contenido = '{"indices": [0, 1]}'

        else:
            contenido = ('{"bio": "Bio", "persona": "Persona redactada", "profession": "jubilado", "interested_topics": '
                         '["salud"], "age": 3, "gender": "male", "mbti": "INTJ", "country": "Japón"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=contenido), finish_reason="stop")])


def _generador(detector=None):
    from app.services.oasis_profile_generator import OasisProfileGenerator
    g = OasisProfileGenerator.__new__(OasisProfileGenerator)
    g.api_key, g.base_url, g.model_name = "k", "http://x", "m"
    g.client, g.graph_id, g.zep_client = _LLMFalso(detector), None, None
    return g


def _entidad(i, publico=True, grupo=None):
    from app.services.zep_entity_reader import EntityNode
    attrs = {"__simuloo_individual": True} if publico else {}
    if grupo:
        attrs["__simuloo_group"] = grupo
    return EntityNode(uuid=f"u{i}", name=f"Persona {i}", labels=["Entity", "Person"], summary="Un público",
                      attributes=attrs)


def _un_encuestado(con_banco):
    b = Banco(con_banco, FUENTES["cis"])
    return b.encuestado(b.segmento({}, minimo=1).ids[0])


def test_anclado_toma_edad_genero_region_del_dato_real(con_banco):
    g = _generador()
    enc = _un_encuestado(con_banco)
    p = g.generate_profile_from_entity(_entidad(1), 1, encuestado=enc, fuente=FUENTES["cis"])
    assert p.age == enc.edad and p.gender == F.genero_oasis(enc)
    assert p.country == "España" and p.mbti is None                      # no se inventa el MBTI ni el país
    assert (p.data_source, p.data_ref) == ("CIS", enc.estudio)
    assert p.memory_facts and "respondió" in p.memory_facts[0]
    prompt = g.client.prompts[-1]
    assert "DATA SHEET" in prompt and f"{enc.edad} años" in prompt and "do NOT contradict" in prompt
    assert p.to_reddit_format()["data_source"] == "CIS"


def test_el_prompt_anclado_prohibe_el_estereotipo_y_no_pide_inventar(con_banco):
    g = _generador()
    enc = _un_encuestado(con_banco)
    ent = _entidad(1)
    ent.attributes["__simuloo_variant"] = 3
    g.generate_profile_from_entity(ent, 1, encuestado=enc, fuente=FUENTES["cis"])
    prompt = g.client.prompts[-1]
    assert "AVOID STEREOTYPES" in prompt and "Do NOT infer traits" in prompt
    assert "The topic of the simulation decides what to foreground" in prompt and "a person is not their vote" in prompt
    assert "NOT from what is \"typical\" for their sex, age or job" in prompt
    assert "population of España (CIS)" in prompt
    # con un encuestado real no se le pide al modelo que invente edad, familia ni que sea «distinta» de las demás
    assert "situación familiar" not in prompt and "claramente distinta" not in prompt and "persona n.º" not in prompt


def test_el_prompt_se_adapta_al_pais_de_la_fuente(dos_paises):
    g = _generador()
    us = poblacion.abrir_banco(FUENTES["gss"])
    enc = us.encuestado(us.segmento({}, minimo=1).ids[0])
    p = g.generate_profile_from_entity(_entidad(1), 1, encuestado=enc, fuente=FUENTES["gss"])
    assert p.country == "Estados Unidos" and p.data_source == "GSS"
    prompt = g.client.prompts[-1]
    assert "population of Estados Unidos (GSS)" in prompt and "Estado:" in prompt


def test_modo_apagado_es_identico_a_hoy(con_banco):
    g = _generador()
    enc = _un_encuestado(con_banco)
    sin = g.generate_profile_from_entity(_entidad(1), 1)                 # sin encuestado
    assert sin.data_source is None and sin.memory_facts == [] and sin.age == 3 and sin.mbti == "INTJ"
    assert "data_source" not in sin.to_reddit_format()
    assert "DATA SHEET" not in g.client.prompts[-1]
    # una entidad que no es público no se ancla aunque llegue un encuestado
    emp = g.generate_profile_from_entity(_entidad(2, publico=False), 2, encuestado=enc, fuente=FUENTES["cis"])
    assert emp.data_source is None


def test_generar_lote_ancla_por_grupos_solo_al_publico_y_no_repite(con_banco, tmp_path):
    g = _generador()
    ents = [_entidad(0, grupo="A"), _entidad(1, publico=False), _entidad(2, grupo="A"), _entidad(3, grupo="B")]
    ruta = str(tmp_path / "poblacion.json")
    perfiles = g.generate_profiles_from_entities(ents, parallel_count=1, poblacion_datos=True, poblacion_pais="ES",
                                                 publico_descripcion="", poblacion_resumen_path=ruta)
    assert [p.data_source for p in perfiles] == ["CIS", None, "CIS", "CIS"]
    resumen = json.load(open(ruta, encoding="utf-8"))
    assert resumen["reparto"]["n"] == 3 and resumen["cita"] == "Fuente de datos: CIS"
    assert resumen["pais"] == "ES" and len(resumen["grupos"]) == 2 and resumen["pais_decidido_por"] == "pedido"
    assert sorted(x["personas"] for x in resumen["grupos"]) == [1, 2]
    # apagado: nadie anclado y no se escribe el resumen
    perfiles = g.generate_profiles_from_entities(ents, parallel_count=1, poblacion_datos=False)
    assert all(p.data_source is None for p in perfiles)


def test_lote_automatico_elige_el_pais_del_brief(dos_paises, tmp_path):
    g = _generador(detector='{"pais": "US", "motivo": "Amas de casa de Ohio"}')
    ruta = str(tmp_path / "poblacion.json")
    perfiles = g.generate_profiles_from_entities([_entidad(0, grupo="A"), _entidad(1, grupo="A")], parallel_count=1,
                                                 poblacion_datos=True, poblacion_pais="auto",
                                                 publico_descripcion="Amas de casa de Ohio", pregunta="¿Lo comprarían?",
                                                 poblacion_resumen_path=ruta)
    assert [p.data_source for p in perfiles] == ["GSS", "GSS"] and all(p.country == "Estados Unidos" for p in perfiles)
    r = json.load(open(ruta, encoding="utf-8"))
    assert r["pais"] == "US" and r["pais_decidido_por"] == "automatico" and "Ohio" in r["pais_motivo"]


def test_lote_sin_pais_claro_no_ancla_y_lo_dice(con_banco, tmp_path):
    """Si el país no es claro (o no hay banco de ese país) se genera como siempre y se deja escrito por qué."""
    g = _generador()                                       # el detector devuelve null
    ruta = str(tmp_path / "poblacion.json")
    perfiles = g.generate_profiles_from_entities([_entidad(0, grupo="A")], parallel_count=1, poblacion_datos=True,
                                                 poblacion_pais="auto", publico_descripcion="Gente", pregunta="p",
                                                 poblacion_resumen_path=ruta)
    assert perfiles[0].data_source is None
    r = json.load(open(ruta, encoding="utf-8"))
    assert r["sin_datos"] is True and r["motivo"] and r["pais_decidido_por"] == "ninguno"
    # país pedido sin banco (Francia): igual
    perfiles = g.generate_profiles_from_entities([_entidad(0, grupo="A")], parallel_count=1, poblacion_datos=True,
                                                 poblacion_pais="FR", poblacion_resumen_path=ruta)
    assert perfiles[0].data_source is None and json.load(open(ruta, encoding="utf-8"))["sin_datos"] is True


def test_cita_de_simulacion(con_banco, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path))
    assert poblacion.cita_de_simulacion("sim_x") == ""
    (tmp_path / "sim_x").mkdir()
    (tmp_path / "sim_x" / "poblacion.json").write_text('{"cita": "Fuente de datos: GSS", "estudios": ["2024"]}', encoding="utf-8")
    assert poblacion.cita_de_simulacion("sim_x") == "Fuente de datos: GSS (estudio 2024)"
    # nombre antiguo del fichero (simulaciones anteriores al refactor): se sigue leyendo
    (tmp_path / "sim_y").mkdir()
    (tmp_path / "sim_y" / "poblacion_cis.json").write_text('{"estudios": ["3535"]}', encoding="utf-8")
    assert poblacion.cita_de_simulacion("sim_y") == "Fuente de datos: CIS (estudio 3535)"


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
    monkeypatch.setattr(Config, "POBLACION_BANCOS_DIR", str(tmp_path))
    d = cliente.get("/api/simulation/poblacion/estado", headers=H).get_json()["data"]
    assert d["disponible"] is False and d["estudios"] == [] and d["fuentes"] == []


def test_api_estado_con_banco_y_por_defecto(cliente, con_banco, monkeypatch):
    monkeypatch.setattr(Config, "POBLACION_DATOS_REALES", True)
    d = cliente.get("/api/simulation/poblacion/estado", headers=H).get_json()["data"]
    assert d["disponible"] and d["por_defecto"] is True and len(d["estudios"]) == 2
    assert d["fuente"] == "Fuente de datos: CIS"                       # compatibilidad con la interfaz anterior
    assert [f["id"] for f in d["fuentes"]] == ["cis"] and d["fuentes"][0]["uso_interno"] is True


def test_api_estado_lista_un_pais_por_fuente(cliente, dos_paises):
    d = cliente.get("/api/simulation/poblacion/estado", headers=H).get_json()["data"]
    assert [(f["pais"], f["nombre"]) for f in d["fuentes"]] == [("ES", "CIS"), ("US", "GSS")]
    assert all(f["estudios"] for f in d["fuentes"])


def test_api_poblacion_de_una_simulacion(cliente, storage, monkeypatch):   # noqa: F811
    sid = "sim_abc123"
    assert cliente.get(f"/api/simulation/{sid}/poblacion", headers=H).get_json() == {"success": True, "data": None}
    import os
    carpeta = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, sid)
    os.makedirs(carpeta, exist_ok=True)
    json.dump({"estudios": ["3535"], "reparto": {"n": 5}}, open(os.path.join(carpeta, "poblacion.json"), "w"))
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
