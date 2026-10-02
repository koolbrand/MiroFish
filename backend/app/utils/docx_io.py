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

# Identidad de Simuloo (brandbook de Koolbrand): tinta, lima y su versión suave, y las dos tipografías. El bloque lima
# detrás del texto es la firma de la marca; en Word es el sombreado de carácter.
_INK, _INK2, _MUTED, _LINE = '111111', '2A2A2A', '6E6E6E', 'DDDDDD'
_LIME, _LIME_SOFT = 'CCE673', 'F0F8D5'
_SANS, _MONO = 'Inter Tight', 'JetBrains Mono'
_TEXT_WIDTH = 9072                        # A4 (11906) menos 1417 de margen a cada lado, en veinteavos de punto
_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

_LABELS = {
    'es': {'template': 'Plantilla de brief', 'draft': 'Borrador de brief', 'lang': 'es-ES',
           'tagline': 'Simuloo · Simulación de opinión pública con IA', 'page': ('Página ', ' de ', '')},
    'en': {'template': 'Brief template', 'draft': 'Brief draft', 'lang': 'en-GB',
           'tagline': 'Simuloo · AI public opinion simulation', 'page': ('Page ', ' of ', '')},
    'zh': {'template': '简报模板', 'draft': '简报草稿', 'lang': 'zh-CN',
           'tagline': 'Simuloo · AI 舆论模拟', 'page': ('第 ', ' 页，共 ', ' 页')},
}

_CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/>'
                  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                  '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                  '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'
                  '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
                  '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                  '</Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
         '</Relationships>')
_DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             f'<Relationship Id="rId1" Type="{_R}/styles" Target="styles.xml"/>'
             f'<Relationship Id="rId2" Type="{_R}/header" Target="header1.xml"/>'
             f'<Relationship Id="rId3" Type="{_R}/footer" Target="footer1.xml"/>'
             f'<Relationship Id="rId4" Type="{_R}/fontTable" Target="fontTable.xml"/>'
             '</Relationships>')

# Si el equipo que abre el documento no tiene las tipografías de la marca, Word usa estas en su lugar.
_FONT_TABLE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               f'<w:fonts xmlns:w="{W}">'
               f'<w:font w:name="{_SANS}"><w:altName w:val="Arial"/><w:charset w:val="00"/><w:family w:val="swiss"/><w:pitch w:val="variable"/></w:font>'
               f'<w:font w:name="{_MONO}"><w:altName w:val="Consolas"/><w:charset w:val="00"/><w:family w:val="modern"/><w:pitch w:val="fixed"/></w:font>'
               '</w:fonts>')


def _rpr(font: str = '', bold: bool = False, italic: bool = False, caps: bool = False, color: str = '',
         spacing: int = 0, size: int = 0, shade: str = '') -> str:
    """Propiedades de texto. El esquema de Word fija el orden: rFonts, b, i, caps, color, spacing, sz, shd."""
    return ((f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>' if font else '')
            + ('<w:b/>' if bold else '') + ('<w:i/>' if italic else '') + ('<w:caps/>' if caps else '')
            + (f'<w:color w:val="{color}"/>' if color else '') + (f'<w:spacing w:val="{spacing}"/>' if spacing else '')
            + (f'<w:sz w:val="{size}"/>' if size else '')
            + (f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ''))


def _style_xml(style_id: str, name: str, ppr: str, rpr: str) -> str:
    return (f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
            f'<w:next w:val="Normal"/><w:qFormat/><w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')


def _styles_xml(lang: str) -> str:
    # En pPr el orden es: keepNext, pBdr, shd, spacing, ind, outlineLvl
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:styles xmlns:w="{W}">'
            '<w:docDefaults><w:rPrDefault><w:rPr>'
            f'<w:rFonts w:ascii="{_SANS}" w:hAnsi="{_SANS}" w:eastAsia="Microsoft YaHei" w:cs="{_SANS}"/>'
            f'<w:color w:val="{_INK2}"/><w:sz w:val="21"/><w:lang w:val="{lang}" w:eastAsia="zh-CN"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            # Título: texto ink sobre el bloque lima de la marca
            + _style_xml('Heading1', 'heading 1',
                         '<w:keepNext/><w:spacing w:before="0" w:after="200"/><w:outlineLvl w:val="0"/>',
                         _rpr(_SANS, bold=True, color=_INK, size=44, shade=_LIME))
            # Sección: título con filete fino debajo
            + _style_xml('Heading2', 'heading 2',
                         f'<w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="4" w:color="{_LINE}"/></w:pBdr>'
                         '<w:spacing w:before="280" w:after="100"/><w:outlineLvl w:val="1"/>',
                         _rpr(_SANS, bold=True, color=_INK, size=30))
            # Subtítulo: etiqueta en mayúsculas con la mono de la marca
            + _style_xml('Heading3', 'heading 3',
                         '<w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="2"/>',
                         _rpr(_MONO, caps=True, color=_MUTED, spacing=20, size=18))
            # Cita = nota destacada: barra lima y fondo lima suave
            + _style_xml('Quote', 'Quote',
                         f'<w:pBdr><w:left w:val="single" w:sz="36" w:space="10" w:color="{_LIME}"/></w:pBdr>'
                         f'<w:shd w:val="clear" w:color="auto" w:fill="{_LIME_SOFT}"/>'
                         '<w:spacing w:before="60" w:after="60"/><w:ind w:left="340" w:right="113"/>',
                         _rpr(color=_INK2))
            + '</w:styles>')


