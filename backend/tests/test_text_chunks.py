"""
El troceado del texto siempre termina, aunque los parámetros sean absurdos, y no cambia con los normales.
"""

import time

import pytest

from app.utils.file_parser import split_text_into_chunks

TEXT = ("Primera frase del documento. Segunda frase, algo más larga que la primera. Tercera frase.\n\n"
        "Otro párrafo con varias oraciones. ¿Y una pregunta? ¡Y una exclamación! Final del párrafo.\n\n") * 40


@pytest.mark.parametrize("size,overlap", [(10, 10), (10, 25), (0, 0), (-5, 3), (1, 1), (50, 50), (500, 500), (500, 5000), (100, 99)])
def test_absurd_parameters_terminate_quickly_and_cover_the_text(size, overlap):
    started = time.monotonic()
    chunks = split_text_into_chunks(TEXT, size, overlap)
    assert time.monotonic() - started < 2
    assert chunks and all(c.strip() for c in chunks)
    assert len(chunks) < len(TEXT)                         # nunca un fragmento por carácter
    assert TEXT.strip().startswith(chunks[0][:20])
    assert TEXT.strip().endswith(chunks[-1][-20:])


def test_normal_parameters_keep_their_results():
    chunks = split_text_into_chunks(TEXT, 500, 50)
    assert 8 <= len(chunks) <= 20
    assert all(len(c) <= 500 for c in chunks)
    # cada fragmento empieza dentro del anterior (solape) y el texto se recorre entero
    joined = " ".join(chunks)
    assert "Final del párrafo." in joined and "Primera frase" in joined


def test_short_and_empty_text():
    assert split_text_into_chunks("   ", 500, 50) == []
    assert split_text_into_chunks("hola", 500, 50) == ["hola"]
