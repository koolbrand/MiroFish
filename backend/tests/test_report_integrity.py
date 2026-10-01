"""
Integridad de los informes en disco y aislamiento del registro de consola entre informes.
"""

import json
import logging
import threading

import pytest

from app.config import Config
from app.services.report_agent import (
    Report, ReportConsoleLogger, ReportManager, ReportOutline, ReportSection, ReportStatus,
)


@pytest.fixture(autouse=True)
def reports_dir(tmp_path, monkeypatch):
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    ReportManager._deleted_ids.clear()
    return tmp_path / "reports"


def make(report_id, status, created_at, simulation_id="sim_000000000001", **extra):
    report = Report(report_id=report_id, simulation_id=simulation_id, graph_id="g", simulation_requirement="¿Qué pasará?",
                    status=status, created_at=created_at, **extra)
    ReportManager.save_report(report)
    return report


def test_a_broken_meta_is_skipped_and_never_breaks_the_listing(reports_dir):
    make("report_aaaaaaaaaaa1", ReportStatus.COMPLETED, "2026-10-01T10:00:00")
    (reports_dir / "report_aaaaaaaaaaa2").mkdir()
    (reports_dir / "report_aaaaaaaaaaa2" / "meta.json").write_text('{"report_id": "rep', encoding="utf-8")
    (reports_dir / "report_aaaaaaaaaaa3").mkdir()
    (reports_dir / "report_aaaaaaaaaaa3" / "meta.json").write_text(json.dumps({"report_id": "report_aaaaaaaaaaa3"}), encoding="utf-8")
    assert [r.report_id for r in ReportManager.list_reports()] == ["report_aaaaaaaaaaa1"]
    assert ReportManager.get_report("report_aaaaaaaaaaa2") is None
    assert ReportManager.get_report("report_aaaaaaaaaaa3") is None                      # le faltan campos
    assert ReportManager.get_report_by_simulation("sim_000000000001").report_id == "report_aaaaaaaaaaa1"
    assert ReportManager.get_progress("report_aaaaaaaaaaa2") is None


def test_the_report_of_a_simulation_is_the_right_one_not_the_first_listed():
    make("report_bbbbbbbbbbb1", ReportStatus.FAILED, "2026-10-01T09:00:00")
    make("report_bbbbbbbbbbb2", ReportStatus.COMPLETED, "2026-10-01T10:00:00")
    make("report_bbbbbbbbbbb3", ReportStatus.FAILED, "2026-10-01T11:00:00")             # el más nuevo, pero fallido
    assert ReportManager.get_report_by_simulation("sim_000000000001").report_id == "report_bbbbbbbbbbb2"
    make("report_bbbbbbbbbbb4", ReportStatus.GENERATING, "2026-10-01T12:00:00")         # se está regenerando
    assert ReportManager.get_report_by_simulation("sim_000000000001").report_id == "report_bbbbbbbbbbb4"
    assert ReportManager.get_report_by_simulation("sim_999999999999") is None


def test_only_failed_reports_means_the_latest_failed_one():
    make("report_ccccccccccc1", ReportStatus.FAILED, "2026-10-01T09:00:00")
    make("report_ccccccccccc2", ReportStatus.FAILED, "2026-10-01T10:00:00")
    assert ReportManager.get_report_by_simulation("sim_000000000001").report_id == "report_ccccccccccc2"


def test_warnings_survive_a_save_and_load_roundtrip():
    make("report_ddddddddddd1", ReportStatus.COMPLETED, "2026-10-01T10:00:00", warnings=["sección forzada"])
    assert ReportManager.get_report("report_ddddddddddd1").warnings == ["sección forzada"]


