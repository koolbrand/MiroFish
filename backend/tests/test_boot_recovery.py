"""
Recuperación al arrancar: lo que estaba a medias cuando murió el proceso no se queda «en marcha» para siempre.
"""

import json
import os

import pytest

from app.services.report_agent import ReportManager

REASON = "El servidor se reinició mientras se escribía el informe."


def write_report(root, report_id, status, **extra):
    folder = root / report_id
    folder.mkdir()
    meta = {
        "report_id": report_id, "simulation_id": "sim_000000000001", "graph_id": "g",
        "simulation_requirement": "¿Funcionará?", "status": status, "outline": None,
        "markdown_content": "", "created_at": "2026-10-01T10:00:00", "completed_at": "", "error": None,
        "warnings": ["aviso"], **extra,
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return folder


def read_meta(root, report_id):
    return json.loads((root / report_id / "meta.json").read_text(encoding="utf-8"))


@pytest.fixture
def reports(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path))
    return tmp_path


def test_unfinished_reports_are_failed_with_the_reason(reports):
    for rid, status in [("report_aaaaaaaaaaa1", "pending"), ("report_aaaaaaaaaaa2", "planning"),
                        ("report_aaaaaaaaaaa3", "generating")]:
        write_report(reports, rid, status)
    assert ReportManager.fail_unfinished(REASON) == 3
    for rid in ("report_aaaaaaaaaaa1", "report_aaaaaaaaaaa2", "report_aaaaaaaaaaa3"):
        meta = read_meta(reports, rid)
        assert meta["status"] == "failed" and meta["error"] == REASON


def test_finished_reports_are_not_touched(reports):
    write_report(reports, "report_bbbbbbbbbbb1", "completed", markdown_content="# Informe", completed_at="2026-10-01T11:00:00")
    write_report(reports, "report_bbbbbbbbbbb2", "failed", error="otro motivo")
    before = {rid: read_meta(reports, rid) for rid in ("report_bbbbbbbbbbb1", "report_bbbbbbbbbbb2")}
    assert ReportManager.fail_unfinished(REASON) == 0
    for rid, meta in before.items():
        assert read_meta(reports, rid) == meta


def test_only_status_and_error_change_and_it_is_idempotent(reports):
    write_report(reports, "report_ccccccccccc1", "generating", markdown_content="# Parcial", outline={"title": "T", "summary": "S", "sections": []})
    before = read_meta(reports, "report_ccccccccccc1")
    assert ReportManager.fail_unfinished(REASON) == 1
    after = read_meta(reports, "report_ccccccccccc1")
    assert {k: v for k, v in after.items() if k not in ("status", "error")} == \
           {k: v for k, v in before.items() if k not in ("status", "error")}
    assert ReportManager.fail_unfinished(REASON) == 0     # ya está failed
    assert not [f for f in os.listdir(reports / "report_ccccccccccc1") if f.endswith(".tmp")]


def test_broken_or_foreign_entries_do_not_stop_the_sweep(reports):
    (reports / "report_ddddddddddd1").mkdir()
    (reports / "report_ddddddddddd1" / "meta.json").write_text("{no es json", encoding="utf-8")
    (reports / "notas.txt").write_text("hola", encoding="utf-8")
    (reports / "no_es_un_informe").mkdir()
    write_report(reports, "report_ddddddddddd2", "generating")
    assert ReportManager.fail_unfinished(REASON) == 1
    assert read_meta(reports, "report_ddddddddddd2")["status"] == "failed"