def _small_run(text: str, mono: bool = True) -> str:
    return (f'<w:r><w:rPr>{_rpr(_MONO if mono else _SANS, caps=mono, color=_MUTED, spacing=20 if mono else 0, size=16)}</w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')


def _field(instr: str, rpr: str) -> str:
    """Campo de Word (número de página, total de páginas). El «1» es el valor guardado; Word lo recalcula al maquetar."""
    return (f'<w:r><w:rPr>{rpr}</w:rPr><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:t>1</w:t></w:r>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:fldChar w:fldCharType="end"/></w:r>')


def _header_xml(label: str) -> str:
    """Cabecera: la marca (simul + «oo» sobre el bloque lima) a la izquierda y el tipo de documento a la derecha."""
    word = _rpr(_SANS, bold=True, color=_INK, size=32)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:hdr xmlns:w="{W}" xmlns:r="{_R}"><w:p><w:pPr>'
            f'<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="6" w:color="{_LINE}"/></w:pBdr>'
            f'<w:tabs><w:tab w:val="right" w:pos="{_TEXT_WIDTH}"/></w:tabs><w:spacing w:after="0"/></w:pPr>'
            f'<w:r><w:rPr>{word}</w:rPr><w:t>simul</w:t></w:r>'
            f'<w:r><w:rPr>{_rpr(_SANS, bold=True, color=_INK, size=32, shade=_LIME)}</w:rPr><w:t>oo</w:t></w:r>'
            '<w:r><w:tab/></w:r>' + _small_run(label) + '</w:p></w:hdr>')


def _footer_xml(tagline: str, page: tuple) -> str:
    """Pie: la frase de la marca a la izquierda y «Página X de Y» a la derecha."""
    rpr = _rpr(_MONO, caps=True, color=_MUTED, spacing=20, size=16)
    before, between, after = page
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:ftr xmlns:w="{W}" xmlns:r="{_R}"><w:p><w:pPr>'
            f'<w:pBdr><w:top w:val="single" w:sz="4" w:space="6" w:color="{_LINE}"/></w:pBdr>'
            f'<w:tabs><w:tab w:val="right" w:pos="{_TEXT_WIDTH}"/></w:tabs><w:spacing w:after="0"/></w:pPr>'
            + _small_run(tagline) + '<w:r><w:tab/></w:r>'
            + (_small_run(before) if before else '') + _field('PAGE', rpr)
            + _small_run(between) + _field('NUMPAGES', rpr) + (_small_run(after) if after else '')
            + '</w:p></w:ftr>')


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


def build_docx(markdown_text: str, title: str = '', *, locale: str = 'es', kind: str = 'draft') -> bytes:
    """
    .docx sencillo desde Markdown básico: `# ## ###` (títulos reales de Word, con navegación), `-`/`*`/`1.` (listas),
    `>` (cita), `**negrita**`, `*cursiva*`, `` `código` `` y párrafos. Suficiente para una plantilla o un borrador.
    Lleva la identidad de Simuloo: estilos, cabecera con la marca y pie con el número de página. `kind` es
    `template` o `draft` (rotula la cabecera) y `locale` es es, en o zh (rotula cabecera y pie).
    """
    labels = _LABELS.get(locale) or _LABELS['es']
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
                f'<w:document xmlns:w="{W}" xmlns:r="{_R}"><w:body>' + ''.join(body) +
                '<w:sectPr><w:headerReference w:type="default" r:id="rId2"/><w:footerReference w:type="default" r:id="rId3"/>'
                '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1304" w:right="1417" w:bottom="1247" w:left="1417" w:header="624" w:footer="567" w:gutter="0"/></w:sectPr>'
                '</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', _CONTENT_TYPES)
        zf.writestr('_rels/.rels', _RELS)
        zf.writestr('word/document.xml', document)
        zf.writestr('word/styles.xml', _styles_xml(labels['lang']))
        zf.writestr('word/fontTable.xml', _FONT_TABLE)
        zf.writestr('word/header1.xml', _header_xml(labels['template' if kind == 'template' else 'draft']))
        zf.writestr('word/footer1.xml', _footer_xml(labels['tagline'], labels['page']))
        zf.writestr('word/_rels/document.xml.rels', _DOC_RELS)
    return buf.getvalue()
