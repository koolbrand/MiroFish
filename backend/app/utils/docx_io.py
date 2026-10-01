"""
Documentos de Word (.docx): leer su texto y escribir uno sencillo.

Por qué sin librería: un .docx es un zip con XML y sacar el texto son ~100 líneas; así no entra una dependencia más (y
sus avisos de seguridad) en la imagen, y las defensas quedan a la vista. Se usa `lxml`, que ya viene con WeasyPrint.

El documento lo sube una persona cualquiera, así que se trata como entrada hostil:
- **Bomba de descompresión** (un zip de 50 KB que expande a gigas): se mira el tamaño declarado y la proporción antes de
  descomprimir, y además se lee con un tope (el tamaño declarado en la cabecera del zip puede mentir).
- **Bomba de entidades / XXE**: un .docx de verdad nunca lleva `<!DOCTYPE` ni `<!ENTITY`; si aparece, se rechaza antes de
  parsear, y el parser va sin resolver entidades, sin red y sin árboles enormes.
- **Zip raro**: nº de entradas acotado y rutas absolutas o con `..` rechazadas (aquí no se extrae nada a disco, pero un
  documento así no es legítimo).

Qué se lee: el cuerpo (párrafos, títulos, listas y tablas, también dentro de controles de contenido) y las notas al
pie. Cambios sin aceptar: se lee el texto insertado y NO el borrado. No se lee: imágenes, cuadros de texto flotantes,
cabeceras y pies, comentarios. Un .doc antiguo (OLE) o uno cifrado no son zip: error claro.
"""

import io
import os
import re
import zipfile
from typing import List, Optional
from xml.sax.saxutils import escape

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_NS = {'w': W}


def _w(tag: str) -> str:
    return f'{{{W}}}{tag}'


MAX_ENTRIES = 2000
MAX_XML_BYTES = 30 * 1024 * 1024          # descomprimido, por parte
MAX_RATIO = 250                           # descomprimido / comprimido; el texto XML real ronda 5–20
ZIP_MAGIC = b'PK\x03\x04'
OLE_MAGIC = b'\xd0\xcf\x11\xe0'           # .doc antiguo y .docx cifrados con contraseña


