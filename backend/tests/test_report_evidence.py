"""Synthetic replay of the electoral case: no providers or private microdata."""
import json

import pytest

from app.config import Config
from app.models.project import ProjectManager
from app.services import report_agent as module
from app.services.report_agent import ReportAgent, ReportManager, ReportOutline, ReportSection, ReportStatus
from app.services.report_evidence import (
    SOURCE_LIMIT, load_evidence, prepare_section, prompt_context, render_record, validate_electoral_claims,
)
from app.services.simulation_runner import SimulationRunner
from app.utils.locale import get_locale, set_locale, t

SIM = "sim_aaaaaaaaaaaa"
GRAPH = "mirofish_aaaaaaaaaaaa"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def case(tmp_path, monkeypatch):
    previous = get_locale()
    set_locale("es")
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    monkeypatch.setattr(ProjectManager, "PROJECTS_DIR", str(tmp_path / "projects"))
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path / "simulations"))
    monkeypatch.setattr(ReportManager, "REPORTS_DIR", str(tmp_path / "reports"))
    project = ProjectManager.create_project("Synthetic electoral case", owner_id="alice")
    project.graph_id = GRAPH
    project.simulation_requirement = "Elecciones hipotéticas"
    ProjectManager.save_project(project)
    ProjectManager.save_extracted_text(project.project_id,
        "La convocatoria es hipotética. Ponencia pendiente, no sentencia. IPC 4,9 %. "
        "Fuente aportada: https://ine.example.test/ipc\n")
    folder = tmp_path / "simulations" / SIM
    folder.mkdir(parents=True)
    write(folder / "state.json", {"simulation_id": SIM, "project_id": project.project_id, "graph_id": GRAPH})
    write(folder / "simulation_config.json", {"time_config": {"total_simulation_hours": 72, "minutes_per_round": 60}})
    write(folder / "run_state.json", {"runner_status": "completed", "current_round": 15, "simulated_hours": 15})
    write(folder / "reddit_profiles.json", [
        {"user_id": 1, "name": "Electorado · 1", "data_source": "Synthetic Survey", "data_ref": "A"},
        {"user_id": 2, "name": "Electorado · 2", "data_source": "Synthetic Survey", "data_ref": "B"},
        {"user_id": 3, "name": "Institución"},
    ])
    # Same profiles on two platforms must NOT double the population count.
    write(folder / "twitter_profiles.json", json.loads((folder / "reddit_profiles.json").read_text()))
    for platform in ("twitter", "reddit"):
        (folder / platform).mkdir()
        rows = [{"event_type": "simulation_start"},
                {"agent_id": "1", "round": 0, "action_type": "CREATE_POST", "success": True},
                {"agent_id": 3, "round": 8, "action_type": "LIKE_POST", "success": True},
                {"agent_id": 3, "round": 8, "action_type": "CREATE_COMMENT", "success": False}]
        (folder / platform / "actions.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n{partial", encoding="utf-8")
    yield folder, project
    set_locale(previous)


def test_counts_are_events_not_ballots_and_population_not_platforms(case):
    bundle = load_evidence(SIM, GRAPH)
    metrics = bundle["metrics"]
    assert metrics["agents"] == {"total": 3, "anchored": 2, "active": 2, "active_anchored": 1,
                                  "profile_metadata_available": True,
                                  "anchored_groups": {"Electorado": 2}, "studies": {"A": 1, "B": 1},
                                  "population_citation": ""}
    assert metrics["actions"]["total"] == 6
    assert metrics["actions"]["by_type"] == {"CREATE_POST": 2, "LIKE_POST": 2, "CREATE_COMMENT": 2}
    assert metrics["actions"]["by_platform"] == {"twitter": 3, "reddit": 3}
    assert metrics["actions"]["failed"] == 2 and metrics["actions"]["malformed_lines"] == 2
    assert metrics["measurement"] == {"method": "social_conversation", "electoral_status": "not_measured", "votes": None, "seats": None, "winner": None}
    assert metrics["execution"]["duration_limited"]
    assert "hipotética" in prompt_context(bundle) and "no sentencia" in prompt_context(bundle)
    assert "hipotética" not in json.dumps(metrics)  # no brief leak in report listings


