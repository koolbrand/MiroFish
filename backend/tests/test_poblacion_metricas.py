"""Métricas de calidad de la muestra: puras, y comprobadas contra simulaciones de verdad."""

import random

import pytest

from app.services import poblacion
from app.services.poblacion import metricas as M
from app.services.poblacion.fuentes import FUENTES
from poblacion_fixture import crear_banco


def test_jsd_extremos_y_simetria():
    assert M.jsd({"a": 1, "b": 1}, {"a": 2, "b": 2}) == pytest.approx(0)
    assert M.jsd({"a": 1}, {"b": 1}) == pytest.approx(1)
    p, q = {"a": 3, "b": 1}, {"a": 1, "b": 3}
    assert M.jsd(p, q) == pytest.approx(M.jsd(q, p)) and 0 < M.jsd(p, q) < 1


def test_distribucion_ignora_vacios_y_pesos_cero():
    assert M.distribucion(["x", "y", None, "x"], [1, 2, 5, 1]) == {"x": 0.5, "y": 0.5}
    assert M.distribucion(["x"], [0]) == {} and M.distribucion([]) == {}


def test_wasserstein_distingue_un_escalon_del_extremo():
    orden = ["bajo", "medio", "alto"]
    cerca = M.wasserstein1({"bajo": 1}, {"medio": 1}, orden)
    lejos = M.wasserstein1({"bajo": 1}, {"alto": 1}, orden)
    assert cerca == pytest.approx(0.5) and lejos == pytest.approx(1.0)
    assert M.jsd({"bajo": 1}, {"medio": 1}) == M.jsd({"bajo": 1}, {"alto": 1})          # JSD no ve la distancia


def test_entropia_normalizada():
    assert M.entropia_normalizada({"a": 1}) == 0
    assert M.entropia_normalizada({"a": 1, "b": 1, "c": 1}) == pytest.approx(1)
    assert 0 < M.entropia_normalizada({"a": 9, "b": 1}) < 0.6


def test_umbral_de_ruido_coincide_con_el_azar_real():
    """La aproximación analítica del ruido de muestreo debe parecerse a sacar muestras de verdad."""
    rng = random.Random(1)
    poblacion_ = {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}
    n, d = 100, []
    for _ in range(400):
        muestra = rng.choices(list(poblacion_), weights=list(poblacion_.values()), k=n)
        d.append(M.jsd(M.distribucion(muestra), poblacion_))
    medio = sum(d) / len(d)
    esperado = (4 - 1) / (8 * n * 0.6931471805599453)
    assert medio == pytest.approx(esperado, rel=0.2)
    assert sum(x > M.umbral_ruido(4, n) for x in d) / len(d) < 0.01                      # el umbral apenas salta por azar
    assert M.umbral_ruido(4, 10) > M.umbral_ruido(4, 100) and M.umbral_ruido(1, 100) == 0


def test_calidad_detecta_un_muestreo_deformado_y_un_grupo_aplanado():
    ref = {"sexo": ["Hombre", "Mujer"] * 500, "edad": [20 + (i % 60) for i in range(1000)]}
    pesos = [1.0] * 1000
    buena = {"sexo": ["Hombre", "Mujer"] * 25, "edad": [20 + (i * 7 % 60) for i in range(50)]}
    q = M.calidad_de_grupo(buena, ref, pesos)
    assert q["representativa"] and q["campos"]["sexo"]["dentro_del_ruido"]
    sesgada = {"sexo": ["Mujer"] * 50, "edad": [20 + (i * 7 % 60) for i in range(50)]}
    assert not M.calidad_de_grupo(sesgada, ref, pesos)["representativa"]
    plana = {"sexo": ["Hombre", "Mujer"] * 25, "edad": [45] * 49 + [46]}                     # todos con la misma edad
    q = M.calidad_de_grupo(plana, ref, pesos)
    assert q["dispersion_edad"]["aplanada"] and any("edad" in a for a in q["avisos"])


def test_moda_por_celda_es_la_linea_base_sin_modelo():
    filas = [{"sexo": "Mujer", "tramo": "25-34", "r": "si"}, {"sexo": "Mujer", "tramo": "25-34", "r": "si"},
             {"sexo": "Mujer", "tramo": "25-34", "r": "no"}, {"sexo": "Hombre", "tramo": "65+", "r": "no"}]
    assert M.moda_por_celda(filas, "r") == {("Mujer", "25-34"): "si", ("Hombre", "65+"): "no"}


def test_la_asignacion_real_es_representativa_de_su_segmento(tmp_path, monkeypatch):
    """Con el banco sintético, el muestreo ponderado no deforma ni aplana a un grupo sin filtros."""
    from app.config import Config
    ruta = crear_banco(str(tmp_path / "b.sqlite"), n=1500)
    monkeypatch.setattr(Config, "POBLACION_BANCO_PATH", ruta)
    monkeypatch.setattr(Config, "POBLACION_BANCOS_DIR", str(tmp_path))
    malas = 0
    for semilla in range(40):
        asig = poblacion.asignar_por_grupos([poblacion.Grupo("g", "Todos", "", 60)], "", None, fuente=FUENTES["cis"],
                                            rng=random.Random(semilla))
        q = asig.resumen()["calidad"]
        assert q["grupos_evaluados"] == 1
        malas += 0 if q["representativa"] else 1
    assert malas <= 1          # con la cola del 0,1 % sobre ~6 medidas, el azar casi nunca dispara el aviso
