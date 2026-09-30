"""La precarga del modelo del recomendador es opcional, en segundo plano y nunca rompe el arranque."""
import sys
import types

from app.utils import recsys_prewarm


def _fake_hub(monkeypatch, fn):
    mod = types.ModuleType('huggingface_hub')
    mod.snapshot_download = fn
    monkeypatch.setitem(sys.modules, 'huggingface_hub', mod)


def test_descarga_solo_los_cinco_archivos_del_modelo(monkeypatch):
    calls = []
    _fake_hub(monkeypatch, lambda repo, **kw: calls.append((repo, kw)) or '/cache/twhin')
    monkeypatch.delenv('RECSYS_PREWARM', raising=False)

    thread = recsys_prewarm.start_prewarm()
    assert thread is not None
    thread.join(timeout=5)

    assert calls == [('Twitter/twhin-bert-base', {'allow_patterns': recsys_prewarm.FILES})]
    assert 'model.safetensors' in recsys_prewarm.FILES and len(recsys_prewarm.FILES) == 5


def test_se_puede_desactivar(monkeypatch):
    calls = []
    _fake_hub(monkeypatch, lambda *a, **k: calls.append(1))
    monkeypatch.setenv('RECSYS_PREWARM', '0')

    assert recsys_prewarm.start_prewarm() is None
    assert calls == []


def test_un_fallo_de_red_no_propaga(monkeypatch):
    def boom(*a, **k):
        raise OSError('sin red')
    _fake_hub(monkeypatch, boom)
    monkeypatch.delenv('RECSYS_PREWARM', raising=False)

    thread = recsys_prewarm.start_prewarm()
    thread.join(timeout=5)
    assert not thread.is_alive()   # terminó sin lanzar
