"""
PDF del informe con la identidad de Simuloo (WeasyPrint).

Parte del Markdown del informe y de unos pocos datos de la simulación (personas, rondas, acciones) y lo
maqueta en A4 con la marca: portada de tinta con el logotipo, título con el bloque lima, tipografía
Inter Tight + JetBrains Mono (incrustadas), secciones numeradas, citas con filete lima y pie con la
paginación.

Seguridad: el Markdown lo escribe un modelo a partir de material del usuario y de resultados de búsqueda
de internet, así que es texto no fiable.
  - El HTML en bruto se escapa antes de convertir (un `<script>` o un `<img src=http://…>` se ve como texto).
  - WeasyPrint solo puede leer las fuentes empaquetadas y `data:`: cualquier otra URL (red interna, http)
    se rechaza (SSRF).
  - Los enlaces solo conservan http, https y mailto; las imágenes se sustituyen por su texto alternativo.
"""

import html
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.report_pdf')

FONT_DIR = (Path(__file__).resolve().parent.parent / "assets" / "fonts").resolve()

# Tinta, lima y crema de Koolbrand (koolbrand.css)
INK, INK_2, LIME, LIME_DARK, LIME_SOFT = "#111111", "#2A2A2A", "#CCE673", "#5C6C16", "#EFF8D8"
GRAY, GRAY_LINE, CREAM = "#6E6E6E", "#DDDDDD", "#F7F6F3"

# Como mucho dos PDF a la vez: maquetar uno ocupa CPU y memoria unos segundos
_SLOTS = threading.BoundedSemaphore(2)

# ============== Textos por idioma ==============

TEXTS = {
    "es": {
        "kind": "Informe de simulación", "brief_kind": "Brief inicial", "question": "Pregunta", "summary": "En pocas palabras",
        "people": "Agentes simulados", "rounds": "Rondas", "actions": "Acciones",
        "generated": "Generado el {date}", "footer": "Simuloo · by Koolbrand",
        "page": ("Página ", " de ", ""),
        "note_title": "Cómo leer este informe",
        "note": "Sale de una simulación con personas creadas por IA a partir de tu material: sirve para ensayar "
                "la decisión y ver por dónde puede torcerse, no para garantizarla. Las opiniones son simuladas.",
        "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                   "octubre", "noviembre", "diciembre"],
        "date": "{d} de {month} de {y}",
    },
    "en": {
        "kind": "Simulation report", "brief_kind": "Initial brief", "question": "Question", "summary": "In a nutshell",
        "people": "Simulated agents", "rounds": "Rounds", "actions": "Actions",
        "generated": "Generated on {date}", "footer": "Simuloo · by Koolbrand",
        "page": ("Page ", " of ", ""),
        "note_title": "How to read this report",
        "note": "It comes from a simulation with AI-created people built from your material: it helps you rehearse "
                "the decision and see where it could go wrong, not guarantee it. The opinions are simulated.",
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"],
        "date": "{month} {d}, {y}",
    },
    "zh": {
        "kind": "模拟报告", "brief_kind": "初始简报", "question": "问题", "summary": "一句话概括",
        "people": "模拟代理", "rounds": "轮数", "actions": "行动",
        "generated": "生成于 {date}", "footer": "Simuloo · by Koolbrand",
        "page": ("第 ", " 页 / 共 ", " 页"),
        "note_title": "如何阅读本报告",
        "note": "本报告来自基于你的材料由 AI 创建的人物所做的模拟：它帮助你预演决策、看出可能出问题的地方，"
                "而不是保证结果。其中的观点均为模拟。",
        "months": [f"{i}月" for i in range(1, 13)],
        "date": "{y}年{m}月{d}日",
    },
}

