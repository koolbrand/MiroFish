"""El tope de memoria del recomendador TwHIN-BERT reparte el corpus en lotes pequeños y trunca."""
import os
import sys

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('oasis')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import recsys_memory  # noqa: E402


class FakeTokenizer:
    def __init__(self):
        self.calls = []

    def __call__(self, texts, **kwargs):
        self.calls.append((len(texts), kwargs))
        n = len(texts)
        return {'input_ids': torch.zeros(n, 3, dtype=torch.long),
                'attention_mask': torch.ones(n, 3, dtype=torch.long)}


class FakeOutput:
    def __init__(self, n):
        self.pooler_output = torch.ones(n, 4)


class FakeModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))

    def forward(self, input_ids, attention_mask):
        return FakeOutput(input_ids.shape[0])


def test_lotes_acotados_y_truncado():
    assert recsys_memory.apply()
    from oasis.social_platform import recsys

    tok, model = FakeTokenizer(), FakeModel()
    # OASIS pide lotes de 1000: con el tope deben salir lotes de 64 como mucho
    vectors = recsys.generate_post_vector(model, tok, ['texto'] * 150, batch_size=1000)

    assert tuple(vectors.shape) == (150, 4)
    sizes = [n for n, _ in tok.calls]
    assert sizes == [64, 64, 22]
    for _, kwargs in tok.calls:
        assert kwargs['truncation'] is True
        assert kwargs['max_length'] == recsys_memory.RECSYS_MAX_TOKENS


def test_apply_es_idempotente():
    from oasis.social_platform import recsys
    assert recsys_memory.apply()
    first = recsys.generate_post_vector
    assert recsys_memory.apply()
    assert recsys.generate_post_vector is first
