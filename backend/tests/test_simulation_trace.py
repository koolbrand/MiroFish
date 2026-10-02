"""
Registro de acciones de la simulación (scripts/run_parallel_simulation.py): las publicaciones iniciales no se anotan dos veces.

El fallo que cubre: las publicaciones iniciales se anotan a mano en la ronda 0 y además se ejecutan en la simulación, que
las deja en la tabla `trace`. El cursor con el que se leía «lo nuevo» (`last_rowid`) seguía en 0, así que en la PRIMERA
ronda con actividad se volvían a leer y se anotaban otra vez como si fueran de esa ronda. En las simulaciones reales de
producción pasaba con las 18 semillas de dos simulaciones, todas a la vez y una vez por plataforma (el 14 % de lo que
enseñaba la pantalla de Víctor eran esas copias).
"""
import json
import os
import sqlite3
import sys

import pytest

pytest.importorskip('oasis')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import run_parallel_simulation as sim  # noqa: E402

NAMES = {0: 'Ana', 1: 'Beto'}


def make_db(path, rows=()):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE trace (user_id INTEGER, created_at TEXT, action TEXT, info TEXT)')
    conn.commit()
    conn.close()
    add_rows(path, rows)


def add_rows(path, rows):
    conn = sqlite3.connect(path)
    for user_id, action, info in rows:
        conn.execute('INSERT INTO trace (user_id, created_at, action, info) VALUES (?, ?, ?, ?)',
                     (user_id, '2026-10-02 09:12:00', action, json.dumps(info)))
    conn.commit()
    conn.close()


def contents(actions):
    return [a['action_args'].get('content') for a in actions]


def test_last_trace_rowid_is_zero_without_database_or_rows(tmp_path):
    assert sim.get_last_trace_rowid(str(tmp_path / 'no_existe.db')) == 0
    db = str(tmp_path / 'vacia.db')
    make_db(db)
    assert sim.get_last_trace_rowid(db) == 0


def test_last_trace_rowid_is_the_highest_row(tmp_path):
    db = str(tmp_path / 't.db')
    make_db(db, [(0, 'sign_up', {}), (0, 'create_post', {'content': 'a'}), (1, 'create_post', {'content': 'b'})])
    assert sim.get_last_trace_rowid(db) == 3


def test_seed_posts_are_not_read_again_once_the_cursor_moves_past_them(tmp_path):
    """El caso real: altas y semillas en la base de datos; la primera ronda con actividad trae solo lo nuevo."""
    db = str(tmp_path / 't.db')
    make_db(db, [(0, 'sign_up', {}), (1, 'sign_up', {}),
                 (0, 'create_post', {'content': 'Semilla A'}), (1, 'create_post', {'content': 'Semilla B'})])
    cursor = sim.get_last_trace_rowid(db)            # lo que hay tras sembrar: ya está anotado en la ronda 0
    add_rows(db, [(1, 'create_post', {'content': 'Lo que escribe Beto en su ronda'})])
    actions, new_cursor = sim.fetch_new_actions_from_db(db, cursor, NAMES)
    assert contents(actions) == ['Lo que escribe Beto en su ronda']
    assert new_cursor > cursor


def test_without_moving_the_cursor_the_seeds_come_back_as_new_actions(tmp_path):
    """Por qué hace falta mover el cursor: desde 0, la lectura devuelve las semillas otra vez (el fallo original)."""
    db = str(tmp_path / 't.db')
    make_db(db, [(0, 'sign_up', {}), (0, 'create_post', {'content': 'Semilla A'}), (1, 'create_post', {'content': 'Semilla B'})])
    add_rows(db, [(1, 'create_post', {'content': 'Nuevo'})])
    actions, _ = sim.fetch_new_actions_from_db(db, 0, NAMES)
    assert contents(actions) == ['Semilla A', 'Semilla B', 'Nuevo']


def test_a_second_read_does_not_repeat_what_the_first_returned(tmp_path):
    db = str(tmp_path / 't.db')
    make_db(db, [(0, 'create_post', {'content': 'x'})])
    cursor = sim.get_last_trace_rowid(db)
    add_rows(db, [(0, 'create_post', {'content': 'y'})])
    first, cursor = sim.fetch_new_actions_from_db(db, cursor, NAMES)
    second, _ = sim.fetch_new_actions_from_db(db, cursor, NAMES)
    assert contents(first) == ['y'] and second == []


def test_several_seeds_from_the_same_agent_are_all_kept():
    """En Twitter, un agente con dos semillas se quedaba solo con la última (el diccionario se pisaba)."""
    actions = {}
    agent, other = object(), object()
    sim.add_action_for_agent(actions, agent, 'primera')
    sim.add_action_for_agent(actions, other, 'otra')
    sim.add_action_for_agent(actions, agent, 'segunda')
    sim.add_action_for_agent(actions, agent, 'tercera')
    assert actions[agent] == ['primera', 'segunda', 'tercera']
    assert actions[other] == 'otra'            # un agente con una sola acción no cambia de forma
