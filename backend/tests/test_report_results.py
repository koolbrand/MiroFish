"""Extractive openings: no model-authored statements can reach public data."""
import copy
import json
import shutil
import threading
from types import SimpleNamespace

import pytest
from app.services import report_results as service
from app.services.report_agent import Report, ReportManager, ReportStatus, ReportAgent

REAL_CALL_MODEL = service._call_model
TEXT = '# Ensayo\n\n> Resumen anterior.\n\n## Reacciones\n\nEl **precio** provocó dudas; probar el producto redujo esa incertidumbre.\n\n## Límites\n\nEl ensayo no permite estimar ventas ni apoyo; se observaron70 personas sin medir preferencias.'


def payload():
    return {'headline': 's2_p1',
            'findings': [{'id': 'f1', 'evidence_id': 's1_p1'},
                         {'id': 'f2', 'evidence_id': 's2_p1'}],
            'contrasts': [{'id': 'x1', 'left': 's1_p1', 'right': 's2_p1'}],
            'limitations': ['s2_p1']}


@pytest.fixture()
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(ReportManager, 'REPORTS_DIR', str(tmp_path))
    monkeypatch.setattr(ReportManager, '_deleted_ids', set())
    monkeypatch.setattr(service, '_inflight', {})
    report = Report('report_synthetic001', 'sim_synthetic001', 'graph_synthetic001', '¿Qué aprende el ensayo?', ReportStatus.COMPLETED, markdown_content=TEXT)
    ReportManager.save_report(report)
    monkeypatch.setattr(service, '_call_model', lambda *args: payload())
    return report


def test_projection_is_literal_and_formatting_only(case):
    source = service.report_source(case)
    data = service.project_selection(payload(), source)
    assert data['findings'][0]['text'] == 'El precio provocó dudas; probar el producto redujo esa incertidumbre.'
    assert data['findings'][0]['refs'][0]['quote'] == 'El **precio** provocó dudas; probar el producto redujo esa incertidumbre.'
    assert '70' in data['headline']['text']
    assert service.validate_results(data, source) == data
    assert set(data) == {'headline', 'findings', 'contrasts', 'limitations'}
    assert 'implication' not in json.dumps(data)


@pytest.mark.parametrize('attack', ['free_prose', 'fake_id', 'oversized', 'kind', 'duplicate', 'same_contrast', 'extra_root'])
def test_model_can_only_select_complete_eligible_units(case, attack):
    selection = payload()
    if attack == 'free_prose': selection['findings'][0]['text'] = 'Todo el electorado apoya la propuesta.'
    if attack == 'fake_id': selection['headline'] = 's99_p1'
    if attack == 'oversized': case.markdown_content += '\n\n' + 'No ocurrió el hecho. ' * 50; selection['headline'] = 's2_p2'
    if attack == 'kind': selection['findings'][0]['kind'] = 'winner'
    if attack == 'duplicate': selection['findings'][1]['evidence_id'] = 's1_p1'
    if attack == 'same_contrast': selection['contrasts'][0]['right'] = selection['contrasts'][0]['left']
    if attack == 'extra_root': selection['advice'] = 'Cada actor debería aceptar.'
    with pytest.raises(service.ResultsError, match='payload_invalid'):
        service.project_selection(selection, service.report_source(case))


@pytest.mark.parametrize('attack', ['new_actor', 'new_number', 'quote', 'section_bool', 'section_title', 'kind', 'extra_field'])
def test_stored_data_must_exactly_match_server_projection(case, attack):
    source = service.report_source(case)
    data = service.project_selection(payload(), source)
    if attack == 'new_actor': data['findings'][0]['text'] += ' El grupo inventado está de acuerdo.'
    if attack == 'new_number': data['headline']['text'] = 'El70% apoya el producto.'
    if attack == 'quote': data['findings'][0]['refs'][0]['quote'] = 'Una cita que nadie escribió.'
    if attack == 'section_bool': data['headline']['refs'][0]['section_index'] = True
    if attack == 'section_title': data['headline']['refs'][0]['section_title'] = 'Otro título'
    if attack == 'kind': data['findings'][0]['kind'] = 'winner'
    if attack == 'extra_field': data['findings'][0]['implication'] = 'Nuevo consejo'
    with pytest.raises(service.ResultsError, match='payload_invalid'):
        service.validate_results(data, source)