RESULT_TEXTS = {
    'es': {'support_title': 'Respaldo del resumen', 'title': 'Resultados en un vistazo', 'finding': 'Hallazgo', 'implication': 'Qué implica',
           'contrasts': 'Posiciones observadas', 'findings': 'Hallazgos del informe',
           'kinds': {'reaction': 'Reacción', 'agreement': 'Coincidencia', 'barrier': 'Barrera', 'condition': 'Condición'}, 'tensions': 'Tensiones del resultado', 'conditions': 'Condiciones que cambian el resultado',
           'if': 'Si', 'then': 'Entonces', 'limits': 'Lo que no puede concluirse', 'ref': 'Respaldo en el informe · sección',
           'note': 'Fragmentos del informe sobre el mundo simulado, no prueba independiente. La selección y el tamaño de los bloques no miden apoyo ni probabilidad.'},
    'en': {'support_title': 'Support for the summary', 'title': 'Results at a glance', 'finding': 'Finding', 'implication': 'What it implies',
           'contrasts': 'Observed positions', 'findings': 'Report findings',
           'kinds': {'reaction': 'Reaction', 'agreement': 'Agreement', 'barrier': 'Barrier', 'condition': 'Condition'}, 'tensions': 'Tensions in the result', 'conditions': 'Conditions that change the result',
           'if': 'If', 'then': 'Then', 'limits': 'What cannot be concluded', 'ref': 'Support in the report · section',
           'note': 'Report excerpts about the simulated world, not independent proof. Selection and block sizes do not measure support or probability.'},
    'zh': {'support_title': '摘要依据', 'title': '结果概览', 'finding': '发现', 'implication': '意味着什么',
           'contrasts': '观察到的立场', 'findings': '报告发现',
           'kinds': {'reaction': '反应', 'agreement': '一致之处', 'barrier': '障碍', 'condition': '条件'}, 'tensions': '结果中的张力', 'conditions': '改变结果的条件', 'if': '如果', 'then': '那么',
           'limits': '不能得出的结论', 'ref': '报告中的依据 · 章节',
           'note': '关于模拟世界的报告摘录，而非独立证明。选择与区块大小不代表支持度或概率。'},
}


def _texts(locale: str) -> Dict[str, Any]:
    return TEXTS.get((locale or "es")[:2], TEXTS["es"])


def _format_date(iso: str, texts: Dict[str, Any]) -> str:
    try:
        dt = datetime.fromisoformat((iso or "").replace("Z", ""))
    except ValueError:
        return ""
    return texts["date"].format(d=dt.day, m=dt.month, y=dt.year, month=texts["months"][dt.month - 1])


# ============== Markdown → HTML seguro ==============

_HEAD_RE = re.compile(
    r"\A\s*#\s+(?P<title>[^\n]+)\n+(?:(?P<quote>(?:>[^\n]*\n?)+)\n*)?(?:---+\s*\n+)?"
)
_IMG_RE = re.compile(r"<img\b[^>]*?alt=\"([^\"]*)\"[^>]*>|<img\b[^>]*>", re.IGNORECASE)
_HREF_RE = re.compile(r"<a\s+href=\"([^\"]*)\"", re.IGNORECASE)


def split_report(markdown_text: str) -> Tuple[str, str, str]:
    """(título, resumen, cuerpo): el informe empieza con «# Título», una cita-resumen y una línea."""
    text = (markdown_text or "").replace("\r\n", "\n")
    match = _HEAD_RE.match(text)
    if not match:
        return "", "", text.strip()
    quote = match.group("quote") or ""
    summary = " ".join(re.sub(r"^>\s?", "", line).strip() for line in quote.splitlines()).strip()
    return match.group("title").strip(), summary, text[match.end():].strip()


def _safe_href(match: "re.Match") -> str:
    href = html.unescape(match.group(1)).strip()
    return match.group(0) if re.match(r"(https?://|mailto:)", href, re.IGNORECASE) else "<a"


def markdown_to_html(markdown_text: str) -> str:
    import markdown as md_lib
    # El HTML en bruto se vuelve texto: solo la sintaxis Markdown genera etiquetas
    escaped = (markdown_text or "").replace("&", "&amp;").replace("<", "&lt;")
    escaped = re.sub(r"&amp;(#?\w+;)", r"&\1", escaped)   # respeta las entidades que ya venían escritas (&nbsp;)
    body = md_lib.markdown(escaped, extensions=["tables", "sane_lists", "fenced_code"], output_format="html")
    body = _IMG_RE.sub(lambda m: html.escape(m.group(1) or ""), body)
    return _HREF_RE.sub(_safe_href, body)