class DocxError(ValueError):
    """Documento que no se puede leer. `code` es una clave de i18n (`api.<code>`)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _read_part(zf: zipfile.ZipFile, name: str) -> Optional[bytes]:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_XML_BYTES or (info.compress_size and info.file_size / info.compress_size > MAX_RATIO):
        raise DocxError('docxTooBig')
    with zf.open(info) as f:
        data = f.read(MAX_XML_BYTES + 1)          # el tamaño declarado puede mentir: se lee con tope
    if len(data) > MAX_XML_BYTES:
        raise DocxError('docxTooBig')
    return data


def _parse(xml: bytes):
    head = xml[:4096].lower()
    if b'<!doctype' in head or b'<!entity' in head or b'<!doctype' in xml.lower():
        raise DocxError('docxUnreadable')
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False,
                             huge_tree=False, remove_comments=True, remove_pis=True)
    try:
        return etree.fromstring(xml, parser)
    except etree.XMLSyntaxError:
        raise DocxError('docxUnreadable')


_HEADING_RE = re.compile(r'^(?:heading|ttulo|titre|titel|kop|titolo)\s*([1-6])$', re.I)
# Estilos de lista de Word (el marcador está en la definición del estilo, no en el párrafo): ListBullet, ListParagraph, «Prrafodelista»…
_LIST_STYLE_RE = re.compile(r'^(list|lista|prrafodelista|liste)', re.I)
_TITLE_STYLES = {'title', 'ttulo', 'titre', 'titel', 'titolo'}


def _style(p) -> str:
    node = p.find('w:pPr/w:pStyle', _NS)
    return (node.get(_w('val')) if node is not None else '') or ''


def _para_text(p) -> str:
    """Texto de un párrafo en el orden del documento. `w:delText` (texto borrado con cambios sin aceptar) no cuenta."""
    out: List[str] = []
    for el in p.iter():
        if el.tag == _w('t') and el.text:
            out.append(el.text)
        elif el.tag == _w('tab'):
            out.append('\t')
        elif el.tag in (_w('br'), _w('cr')):
            out.append('\n')
        elif el.tag == _w('noBreakHyphen'):
            out.append('-')
    return ''.join(out)


def _block_lines(el, lines: List[str]) -> None:
    if el.tag == _w('p'):
        text = _para_text(el).strip()
        if not text:
            lines.append('')
            return
        style = _style(el)
        m = _HEADING_RE.match(style.replace(' ', ''))
        if m:
            text = '#' * min(int(m.group(1)), 6) + ' ' + text
        elif style.lower() in _TITLE_STYLES:
            text = '# ' + text
        elif el.find('w:pPr/w:numPr', _NS) is not None or _LIST_STYLE_RE.match(style):
            text = '- ' + text
        lines.append(text)
    elif el.tag == _w('tbl'):
        for row in el.findall('w:tr', _NS):
            cells = []
            for cell in row.findall('w:tc', _NS):
                parts: List[str] = []
                for p in cell.iter(_w('p')):
                    t = _para_text(p).strip()
                    if t:
                        parts.append(t)
                cells.append(' '.join(parts))
            if any(cells):
                lines.append(' | '.join(cells))
        lines.append('')
    elif el.tag == _w('sdt'):                                   # control de contenido: el texto está dentro
        content = el.find('w:sdtContent', _NS)
        if content is not None:
            for child in content:
                _block_lines(child, lines)
    elif el.tag in (_w('ins'), _w('moveTo'), _w('customXml')):
        for child in el:
            _block_lines(child, lines)


def extract_docx_text(source) -> str:
    """Texto de un .docx (ruta o fichero abierto). Lanza `DocxError` con una clave de i18n si no se puede leer."""
    if isinstance(source, (str, os.PathLike)):
        fileobj, close = open(source, 'rb'), True
    else:
        fileobj, close = source, False
    try:
        head = fileobj.read(4)
        fileobj.seek(0)
        if head.startswith(OLE_MAGIC):
            raise DocxError('docxOld')                           # .doc antiguo o documento con contraseña
        if not head.startswith(ZIP_MAGIC):
            raise DocxError('docxUnreadable')
        try:
            zf = zipfile.ZipFile(fileobj)
        except zipfile.BadZipFile:
            raise DocxError('docxUnreadable')
        with zf:
            names = zf.namelist()
            if len(names) > MAX_ENTRIES:
                raise DocxError('docxTooBig')
            if any(n.startswith('/') or '..' in n.split('/') for n in names):
                raise DocxError('docxUnreadable')
            if 'word/document.xml' not in names or '[Content_Types].xml' not in names:
                raise DocxError('docxUnreadable')                # un zip cualquiera (o un xlsx/pptx con otra extensión)
            xml = _read_part(zf, 'word/document.xml')
            body = _parse(xml).find('w:body', _NS)
            if body is None:
                raise DocxError('docxUnreadable')
            lines: List[str] = []
            for child in body:
                _block_lines(child, lines)
            for part, tag in (('word/footnotes.xml', 'footnote'), ('word/endnotes.xml', 'endnote')):
                data = _read_part(zf, part) if part in names else None
                if not data:
                    continue
                notes = [_para_text(p).strip()
                         for note in _parse(data).findall(f'w:{tag}', _NS) if note.get(_w('type')) in (None, 'normal')
                         for p in note.iter(_w('p'))]
                notes = [n for n in notes if n]
                if notes:
                    lines += ['', *notes]
    except zipfile.BadZipFile:
        raise DocxError('docxUnreadable')
    finally:
        if close:
            fileobj.close()

    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if not text:
        raise DocxError('docxEmpty')
    return text


# ---------------------------------------------------------------------------------------------------------------
# Escribir
# ---------------------------------------------------------------------------------------------------------------

_CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/>'
                  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                  '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                  '</Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
         '</Relationships>')
_DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '</Relationships>')


def _style_xml(style_id: str, name: str, size_half_pts: int, bold: bool, before: int, after: int, outline: Optional[int] = None) -> str:
    return (f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            f'<w:pPr><w:keepNext/><w:spacing w:before="{before}" w:after="{after}"/>'
            + (f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else '') +
            f'</w:pPr><w:rPr>{"<w:b/>" if bold else ""}<w:color w:val="111111"/><w:sz w:val="{size_half_pts}"/></w:rPr></w:style>')


_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:styles xmlns:w="{W}">'
           '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>'
           '<w:sz w:val="22"/><w:lang w:val="es-ES"/></w:rPr></w:rPrDefault>'
           '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
           + _style_xml('Heading1', 'heading 1', 40, True, 360, 160, 0)
           + _style_xml('Heading2', 'heading 2', 30, True, 300, 120, 1)
           + _style_xml('Heading3', 'heading 3', 26, True, 240, 100, 2)
           + '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:qFormat/>'
             '<w:pPr><w:ind w:left="567"/></w:pPr><w:rPr><w:i/><w:color w:val="555555"/></w:rPr></w:style>'
           '</w:styles>')

_INLINE_RE = re.compile(r'(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)')
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def _runs(text: str, base_italic: bool = False) -> str:
    out = []
    for piece in _INLINE_RE.split(text):
        if not piece:
            continue
        bold = italic = mono = False
        if piece.startswith('**') and piece.endswith('**') and len(piece) > 4:
            bold, piece = True, piece[2:-2]
        elif piece.startswith('*') and piece.endswith('*') and len(piece) > 2:
            italic, piece = True, piece[1:-1]
        elif piece.startswith('`') and piece.endswith('`') and len(piece) > 2:
            mono, piece = True, piece[1:-1]
        # El esquema de Word fija el orden: rFonts antes de b e i (LibreOffice lo tolera; Word, no siempre)
        props = ('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>' if mono else '') + ('<w:b/>' if bold else '') + \
                ('<w:i/>' if (italic or base_italic) else '')
        out.append(f'<w:r>{"<w:rPr>" + props + "</w:rPr>" if props else ""}<w:t xml:space="preserve">{escape(piece)}</w:t></w:r>')
    return ''.join(out)


def _paragraph(text: str, style: Optional[str] = None, hanging: int = 0, left: int = 0, italic: bool = False, lead: str = '') -> str:
    """Párrafo. `lead` es el marcador de una lista («•», «1.») que va delante, con sangría francesa."""
    ppr = f'<w:pStyle w:val="{style}"/>' if style else ''
    if hanging:
        ppr += f'<w:tabs><w:tab w:val="num" w:pos="{left}"/></w:tabs><w:ind w:left="{left}" w:hanging="{hanging}"/>'
    runs = (f'<w:r><w:t xml:space="preserve">{escape(lead)}</w:t></w:r><w:r><w:tab/></w:r>' if lead else '') + _runs(text, italic)
    return f'<w:p>{"<w:pPr>" + ppr + "</w:pPr>" if ppr else ""}{runs}</w:p>'


def build_docx(markdown_text: str, title: str = '') -> bytes:
    """
    .docx sencillo desde Markdown básico: `# ## ###` (títulos reales de Word, con navegación), `-`/`*`/`1.` (listas),
    `>` (cita), `**negrita**`, `*cursiva*`, `` `código` `` y párrafos. Suficiente para una plantilla o un borrador.
    """
    # Bloques como Markdown: las líneas seguidas de un mismo párrafo (o cita, o elemento de lista) forman UN párrafo
    blocks: List[dict] = []
    current: Optional[dict] = None

    def flush():
        nonlocal current
        if current:
            blocks.append(current)
        current = None

    for raw in _CTRL_RE.sub('', markdown_text or '').splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        m = re.match(r'^(#{1,3})\s+(.*)$', line)
        if m:
            flush()
            blocks.append({'kind': 'heading', 'level': len(m.group(1)), 'text': m.group(2).strip()})
            continue
        m = re.match(r'^(\s*)[-*•]\s+(.*)$', line)
        if m:
            flush()
            current = {'kind': 'bullet', 'level': min(len(m.group(1)) // 2, 4), 'text': m.group(2).strip()}
            continue
        m = re.match(r'^(\s*)(\d+)[.)]\s+(.*)$', line)
        if m:
            flush()
            current = {'kind': 'number', 'level': min(len(m.group(1)) // 2, 4), 'n': m.group(2), 'text': m.group(3).strip()}
            continue
        m = re.match(r'^>\s?(.*)$', line)
        if m:
            inner = m.group(1).strip()
            if not inner:                                   # «>» solo: separa párrafos dentro de la cita
                flush()
            elif current and current['kind'] == 'quote':
                current['text'] += ' ' + inner
            else:
                flush()
                current = {'kind': 'quote', 'text': inner}
            continue
        if re.match(r'^[-_*]{3,}$', line.strip()):
            flush()
            continue
        if current and current['kind'] in ('para', 'bullet', 'number'):     # continuación de la línea anterior
            current['text'] += ' ' + line.strip()
        else:
            flush()
            current = {'kind': 'para', 'text': line.strip()}
    flush()

    body: List[str] = []
    for b in blocks:
        if b['kind'] == 'heading':
            body.append(_paragraph(b['text'], f"Heading{b['level']}"))
        elif b['kind'] == 'bullet':
            body.append(_paragraph(b['text'], hanging=360, left=720 + b['level'] * 360, lead='•'))
        elif b['kind'] == 'number':
            body.append(_paragraph(b['text'], hanging=360, left=720 + b['level'] * 360, lead=f"{b['n']}."))
        elif b['kind'] == 'quote':
            if b['text']:
                body.append(_paragraph(b['text'], 'Quote'))
        else:
            body.append(_paragraph(b['text']))
    if title:
        body.insert(0, _paragraph(title, 'Heading1'))

    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document xmlns:w="{W}"><w:body>' + ''.join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
                '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', _CONTENT_TYPES)
        zf.writestr('_rels/.rels', _RELS)
        zf.writestr('word/document.xml', document)
        zf.writestr('word/styles.xml', _STYLES)
        zf.writestr('word/_rels/document.xml.rels', _DOC_RELS)
    return buf.getvalue()