def test_source_percentages_remain_literal_without_new_quantification(case):
    case.markdown_content += '\n\nEl informe cita un20% como contexto; no estima apoyo electoral.'
    selection = payload(); selection['headline'] = 's2_p2'
    data = service.project_selection(selection, service.report_source(case))
    assert data['headline']['text'] == 'El informe cita un20% como contexto; no estima apoyo electoral.'
    assert service.validate_results(data, service.report_source(case)) == data


@pytest.mark.parametrize('text', [
    'Solo si se aprueban los presupuestos:\n\nSe convocarán elecciones antes de diciembre.',
    'No ocurrió lo siguiente:\n\n- El Gobierno convocó elecciones.\n- Se aprobó el decreto.',
    '- Solo si el Congreso lo aprueba:\n\n  - El decreto entrará en vigor.\n\n- No existe aprobación todavía.',
    '### Lo que NO sabemos\n\nNo hay un acuerdo confirmado.\n\nLa fecha sigue pendiente.'
])
def test_whole_units_preserve_negated_intro_parent_and_heading(case, text):
    case.markdown_content = '## Contexto\n\n' + text
    catalog = service.evidence_catalog(service.report_source(case))
    last = list(catalog.values())[-1]
    assert last['selectable']
    assert last['quote'] == text
    assert ('No ocurrió' in last['quote'] or 'Solo si' in last['quote'] or 'NO sabemos' in last['quote'] or 'Solo si se aprueban' in last['quote'])


def test_catalog_does_not_cut_long_paragraphs_and_keeps_source(case):
    paragraph = 'Una oración completa que conserva sujeto y condición. ' * 40
    case.markdown_content = '## Texto\n\n' + paragraph
    catalog = service.evidence_catalog(service.report_source(case))
    assert len(catalog) == 1
    assert catalog['s1_p1']['quote'] == paragraph.rstrip()
    assert not catalog['s1_p1']['selectable']


def test_headers_anonymous_dialogue_and_attribution_only_not_selectable(case):
    case.markdown_content = '## Texto\n\n### Un subtítulo largo\n\n> Una persona dijo que no confía.\n\nUn entrevistado lo resume así:'
    catalog = service.evidence_catalog(service.report_source(case))
    assert all(not item['selectable'] for item in catalog.values())


def test_cache_stale_and_legacy_version_never_call_model(case, monkeypatch):
    calls = []
    monkeypatch.setattr(service, '_call_model', lambda *args: calls.append(1) or payload())
    ready, status = service.generate_results(case, background=False)
    assert status == 200 and ready['status'] == 'ready' and ready['version'] == 2
    assert service.generate_results(case, background=False)[0] == ready and calls == [1]
    case.markdown_content += '\nCambió el informe.'
    assert service.read_results(case)['status'] == 'stale' and service.read_results(case)['data'] is None
    ready['version'] = 1; service._write(case.report_id, ready)
    assert service.read_results(case)['error_code'] == 'payload_invalid' and calls == [1]


def test_restart_and_corrupt_sidecar_fail_closed(case):
    source = service.report_source(case)
    service._write(case.report_id, service._empty('generating', digest=source['report_sha256'], locale='es'))
    assert service.read_results(case)['error_code'] == 'interrupted'
    service._write(case.report_id, {'version': True})
    assert service.read_results(case)['error_code'] == 'payload_invalid'


@pytest.mark.parametrize('change', ['delete', 'source'])
def test_worker_revalidates_and_never_resurrects(case, monkeypatch, change):
    def model(*args):
        if change == 'delete': shutil.rmtree(ReportManager._get_report_folder(case.report_id))
        else:
            current = ReportManager.get_report(case.report_id); current.markdown_content += '\nNueva información.'; ReportManager.save_report(current)
        return payload()
    monkeypatch.setattr(service, '_call_model', model)
    service.generate_results(case, background=False)
    if change == 'delete': assert not __import__('os').path.exists(ReportManager._get_report_folder(case.report_id))
    else: assert service.read_results(ReportManager.get_report(case.report_id))['status'] == 'stale'
    assert not service._inflight