# ============== Maquetación ==============

def _css(locale: str, fuente: str = "") -> str:
    t = _texts(locale)
    # «Fuente de datos: …» en el pie de cada página si el público se ancló a datos reales. Se calcula fuera del
    # f-string: Python 3.11 (el del CI) no admite barras invertidas dentro de sus expresiones.
    fuente_css = fuente.replace(chr(92), "").replace('"', "").replace(chr(10), " ")
    pie_centro = (
        '@bottom-center { content: "' + fuente_css + '"; font: 400 7.5pt \'JBM-500\', \'DejaVu Sans Mono\', monospace; '
        'color: ' + GRAY + '; }'
    ) if fuente_css else ""
    pre, mid, post = t["page"]
    fonts = FONT_DIR.as_uri()
    faces = "".join(
        f"@font-face {{ font-family: '{fam}'; font-weight: 400; src: url('{fonts}/{file}'); }}\n"
        for fam, file in [
            ("IT-400", "InterTight-Regular.ttf"), ("IT-500", "InterTight-Medium.ttf"),
            ("IT-700", "InterTight-Bold.ttf"), ("IT-800", "InterTight-ExtraBold.ttf"),
            ("JBM-400", "JetBrainsMono-Regular.ttf"), ("JBM-500", "JetBrainsMono-Medium.ttf"),
            ("JBM-700", "JetBrainsMono-Bold.ttf"),
        ]
    )
    return faces + f"""
@page {{
  size: A4;
  margin: 24mm 18mm 20mm 18mm;
  @top-left {{ content: element(running-logo); vertical-align: middle; }}
  @top-right {{ content: "{t['kind']}"; font: 400 7.5pt 'JBM-500', 'DejaVu Sans Mono', monospace; letter-spacing: .12em;
                text-transform: uppercase; color: {GRAY}; vertical-align: middle; }}
  @bottom-left {{ content: "{t['footer']}"; font: 400 7.5pt 'JBM-500', 'DejaVu Sans Mono', monospace; color: {GRAY}; }}
  {pie_centro}
  @bottom-right {{ content: "{pre}" counter(page) "{mid}" counter(pages) "{post}"; font: 400 7.5pt 'JBM-500', 'DejaVu Sans Mono', monospace; color: {GRAY}; }}
}}
@page :first {{ margin-top: 0; @top-left {{ content: none; }} @top-right {{ content: none; }} }}
html {{ font-family: 'IT-400', 'DejaVu Sans', 'WenQuanYi Micro Hei', sans-serif; font-size: 10.5pt; line-height: 1.55;
        color: {INK}; font-weight: 400; hyphens: manual; }}
body {{ margin: 0; counter-reset: section; }}
.mono {{ font-family: 'JBM-400', 'DejaVu Sans Mono', monospace; }}

/* logotipo: «simul» + las dos «o» dentro del bloque lima rotado */
.logo {{ display: inline-flex; align-items: center; font-family: 'IT-800', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; letter-spacing: -.04em; line-height: 1; white-space: nowrap; }}
.logo .eyes {{ display: inline-block; background: {LIME}; border-radius: .14em; padding: .09em .1em .06em; margin-left: .05em;
               transform: rotate(-2deg); }}
.logo svg {{ display: block; height: .58em; width: 1.13em; }}
#running-logo {{ position: running(running-logo); font-size: 13pt; color: {INK}; }}

/* portada */
.cover-band {{ background: {INK}; color: #fff; margin: 0 -18mm; padding: 11mm 18mm 9mm; display: flex; justify-content: space-between;
               align-items: center; }}
.cover-band .logo {{ font-size: 22pt; color: #fff; }}
.cover-band .logo .eyes {{ color: {INK}; }}
.cover-tag {{ font: 400 8pt 'JBM-700', 'DejaVu Sans Mono', monospace; letter-spacing: .16em; text-transform: uppercase; color: {LIME}; }}
.cover-title {{ margin: 16mm 0 0; font-size: 27pt; line-height: 1.08; font-family: 'IT-800', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; letter-spacing: -.025em; hyphens: manual; }}
.cover-title .hl {{ background: {LIME}; color: {INK}; padding: 0 .12em .03em; border-radius: 4pt; box-decoration-break: clone; }}
.cover-date {{ margin-top: 7mm; font: 400 8pt 'JBM-500', 'DejaVu Sans Mono', monospace; letter-spacing: .1em; text-transform: uppercase; color: {GRAY}; }}
.stats {{ display: flex; margin: 9mm 0 0; border-top: 1.2pt solid {INK}; border-bottom: .6pt solid {INK}; }}
.stat {{ flex: 1; padding: 4mm 0 3.6mm; border-left: .6pt solid {GRAY_LINE}; padding-left: 5mm; }}
.stat:first-child {{ border-left: 0; padding-left: 0; }}
.stat b {{ display: block; font-size: 20pt; font-family: 'IT-800', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; letter-spacing: -.03em; line-height: 1; }}
.stat span {{ display: block; margin-top: 1.6mm; font: 400 7pt 'JBM-500', 'DejaVu Sans Mono', monospace; letter-spacing: .12em; text-transform: uppercase; color: {GRAY}; }}
.box {{ margin-top: 8mm; padding: 5mm 6mm; border: 1.1pt solid {INK}; border-radius: 3pt; break-inside: avoid; }}
.box .label {{ font: 400 7.5pt 'JBM-700', 'DejaVu Sans Mono', monospace; letter-spacing: .14em; text-transform: uppercase; color: {LIME_DARK}; margin: 0 0 1.5mm; }}
.box p {{ margin: 0; font-size: 11pt; line-height: 1.5; font-family: 'IT-500', 'WenQuanYi Micro Hei', sans-serif; }}
.box.lead p {{ font-size: 12pt; color: {INK_2}; }}

.results-opening {{ break-before: page; break-after: page; padding-top: 3mm; }}
.results-title {{ font: 400 22pt 'IT-800', 'WenQuanYi Micro Hei', sans-serif; margin: 0 0 4mm; }}
.results-note {{ font-size: 9pt; color: {INK_2}; margin-bottom: 6mm; }}
.result-card {{ margin-bottom: 5mm; border: .8pt solid {GRAY_LINE}; border-radius: 3pt; padding: 5mm; break-inside: avoid; }}
.result-card-title {{ font: 400 13pt 'IT-700', 'WenQuanYi Micro Hei', sans-serif; margin-bottom: 3mm; }}
.result-pair {{ display: table; width: 100%; table-layout: fixed; }}
.result-pole {{ display: table-cell; box-sizing: border-box; width: 47%; padding: 3mm; background: {CREAM}; vertical-align: top; font-size: 10pt; overflow-wrap: anywhere; }}
.result-pole:last-child {{ background: {LIME_SOFT}; }}
.result-pair.tension-pair .result-pole {{ background: {CREAM}; }}
.result-link {{ display: table-cell; width: 6%; text-align: center; vertical-align: middle; font-size: 13pt; color: {LIME_DARK}; }}
.result-label {{ display: block; font: 400 7pt 'JBM-700', 'WenQuanYi Micro Hei', sans-serif; color: {LIME_DARK}; margin-bottom: 2mm; }}
.result-explanation {{ margin: 3mm 0 0; font-size: 10pt; }}
.result-ref {{ margin: 3mm 0 0; border-left: 2pt solid {LIME}; padding: 1mm 0 0 3mm; font-size: 8.2pt; line-height: 1.45; color: {INK_2}; }}
.result-ref-label {{ font-family: 'IT-700', 'WenQuanYi Micro Hei', sans-serif; display: block; margin-bottom: 1mm; }}
.result-subtitle {{ font: 400 16pt 'IT-700', 'WenQuanYi Micro Hei', sans-serif; margin: 7mm 0 3mm; break-after: avoid; }}

/* cuerpo */
.body {{ margin-top: 9mm; }}
h2 {{ counter-increment: section; margin: 11mm 0 3.5mm; padding-top: 4mm; border-top: 1.2pt solid {INK}; font-size: 16pt; line-height: 1.18;
      font-family: 'IT-800', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; letter-spacing: -.02em; break-after: avoid; }}
h2::before {{ content: counter(section, decimal-leading-zero); display: block; margin-bottom: 1.6mm; font: 400 8pt 'JBM-700', 'DejaVu Sans Mono', monospace;
              letter-spacing: .14em; color: {LIME_DARK}; }}
h3 {{ margin: 6mm 0 2mm; font-size: 12.5pt; font-family: 'IT-700', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; letter-spacing: -.01em; break-after: avoid; }}
h4, h5, h6 {{ margin: 5mm 0 1.5mm; font-size: 10.5pt; font-family: 'IT-700', sans-serif; font-weight: 400; break-after: avoid; }}
p {{ margin: 0 0 3mm; orphans: 3; widows: 3; }}
strong, b {{ font-family: 'IT-700', 'WenQuanYi Micro Hei', sans-serif; font-weight: 400; }}
em {{ font-style: italic; }}
ul, ol {{ margin: 0 0 3.5mm; padding-left: 5.5mm; }}
li {{ margin-bottom: 1.2mm; }}
li::marker {{ color: {LIME_DARK}; font-weight: 700; }}
blockquote {{ margin: 4mm 0; padding: 1.2mm 0 1.2mm 5mm; border-left: 3pt solid {LIME}; font-family: 'IT-500', 'WenQuanYi Micro Hei', sans-serif; color: {INK_2}; break-inside: avoid; }}
blockquote p {{ margin: 0 0 1.5mm; }}
hr {{ border: 0; border-top: .6pt solid {GRAY_LINE}; margin: 6mm 0; }}
a {{ color: {INK}; text-decoration: underline; text-decoration-color: {LIME_DARK}; text-underline-offset: 1.5pt; }}
code {{ font: 400 8.6pt 'JBM-500', 'DejaVu Sans Mono', monospace; background: #ECECEC; padding: 0 1.6pt; border-radius: 2pt; }}
pre {{ margin: 3mm 0; padding: 3mm 4mm; background: {CREAM}; border: .6pt solid {GRAY_LINE}; border-radius: 3pt; white-space: pre-wrap;
       overflow-wrap: anywhere; break-inside: avoid; }}
pre code {{ background: none; padding: 0; font-size: 8.2pt; }}
table {{ width: 100%; border-collapse: collapse; margin: 4mm 0; font-size: 9pt; break-inside: auto; }}
th {{ background: {INK}; color: #fff; text-align: left; padding: 2mm 2.6mm; font: 400 7.5pt 'JBM-700', 'DejaVu Sans Mono', monospace; letter-spacing: .08em;
      text-transform: uppercase; }}
td {{ padding: 2mm 2.6mm; border-bottom: .6pt solid {GRAY_LINE}; vertical-align: top; }}
tr {{ break-inside: avoid; }}
.note {{ margin-top: 12mm; padding: 4.5mm 6mm; background: {LIME_SOFT}; border-left: 3pt solid {LIME_DARK}; border-radius: 0 3pt 3pt 0; break-inside: avoid; }}
.note .label {{ font: 400 7.5pt 'JBM-700', 'DejaVu Sans Mono', monospace; letter-spacing: .14em; text-transform: uppercase; color: {LIME_DARK}; margin-bottom: 1.4mm; }}
.note p {{ margin: 0; font-size: 9.5pt; color: {INK_2}; }}
"""


