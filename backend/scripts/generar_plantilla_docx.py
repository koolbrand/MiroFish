#!/usr/bin/env python3
"""
Regenera la plantilla de brief en Word que se descarga desde la pantalla de inicio.

La fuente es `backend/app/assets/brief/plantilla-brief-simuloo.md`; el resultado va a
`frontend/public/plantilla-brief-simuloo.docx`. Hay un test (`test_docx.py`) que falla si el .docx publicado ya no
corresponde a la fuente: tras tocar el .md, ejecutar

    cd backend && uv run python scripts/generar_plantilla_docx.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from app.utils.docx_io import build_docx  # noqa: E402

SOURCE = os.path.join(HERE, '..', 'app', 'assets', 'brief', 'plantilla-brief-simuloo.md')
TARGET = os.path.join(HERE, '..', '..', 'frontend', 'public', 'plantilla-brief-simuloo.docx')

with open(SOURCE, encoding='utf-8') as f:
    data = build_docx(f.read(), kind='template')
with open(TARGET, 'wb') as f:
    f.write(data)
print(f'{os.path.normpath(TARGET)}: {len(data)} bytes')