def test_global_cap_and_doubleclick(case, monkeypatch):
    started, release, calls = threading.Event(), threading.Event(), []
    def model(*args):
        calls.append(1); started.set(); assert release.wait(3); return payload()
    monkeypatch.setattr(service, '_call_model', model)
    thread = threading.Thread(target=lambda: service.generate_results(case, background=False)); thread.start()
    try:
        assert started.wait(2)
        assert service.generate_results(case)[1] == 202
        other = copy.copy(case); other.report_id = 'report_synthetic002'; ReportManager.save_report(other)
        with pytest.raises(service.ResultsError, match='busy'): service.generate_results(other)
    finally:
        release.set(); thread.join(4)
    assert calls == [1] and service.read_results(case)['status'] == 'ready'


@pytest.mark.parametrize('repaired', [True, False])
def test_only_one_selection_repair_and_no_free_prose(case, monkeypatch, repaired):
    calls = []
    def model(source, locale):
        calls.append(source); selection = payload()
        if len(calls) == 1 or not repaired: selection['findings'][0]['text'] = 'Nueva afirmación no permitida.'
        return selection
    monkeypatch.setattr(service, '_call_model', model)
    result = service.generate_results(case, background=False)[0]
    assert len(calls) == 2 and result['status'] == ('ready' if repaired else 'failed')
    assert calls[1]['remaining_timeout'] <= 240
    assert calls[1]['repair_error'][0]['path'] == 'findings[0]'
    if not repaired: assert result['data'] is None


def test_provider_secret_not_exposed_and_nonfatal_new_report(case, monkeypatch, caplog):
    monkeypatch.setattr(service, '_call_model', lambda *args: (_ for _ in ()).throw(RuntimeError('PRIVATE_API_SECRET')))
    case.status = ReportStatus.GENERATING; ReportManager.save_report(case)
    ReportAgent.__new__(ReportAgent)._generate_results_opening(case)
    assert service.read_results(case)['error_code'] == 'provider_error'
    assert 'PRIVATE_API_SECRET' not in json.dumps(service.read_results(case)) + caplog.text


def test_model_only_selects_ids_and_has_bounded_cost(case, monkeypatch):
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(payload())))])
    def client(**kwargs):
        captured['client'] = kwargs
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(service, 'OpenAI', client)
    REAL_CALL_MODEL(service.report_source(case), 'es')
    assert captured['client']['max_retries'] == 0 and captured['client']['timeout'] <= 240
    assert captured['max_tokens'] <= service.Config.LLM_MAX_TOKENS_CAP
    assert [m['role'] for m in captured['messages']] == ['system', 'user']
    user = json.loads(captured['messages'][1]['content'])
    assert user['source_units']['s1_p1']['quote'] in TEXT
    assert 'Never write prose' in captured['messages'][0]['content']