_EYES_SVG = (
    '<svg viewBox="0 0 124 64" aria-hidden="true"><circle cx="31" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13"/>'
    '<circle cx="93" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13"/></svg>'
)


def _logo() -> str:
    return f'<span class="logo">simul<span class="eyes">{_EYES_SVG}</span></span>'


def _highlight_title(title: str) -> str:
    """El bloque lima de la marca va en la primera frase («Predicción: …» → «Predicción»); sin dos puntos, en la primera palabra."""
    safe = html.escape(title)
    head, sep, rest = title.partition(":")
    if sep and 1 <= len(head.split()) <= 4:
        return f'<span class="hl">{html.escape(head)}:</span>{html.escape(rest)}'
    first, space, rest = safe.partition(" ")
    return f'<span class="hl">{first}</span>{space}{rest}'


def _results_html(data, locale):
    if not data:
        return ''
    labels = RESULT_TEXTS.get((locale or 'es')[:2], RESULT_TEXTS['es'])
    escape = html.escape
    def references(refs):
        return ''.join(f'<div class="result-ref"><span class="result-ref-label">{labels["ref"]} {ref["section_index"]}: '
                       f'{escape(ref["section_title"])}</span></div>' for ref in refs)
    def pair(left, right, left_label='', right_label='', connector='→', tension=False):
        return (f'<div class="result-pair{" tension-pair" if tension else ""}"><div class="result-pole"><span class="result-label">{escape(left_label)}</span>{escape(left)}</div>'
                f'<span class="result-link">{connector}</span><div class="result-pole"><span class="result-label">{escape(right_label)}</span>{escape(right)}</div></div>')
    parts = [f'<section class="results-opening"><div class="results-title">{labels["title"]}</div><p class="results-note">{labels["note"]}</p>',
             references(data['headline']['refs'])]
    for row in data['findings']:
        parts.append(f'<article class="result-card"><div class="result-card-title">{escape(labels["finding"])}</div>'
                     + '<p>' + escape(row['text']).replace('\n', '<br>') + '</p>'
                     + references(row['refs']) + '</article>')
    if data['contrasts']:
        parts.append(f'<div class="result-subtitle">{labels["contrasts"]}</div>')
    for row in data['contrasts']:
        parts.append('<article class="result-card">' + pair(row['left'], row['right'], connector='↔', tension=True)
                     + references(row['refs']) + '</article>')
    parts.append(f'<div class="result-subtitle">{labels["limits"]}</div>')
    for row in data['limitations']:
        parts.append('<article class="result-card"><p>' + escape(row['text']) + '</p>' + references(row['refs']) + '</article>')
    return ''.join(parts) + '</section>'