def test_a_deleted_report_is_not_resurrected_by_the_thread_that_was_writing_it(reports_dir):
    make("report_eeeeeeeeeee1", ReportStatus.GENERATING, "2026-10-01T10:00:00")
    assert ReportManager.delete_report("report_eeeeeeeeeee1")
    outline = ReportOutline(title="T", summary="S", sections=[ReportSection(title="A", content="x")])
    with pytest.raises(FileNotFoundError):
        ReportManager.save_outline("report_eeeeeeeeeee1", outline)
    with pytest.raises(FileNotFoundError):
        ReportManager.update_progress("report_eeeeeeeeeee1", "generating", 50, "Escribiendo")
    assert not (reports_dir / "report_eeeeeeeeeee1").exists()


def test_writes_leave_no_temporary_files(reports_dir):
    make("report_fffffffffff1", ReportStatus.COMPLETED, "2026-10-01T10:00:00", markdown_content="# Informe")
    ReportManager.update_progress("report_fffffffffff1", "completed", 100, "Listo")
    names = [p.name for p in (reports_dir / "report_fffffffffff1").iterdir()]
    assert not [n for n in names if n.endswith(".tmp")]
    assert "meta.json" in names and "full_report.md" in names


def test_console_logs_of_two_reports_do_not_leak_into_each_other(tmp_path):
    """Los loggers son globales: antes cada console_log.txt recogía también lo que registraban los demás informes."""
    source = logging.getLogger("mirofish.report_agent")
    source.setLevel(logging.INFO)
    started, release = threading.Event(), threading.Event()
    holder = {}

    def generate(name):
        holder[name] = ReportConsoleLogger(f"report_{name}")                     # se crea EN el hilo generador
        started.set() if name == "a" else None
        release.wait(5)
        source.info(f"línea secreta del informe {name}")

    ta = threading.Thread(target=generate, args=("aaaaaaaaaaaa",))
    tb = threading.Thread(target=generate, args=("bbbbbbbbbbbb",))
    ta.start(); tb.start()
    try:
        started.wait(5)
        while len(holder) < 2:
            pass
        release.set()
        ta.join(); tb.join()
    finally:
        for logger_ in holder.values():
            logger_.close()
    log_a = (tmp_path / "reports" / "report_aaaaaaaaaaaa" / "console_log.txt").read_text(encoding="utf-8")
    log_b = (tmp_path / "reports" / "report_bbbbbbbbbbbb" / "console_log.txt").read_text(encoding="utf-8")
    assert "informe aaaaaaaaaaaa" in log_a and "informe bbbbbbbbbbbb" not in log_a
    assert "informe bbbbbbbbbbbb" in log_b and "informe aaaaaaaaaaaa" not in log_b


# ============== Reintentos por sección ==============

class _Section:
    title = "Reacciones de los grupos"


def make_agent(monkeypatch, results):
    from app.services import report_agent as module
    agent = module.ReportAgent.__new__(module.ReportAgent)
    calls = {"n": 0}

    def fake(**kwargs):
        calls["n"] += 1
        outcome = results[min(calls["n"] - 1, len(results) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    agent._generate_section_react = fake
    slept = []
    monkeypatch.setattr(module.time, "sleep", lambda s: slept.append(s))
    return agent, calls, slept


def test_a_transient_provider_error_in_a_section_is_retried_not_fatal(monkeypatch):
    agent, calls, slept = make_agent(monkeypatch, [RuntimeError("503 Service Unavailable"), "Texto de la sección"])
    assert agent._generate_section_with_retries(section=_Section()) == "Texto de la sección"
    assert calls["n"] == 2 and slept == [15]


def test_three_failures_give_up_with_the_last_error_and_backoff(monkeypatch):
    agent, calls, slept = make_agent(monkeypatch, [RuntimeError("429"), RuntimeError("503"), RuntimeError("timeout")])
    with pytest.raises(RuntimeError, match="timeout"):
        agent._generate_section_with_retries(section=_Section())
    assert calls["n"] == 3 and slept == [15, 45]


def test_a_deleted_report_is_not_retried(monkeypatch):
    agent, calls, slept = make_agent(monkeypatch, [FileNotFoundError("el informe fue borrado"), "no debería llegar"])
    with pytest.raises(FileNotFoundError):
        agent._generate_section_with_retries(section=_Section())
    assert calls["n"] == 1 and slept == []