def test_malformed_json_fails_without_syntax_retry(case, monkeypatch):
    calls = []
    def create(**kwargs):
        calls.append(1)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='invalid JSON'))])
    monkeypatch.setattr(service, 'OpenAI', lambda **kw: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(service, '_call_model', REAL_CALL_MODEL)
    assert service.generate_results(case, background=False)[0]['error_code'] == 'provider_invalid_response'
    assert calls == [1]


def test_limits_reject_before_paid_selection(case):
    case.markdown_content = 'x' * (service.MAX_SOURCE + 1)
    with pytest.raises(service.ResultsError, match='source_too_large'): service.generate_results(case)
    case.markdown_content = '## ' + 'x' * 501 + '\n\nTexto completo.'
    with pytest.raises(service.ResultsError, match='source_invalid'): service.generate_results(case)
    case.markdown_content = '## Texto\n\n' + 'Texto demasiado largo. ' * 100
    with pytest.raises(service.ResultsError, match='source_invalid'): service.generate_results(case)


@pytest.fixture()
def client(case):
    from flask import Flask, g, request, jsonify
    from app.api import report_bp
    from app.api import report  # noqa: F401
    from app.utils.access import ADMIN, authorize_request
    app = Flask(__name__); app.config['TESTING'] = True
    @app.before_request
    def auth():
        if request.headers.get('Authorization') != 'Bearer synthetic-token': return jsonify(success=False), 401
        g.identity = ADMIN
        return authorize_request()
    app.register_blueprint(report_bp, url_prefix='/api/report')
    return app.test_client()


def test_api_auth_get_download_and_cached_post_have_no_cost(case, client, monkeypatch):
    url, headers, calls = '/api/report/' + case.report_id, {'Authorization': 'Bearer synthetic-token'}, []
    monkeypatch.setattr(service, '_call_model', lambda *args: calls.append(1) or payload())
    assert client.post(url + '/results').status_code == 401
    assert client.get(url, headers=headers).json['data']['results']['status'] == 'not_generated'
    assert client.get(url + '/download', headers=headers).status_code == 200 and not calls
    service.generate_results(case, background=False)
    assert client.post(url + '/results', headers=headers).status_code == 200 and calls == [1]


def test_pdf_shows_literal_findings_not_free_implications(case):
    from app.services.report_pdf import build_html
    data = service.generate_results(case, background=False)[0]['data']
    document = build_html(title='Ensayo', summary=data['headline']['text'], question=case.simulation_requirement,
                          body_html='<main>CUERPO ORIGINAL</main>', meta={'people':70}, locale='es', results_data=data)
    assert 'Qué implica' not in document and 'Posiciones observadas' in document
    assert document.index('CUERPO ORIGINAL') < document.index('Respaldo del resumen')
    assert 'class="stat"' not in document
    assert 'El precio provocó dudas' in document


def test_bold_standalone_title_is_not_a_finding(case):
    case.markdown_content = '## Texto\n\n**Los participantes ante la propuesta**\n\nEl precio provocó dudas y la prueba redujo esa incertidumbre.'
    catalog = service.evidence_catalog(service.report_source(case))
    assert not catalog['s1_p1']['selectable']
    assert catalog['s1_p2']['selectable']
    assert catalog['s1_p2']['quote'].startswith('**Los participantes')


def test_api_generating_report_denied_before_model(case, client, monkeypatch):
    case.status = ReportStatus.GENERATING
    ReportManager.save_report(case)
    monkeypatch.setattr(service, '_call_model', lambda *args: pytest.fail('no paid work before completed'))
    response = client.post('/api/report/' + case.report_id + '/results', headers={'Authorization': 'Bearer synthetic-token'})
    assert response.status_code == 409 and response.json['error_code'] == 'report_not_ready'


def test_pending_direct_denied_before_model(case, monkeypatch):
    case.status = ReportStatus.PENDING
    monkeypatch.setattr(service, '_call_model', lambda *args: pytest.fail('no paid work before completed'))
    with pytest.raises(service.ResultsError, match='report_not_ready'):
        service.generate_results(case)


@pytest.mark.parametrize('finish,content,code', [('length', '{}', 'provider_token_limit'),
                                               ('stop', 'invalid JSON after correction', 'provider_invalid_response')])
def test_second_selection_provider_failure_has_no_third_call(case, monkeypatch, finish, content, code):
    calls = []
    def create(**kwargs):
        calls.append(1)
        invalid = dict(payload(), advice='Free prose rejected')
        reason = 'stop' if len(calls) == 1 else finish
        answer = json.dumps(invalid) if len(calls) == 1 else content
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=reason, message=SimpleNamespace(content=answer))])
    monkeypatch.setattr(service, 'OpenAI', lambda **kw: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(service, '_call_model', REAL_CALL_MODEL)
    result = service.generate_results(case, background=False)[0]
    assert calls == [1, 1] and result['status'] == 'failed' and result['data'] is None
    assert result['error_code'] == code


def test_expired_deadline_does_not_spend_on_selection_correction(case, monkeypatch):
    calls, moments = [], iter([100, 341])
    monkeypatch.setattr(service, 'time', SimpleNamespace(monotonic=lambda: next(moments)))
    monkeypatch.setattr(service, '_call_model', lambda *args: calls.append(1) or dict(payload(), advice='Invalid field'))
    result = service.generate_results(case, background=False)[0]
    assert calls == [1] and result['status'] == 'failed' and result['data'] is None