def _results_support_html(data, locale):
    if not data:
        return ''
    labels = RESULT_TEXTS.get((locale or 'es')[:2], RESULT_TEXTS['es'])
    refs = {}
    for block in [data['headline']] + sum([data[name] for name in ('findings', 'contrasts', 'limitations')], []):
        for ref in block['refs']:
            refs[(ref['section_index'], ref['quote'])] = ref
    parts = [f'<section class="results-opening"><h2>{labels["support_title"]}</h2>']
    for ref in refs.values():
        parts.append(f'<article class="result-card"><div class="result-ref-label">{labels["ref"]} {ref["section_index"]}: '
                     f'{html.escape(ref["section_title"])}</div><p>«{html.escape(ref["quote"])}»</p></article>')
    return ''.join(parts) + '</section>'


def build_html(*, title: str, summary: str, question: str, body_html: str, meta: Dict[str, Any], locale: str,
               completed_at: str = "", created_at: str = "", kind: str = "", show_note: bool = True, results_data=None) -> str:
    t = _texts(locale)
    kind = kind or t["kind"]
    date = _format_date(completed_at or created_at, t)
    question_html = (
        f'<div class="box"><div class="label">{html.escape(t["question"])}</div><p>{html.escape(question)}</p></div>'
        if question else ""
    )
    summary_html = (
        f'<div class="box lead"><div class="label">{html.escape(t["summary"])}</div><p>{html.escape(summary)}</p></div>'
        if summary else ""
    )
    return f"""<!doctype html>
<html lang="{html.escape((locale or 'es')[:2])}"><head><meta charset="utf-8"><title>{html.escape(title or kind)}</title>
<style>{_css(locale, meta.get('fuente_datos') or '')}</style></head>
<body>
<div id="running-logo">{_logo()}</div>
<header class="cover-band">{_logo()}<div class="cover-tag">{html.escape(kind)}</div></header>
<h1 class="cover-title">{_highlight_title(title or kind)}</h1>
<div class="cover-date">{html.escape(t['generated'].format(date=date)) if date else ''}</div>
{question_html}{summary_html}
{_results_html(results_data, locale)}
<main class="body">{body_html}</main>
{_results_support_html(results_data, locale)}
{('<aside class="note"><div class="label">' + html.escape(t['note_title']) + '</div><p>' + html.escape(t['note']) + ((' ' + html.escape(meta['fuente_datos'])) if meta.get('fuente_datos') else '') + '</p></aside>') if show_note else ''}
</body></html>"""