def test_source_comes_from_linked_project_not_configuration(case):
    folder, project = case
    other = ProjectManager.create_project("Other user", owner_id="bob")
    other.graph_id = "other_graph"
    ProjectManager.save_project(other)
    ProjectManager.save_extracted_text(other.project_id, "OTHER USERS PRIVATE BRIEF")
    config = json.loads((folder / "simulation_config.json").read_text())
    config["project_id"] = other.project_id
    write(folder / "simulation_config.json", config)
    assert "OTHER USERS" not in prompt_context(load_evidence(SIM, GRAPH))
    state = json.loads((folder / "state.json").read_text())
    state["project_id"] = other.project_id
    write(folder / "state.json", state)
    with pytest.raises(ValueError, match="no corresponde"):
        load_evidence(SIM, GRAPH)


def test_missing_or_corrupt_chain_fails_without_creating_folders(case):
    folder, _ = case
    (folder / "state.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="vincular"):
        load_evidence(SIM, GRAPH)
    before = set(folder.parent.iterdir())
    with pytest.raises(ValueError):
        load_evidence("sim_bbbbbbbbbbbb", GRAPH)
    assert set(folder.parent.iterdir()) == before


def test_bounded_original_keeps_end_with_pending_events_and_marks_omission(case):
    _, project = case
    source = "HEAD " + "x" * 50000 + " TAIL: sentencia pendiente"
    ProjectManager.save_extracted_text(project.project_id, source)
    bundle = load_evidence(SIM, GRAPH)
    assert bundle["metrics"]["source"]["characters"] == len(source)
    assert bundle["metrics"]["source"]["truncated"]
    assert len(bundle["source_excerpt"]) < SOURCE_LIMIT + 100
    assert bundle["source_excerpt"].startswith("HEAD") and bundle["source_excerpt"].endswith("sentencia pendiente")


def test_missing_source_is_explicit_and_fractional_rounds_match_runner(case):
    folder, project = case
    from pathlib import Path
    Path(ProjectManager._get_project_text_path(project.project_id)).unlink()
    write(folder / "simulation_config.json", {"time_config": {"total_simulation_hours": 2, "minutes_per_round": 50}})
    bundle = load_evidence(SIM, GRAPH)
    assert bundle["metrics"]["execution"]["configured_rounds"] == 2
    assert bundle["metrics"]["source"]["available"] is False
    assert "No se dispone" in render_record(bundle["metrics"])


def test_effective_hours_derive_from_real_logger_rounds_not_monitor_zero(case):
    from scripts.action_logger import PlatformActionLogger
    from app.services.simulation_runner import SimulationRunState
    folder, _ = case
    logger = PlatformActionLogger(platform="twitter", base_dir=str(folder))
    (folder / "twitter" / "actions.jsonl").write_text("", encoding="utf-8")
    logger.log_round_start(round_num=15, simulated_hour=14)
    logger.log_round_end(round_num=15, actions_count=0)
    state = SimulationRunState(SIM)
    SimulationRunner._read_action_log(logger.log_path, 0, state, "twitter")
    assert state.current_round == 15 and state.simulated_hours == 0
    write(folder / "run_state.json", state.to_dict())
    assert load_evidence(SIM, GRAPH)["metrics"]["execution"]["executed_hours"] == 15
    write(folder / "simulation_config.json", {"time_config": {"total_simulation_hours": 72, "minutes_per_round": 50}})
    assert load_evidence(SIM, GRAPH)["metrics"]["execution"]["executed_hours"] == 12.5


def test_csv_only_counts_agents_without_guessing_survey_attribution(case):
    folder, _ = case
    (folder / "reddit_profiles.json").unlink()
    (folder / "twitter_profiles.json").unlink()
    (folder / "twitter_profiles.csv").write_text("user_id,name,username,user_char,description\n1,A,a,persona,bio\n3,B,b,persona,bio\n")
    agents = load_evidence(SIM, GRAPH)["metrics"]["agents"]
    assert agents["total"] == 2 and agents["active"] == 2
    assert agents["anchored"] is None and agents["active_anchored"] is None
    assert agents["profile_metadata_available"] is False


def test_corrupt_original_fails_explicitly_without_source_or_path_in_message(case):
    _, project = case
    from pathlib import Path
    Path(ProjectManager._get_project_text_path(project.project_id)).write_bytes(b"secret \xff")
    with pytest.raises(ValueError, match="No se puede leer") as exc:
        load_evidence(SIM, GRAPH)
    assert "secret" not in str(exc.value) and "extracted_text" not in str(exc.value)


@pytest.mark.parametrize("locale,label", [("es", "Cita simulada"), ("en", "Simulated quote"), ("zh", "模拟引文")])
def test_quotes_and_unapproved_urls_cannot_export_as_external_sources(case, locale, label):
    bundle = load_evidence(SIM, GRAPH)
    body = '> "Ganaremos", dijo una institución.\n> Continuación de la cita.\n\n'
    body += "[Original](https://ine.example.test/ipc) y [Inventado](https://made-up.example.test/poll)."
    body += "\nEnlace simulado https://made-up.example.test/article"
    out = prepare_section(body, bundle, locale)
    assert out.count(label) == 1
    assert "[Original](https://ine.example.test/ipc)" in out
    assert "made-up.example.test" not in out
    assert "[Inventado](" not in out  # no malformed Markdown link remains


@pytest.mark.parametrize("claim", [
    "El partido A ganaría las elecciones.", "El vencedor electoral es A.",
    "La derecha tiene una mayoría suficiente con 137 + 32.",
    "A obtendría 190 escaños.", "A will win the election.", "A is the election winner.", "A将赢得选举。",
    "No hay dudas: A ganará las elecciones.", "Sin duda A ganaría las elecciones.",
    "Ganaría el Partido A.", "El Partido A sería la primera fuerza.",
    "El Partido A obtendría el mayor número de votos.", "A would win.", "A获得最多选票。",
])
def test_unmeasured_winner_and_seat_claims_are_rejected(claim):
    with pytest.raises(ValueError, match="no se ha medido"):
        validate_electoral_claims(claim)


@pytest.mark.parametrize("claim", [
    "No se puede determinar quién ganaría las elecciones.", "¿Quién ganaría las elecciones?",
    '> "A ganaría las elecciones", afirma el agente simulado.',
    "El material original recoge una votación pasada de 137 + 32 = 169.",
    "La mayoría absoluta exige más votos favorables que la mitad del total.",
    "En las elecciones de 2023 el Partido A obtuvo 137 escaños.",
    "Who would win?", "We cannot determine who would win.", "谁获得最多选票？",
])
def test_questions_negative_cautions_and_simulated_quotes_are_allowed(claim):
    validate_electoral_claims(claim)


def test_generic_winning_sales_does_not_block_a_non_electoral_scenario():
    validate_electoral_claims("The new product would win market share.", electoral_context="Ensayar un nuevo precio de café")


def test_coffee_report_has_general_scope_without_electoral_claims(case):
    bundle = load_evidence(SIM, GRAPH, "¿Cómo reaccionan al precio del café?")
    assert bundle["metrics"]["measurement"]["method"] == "social_conversation"
    assert bundle["metrics"]["measurement"]["electoral_status"] == "not_applicable"
    for locale in ("es", "en", "zh"):
        record = render_record(bundle["metrics"], locale)
        assert not any(term in record for term in ("electoral", "votos", "escaños", "winner", "seats", "选举", "席位"))


def agent_for_generation(monkeypatch, section_content):
    agent = ReportAgent(GRAPH, SIM, "Ensayar elecciones hipotéticas", llm_client=object(), zep_tools=object())
    agent.plan_outline = lambda **kw: ReportOutline("Ensayo electoral", "Reacciones simuladas", [ReportSection("A"), ReportSection("B")])
    agent._generate_section_with_retries = lambda **kw: section_content
    agent._enforce_section_locale = lambda content, title: (content, None)
    return agent


@pytest.mark.parametrize("bad", ["", "   ", "placeholder", "heading"])
def test_failed_or_empty_body_never_marks_report_completed(case, monkeypatch, bad):
    content = {"": "", "   ": "   ", "placeholder": t("report.sectionGenFailedContent"), "heading": "## A"}[bad]
    report = agent_for_generation(monkeypatch, content).generate_report()
    assert report.status == ReportStatus.FAILED
    assert ReportManager.get_progress(report.report_id)["status"] == "failed"
    assert report.completed_at == ""


def test_canonical_record_survives_save_load_and_markdown_pdf_path(case, monkeypatch):
    report = agent_for_generation(monkeypatch, 'Las personas simularon reacciones variadas.\n\n> "No confío", dijo el agente.').generate_report()
    assert report.status == ReportStatus.COMPLETED
    saved = ReportManager.get_report(report.report_id)
    assert saved.evidence == report.evidence
    assert "No estimado: ganador electoral, votos y escaños" in saved.markdown_content
    assert "15 / 72" in saved.markdown_content
    assert saved.markdown_content.count("Cita simulada") == 2
    from app.services.report_pdf import split_report, markdown_to_html
    _, _, body = split_report(saved.markdown_content)
    html = markdown_to_html(body)
    assert "No estimado" in html and "15 / 72" in html and "Cita simulada" in html


def test_placeholder_retries_are_bounded_and_never_return_success(monkeypatch):
    agent = ReportAgent.__new__(ReportAgent)
    calls = []
    agent._generate_section_react = lambda **kw: (calls.append(1), t("report.sectionGenLeakContent"))[1]
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    with pytest.raises(ValueError, match="incompleto"):
        agent._generate_section_with_retries(section=ReportSection("A"))
    assert len(calls) == agent.SECTION_ATTEMPTS


@pytest.mark.parametrize("outline", [
    {"title": "T", "sections": []},
    {"title": "Ganaría el Partido A", "summary": "S", "sections": [{"title": "A"}, {"title": "B"}]},
    {"title": "T", "sections": [{"title": None}, {"title": "B"}]},
])
def test_invalid_outline_has_visible_fallback_warning_and_original_context(case, outline):
    from types import SimpleNamespace
    calls = []
    def chat_json(messages, **kw):
        calls.append(messages)
        return outline
    agent = ReportAgent(GRAPH, SIM, "Elecciones hipotéticas", llm_client=SimpleNamespace(chat_json=chat_json),
                        zep_tools=SimpleNamespace(get_simulation_context=lambda **kw: {}))
    agent._evidence_bundle = load_evidence(SIM, GRAPH)
    generated = agent.plan_outline()
    assert len(generated.sections) == 3 and agent._planning_warning
    assert "Ponencia pendiente, no sentencia" in calls[0][1]["content"]
    assert "partidos, medios e instituciones no son" in calls[0][0]["content"]


def test_section_titles_cannot_export_an_invented_link(case):
    from types import SimpleNamespace
    agent = ReportAgent(GRAPH, SIM, "Elecciones hipotéticas",
        llm_client=SimpleNamespace(chat_json=lambda **kw: {
            "title": "T", "summary": "S", "sections": [
                {"title": "Resultado [fuente](https://invented.example.test/poll)"}, {"title": "B"}]}),
        zep_tools=SimpleNamespace(get_simulation_context=lambda **kw: {}))
    agent._evidence_bundle = load_evidence(SIM, GRAPH)
    outline = agent.plan_outline()
    assert "invented.example.test" not in outline.to_markdown()


def test_pdf_cover_uses_persisted_execution_not_current_live_state(case, monkeypatch):
    from types import SimpleNamespace
    from app.api import report as api
    from app.services.report_pdf import TEXTS
    metrics = load_evidence(SIM, GRAPH)["metrics"]
    monkeypatch.setattr(api, "SimulationManager", lambda: (_ for _ in ()).throw(AssertionError("must use snapshot")))
    assert api._pdf_meta(SimpleNamespace(evidence=metrics)) == {"people": 3, "rounds": 15, "actions": 6}
    assert TEXTS["es"]["people"] == "Agentes simulados"
    assert TEXTS["en"]["people"] == "Simulated agents"
    assert TEXTS["zh"]["people"] == "模拟代理"


def test_legacy_report_read_has_no_evidence_and_is_not_rewritten(case):
    from app.services.report_agent import Report
    legacy = Report("report_bbbbbbbbbbbb", SIM, GRAPH, "R", ReportStatus.COMPLETED, markdown_content="OLD CONTENT")
    ReportManager.save_report(legacy)
    path = ReportManager._get_report_path(legacy.report_id)
    from pathlib import Path
    meta = json.loads(Path(path).read_text())
    meta.pop("evidence")
    write(Path(path), meta)
    before = Path(path).read_bytes()
    loaded = ReportManager.get_report(legacy.report_id)
    assert loaded.evidence is None and loaded.markdown_content == "OLD CONTENT"
    assert Path(path).read_bytes() == before
