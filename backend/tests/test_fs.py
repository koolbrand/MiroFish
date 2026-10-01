"""
Escritura atómica y lectura tolerante de los archivos de estado.
"""

import json
import os
import threading

import pytest

from app.utils import fs


def test_atomic_write_replaces_the_file_and_leaves_no_temporaries(tmp_path):
    path = tmp_path / "estado.json"
    fs.atomic_write_json(str(path), {"a": 1, "texto": "ñandú"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "texto": "ñandú"}
    fs.atomic_write_json(str(path), {"a": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["estado.json"]


def test_an_unserializable_value_keeps_the_previous_file_intact(tmp_path):
    path = tmp_path / "estado.json"
    fs.atomic_write_json(str(path), {"ok": True})
    with pytest.raises(TypeError):
        fs.atomic_write_json(str(path), {"roto": object()})
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}      # no se truncó
    assert [p.name for p in tmp_path.iterdir()] == ["estado.json"]


def test_a_reader_never_sees_a_half_written_file(tmp_path):
    path = tmp_path / "estado.json"
    fs.atomic_write_json(str(path), {"n": 0, "relleno": "x" * 20000})
    stop = threading.Event()
    broken = []

    def writer():
        i = 0
        while not stop.is_set():
            i += 1
            fs.atomic_write_json(str(path), {"n": i, "relleno": "x" * 20000}, fsync=False)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        for _ in range(600):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                broken.append(1)
    finally:
        stop.set()
        thread.join()
    assert broken == []


def test_create_dir_false_does_not_resurrect_a_deleted_folder(tmp_path):
    gone = tmp_path / "borrada" / "estado.json"
    with pytest.raises(FileNotFoundError):
        fs.atomic_write_json(str(gone), {"a": 1}, create_dir=False)
    assert not (tmp_path / "borrada").exists()
    fs.atomic_write_json(str(gone), {"a": 1})                                  # por defecto sí crea
    assert gone.exists()


def test_read_json_or_none_tolerates_missing_empty_and_truncated(tmp_path):
    assert fs.read_json_or_none(str(tmp_path / "no_existe.json")) is None
    (tmp_path / "vacio.json").write_text("", encoding="utf-8")
    (tmp_path / "roto.json").write_text('{"a": ', encoding="utf-8")
    (tmp_path / "bueno.json").write_text('{"a": 1}', encoding="utf-8")
    assert fs.read_json_or_none(str(tmp_path / "vacio.json")) is None
    assert fs.read_json_or_none(str(tmp_path / "roto.json")) is None
    assert fs.read_json_or_none(str(tmp_path / "bueno.json")) == {"a": 1}


def test_exists_but_unreadable_tells_missing_from_broken(tmp_path):
    (tmp_path / "roto.json").write_text("{", encoding="utf-8")
    (tmp_path / "bueno.json").write_text("{}", encoding="utf-8")
    assert fs.exists_but_unreadable(str(tmp_path / "roto.json")) is True
    assert fs.exists_but_unreadable(str(tmp_path / "bueno.json")) is False
    assert fs.exists_but_unreadable(str(tmp_path / "nada.json")) is False