def _make_fetcher():
    """Fetcher de WeasyPrint (API de la v70): solo las fuentes empaquetadas y `data:`; cualquier otra URL se rechaza."""
    from weasyprint.urls import URLFetcher

    class LocalFontsOnly(URLFetcher):
        def fetch(self, url, headers=None):
            if url.startswith("file://"):
                path = Path(url[len("file://"):].split("?", 1)[0].replace("%20", " "))
                try:
                    allowed = path.resolve().is_relative_to(FONT_DIR) and path.suffix.lower() == ".ttf"
                except (OSError, ValueError):
                    allowed = False
                if not allowed:
                    raise ValueError(f"Recurso externo bloqueado en el PDF: {url[:80]}")
            return super().fetch(url, headers)

    return LocalFontsOnly(allowed_protocols=("data", "file"), allow_redirects=False)


def render_pdf(html_text: str) -> bytes:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration
    with _SLOTS:
        document = HTML(string=html_text, base_url=FONT_DIR.as_uri() + "/", url_fetcher=_make_fetcher())
        return document.write_pdf(font_config=FontConfiguration(), pdf_variant=None)


def render_report_pdf(*, markdown_text: str, question: str = "", meta: Optional[Dict[str, Any]] = None,
                      locale: str = "es", completed_at: str = "", created_at: str = "", results=None) -> bytes:
    """PDF (bytes) del informe. `meta`: people, rounds, actions (los que falten no se pintan)."""
    title, summary, body = split_report(markdown_text)
    data = None
    if isinstance(results, dict) and results.get('status') == 'ready':
        from types import SimpleNamespace
        from .report_results import report_source, validate_results, ResultsError
        try:
            source = report_source(SimpleNamespace(markdown_content=markdown_text, simulation_requirement=question))
            if results.get('report_sha256') == source['report_sha256']:
                data = validate_results(results.get('data'), source, stored=True)
                summary = data['headline']['text']
        except ResultsError:
            data = None
    html_text = build_html(
        title=title, summary=summary, question=question, body_html=markdown_to_html(body),
        meta=meta or {}, locale=locale, completed_at=completed_at, created_at=created_at,
        results_data=data,
    )
    return render_pdf(html_text)


def render_brief_pdf(*, markdown_text: str, locale: str = "es", created_at: str = "") -> bytes:
    """PDF (bytes) de un brief: la misma maqueta de marca, con su propia etiqueta y sin la nota de «cómo leer el informe»."""
    # Aquí NO se usa split_report: separa una cita inicial como «resumen» (cosa de informes), y en un brief esa cita son
    # las notas de la plantilla, que se perderían. Solo el «# Título» sube a la portada; el resto es el cuerpo.
    text = (markdown_text or "").replace("\r\n", "\n")
    head = re.match(r"\A\s*#\s+([^\n]+)\n?", text)
    title, body = (head.group(1).strip(), text[head.end():].strip()) if head else ("", text.strip())
    html_text = build_html(
        title=title, summary="", question="", body_html=markdown_to_html(body), meta={}, locale=locale,
        created_at=created_at or datetime.now().isoformat(timespec="seconds"),
        kind=_texts(locale)["brief_kind"], show_note=False,
    )
    return render_pdf(html_text)
