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
        "kind": "Informe de predicción", "question": "Pregunta", "summary": "En pocas palabras",
        "people": "Personas simuladas", "rounds": "Rondas", "actions": "Acciones",
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
        "kind": "Prediction report", "question": "Question", "summary": "In a nutshell",
        "people": "Simulated people", "rounds": "Rounds", "actions": "Actions",
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
        "kind": "预测报告", "question": "问题", "summary": "一句话概括",
        "people": "模拟人物", "rounds": "轮数", "actions": "行动",
        "generated": "生成于 {date}", "footer": "Simuloo · by Koolbrand",
        "page": ("第 ", " 页 / 共 ", " 页"),
        "note_title": "如何阅读本报告",
        "note": "本报告来自基于你的材料由 AI 创建的人物所做的模拟：它帮助你预演决策、看出可能出问题的地方，"
                "而不是保证结果。其中的观点均为模拟。",
        "months": [f"{i}月" for i in range(1, 13)],
        "date": "{y}年{m}月{d}日",
    },
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

def _css(locale: str) -> str:
    t = _texts(locale)
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


def build_html(*, title: str, summary: str, question: str, body_html: str, meta: Dict[str, Any], locale: str,
               completed_at: str = "", created_at: str = "") -> str:
    t = _texts(locale)
    date = _format_date(completed_at or created_at, t)
    stats = [(t["people"], meta.get("people")), (t["rounds"], meta.get("rounds")), (t["actions"], meta.get("actions"))]
    stats_html = "".join(
        f'<div class="stat"><b>{html.escape(str(value))}</b><span>{html.escape(label)}</span></div>'
        for label, value in stats if value not in (None, "", 0)
    )
    question_html = (
        f'<div class="box"><div class="label">{html.escape(t["question"])}</div><p>{html.escape(question)}</p></div>'
        if question else ""
    )
    summary_html = (
        f'<div class="box lead"><div class="label">{html.escape(t["summary"])}</div><p>{html.escape(summary)}</p></div>'
        if summary else ""
    )
    return f"""<!doctype html>
<html lang="{html.escape((locale or 'es')[:2])}"><head><meta charset="utf-8"><title>{html.escape(title or t['kind'])}</title>
<style>{_css(locale)}</style></head>
<body>
<div id="running-logo">{_logo()}</div>
<header class="cover-band">{_logo()}<div class="cover-tag">{html.escape(t['kind'])}</div></header>
<h1 class="cover-title">{_highlight_title(title or t['kind'])}</h1>
<div class="cover-date">{html.escape(t['generated'].format(date=date)) if date else ''}</div>
{('<div class="stats">' + stats_html + '</div>') if stats_html else ''}
{question_html}{summary_html}
<main class="body">{body_html}</main>
<aside class="note"><div class="label">{html.escape(t['note_title'])}</div><p>{html.escape(t['note'])}</p></aside>
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
                      locale: str = "es", completed_at: str = "", created_at: str = "") -> bytes:
    """PDF (bytes) del informe. `meta`: people, rounds, actions (los que falten no se pintan)."""
    title, summary, body = split_report(markdown_text)
    html_text = build_html(
        title=title, summary=summary, question=question, body_html=markdown_to_html(body),
        meta=meta or {}, locale=locale, completed_at=completed_at, created_at=created_at,
    )
    return render_pdf(html_text)
