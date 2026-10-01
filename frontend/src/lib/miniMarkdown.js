// Markdown mínimo y SEGURO para lo que escriben las personas simuladas y el modelo (posts, comentarios, chat, encuestas).
// No genera HTML: parte el texto en bloques y trozos y los pinta con h(), así que cualquier «<script>» se ve como texto.
// Bloques: párrafos (un salto de línea = <br>), listas con - * • y 1. 1), citas con >, títulos #, --- y ``` código ```.
// En línea: **negrita**, __negrita__, *cursiva*, _cursiva_ (solo entre separadores: snake_case no se toca) y `código`.
// Lo que no cierra («**sin pareja») se queda tal cual.
import { defineComponent, h, computed } from 'vue'

// ---------- en línea ----------
// Orden: código, negrita+cursiva, negrita, cursiva. Sin lookbehind (Safari < 16.4 rompe al cargar el módulo).
const INLINE = /(`)([^`\n]+?)`|(\*\*\*)([^\s*](?:[^\n]*?[^\s*])?)\*\*\*|(\*\*|__)([^\s](?:[^\n]*?[^\s])?)\5|(\*)([^\s*](?:[^*\n]*?[^\s*])?)\*|(^|[^\p{L}\p{N}_])(_)([^\s_](?:[^_\n]*?[^\s_])?)_(?![\p{L}\p{N}_])/gu

export function parseInline (text) {
  const out = []
  const s = String(text ?? '')
  const re = new RegExp(INLINE.source, 'gu')   // una por llamada: la recursión no puede pisar lastIndex
  let last = 0
  for (let m; (m = re.exec(s));) {
    let start = m.index
    const end = m.index + m[0].length
    if (m[10] !== undefined) start += m[9].length   // «_cursiva_»: lo de antes del guion bajo es texto
    if (start > last) out.push({ t: 'text', v: s.slice(last, start) })
    if (m[1]) out.push({ t: 'code', v: m[2] })
    else if (m[3]) out.push({ t: 'strong', c: [{ t: 'em', c: parseInline(m[4]) }] })
    else if (m[5]) out.push({ t: 'strong', c: parseInline(m[6]) })
    else if (m[7]) out.push({ t: 'em', c: parseInline(m[8]) })
    else out.push({ t: 'em', c: parseInline(m[11]) })
    last = end
  }
  if (last < s.length) out.push({ t: 'text', v: s.slice(last) })
  return out
}

// ---------- bloques ----------
const RE_FENCE = /^\s*```/
const RE_HEAD = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/
const RE_HR = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const RE_QUOTE = /^\s{0,3}>\s?(.*)$/
const RE_UL = /^(\s*)[-*•+]\s+(.*)$/
const RE_OL = /^(\s*)(\d{1,3})[.)]\s+(.*)$/

export function parseBlocks (text, { stripLeadingHeading = false } = {}) {
  let src = String(text ?? '').replace(/\r\n?/g, '\n')
  if (stripLeadingHeading) src = src.replace(/^##\s+.+\n+/, '')   // el «## Título» de la sección ya está pintado fuera (igual que antes)
  const lines = src.split('\n')
  const blocks = []
  let para = null, list = null, quote = null
  const cerrar = () => { para = null; list = null; quote = null }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (RE_FENCE.test(line)) {   // ``` … ```
      cerrar()
      const body = []
      for (i++; i < lines.length && !RE_FENCE.test(lines[i]); i++) body.push(lines[i])
      blocks.push({ type: 'code', v: body.join('\n') })
      continue
    }
    if (!line.trim()) { cerrar(); continue }
    let m
    if (RE_HR.test(line)) { cerrar(); blocks.push({ type: 'hr' }); continue }
    if ((m = RE_HEAD.exec(line))) { cerrar(); blocks.push({ type: 'h', level: m[1].length, c: parseInline(m[2]) }); continue }
    if ((m = RE_QUOTE.exec(line))) {
      if (!quote) { cerrar(); quote = { type: 'quote', lines: [] }; blocks.push(quote) }
      quote.lines.push(parseInline(m[1]))
      continue
    }
    const ul = RE_UL.exec(line), ol = !ul && RE_OL.exec(line)
    if (ul || ol) {
      const kind = ul ? 'ul' : 'ol'
      if (!list || list.type !== kind) {
        para = null; quote = null
        list = { type: kind, start: ol ? +ol[2] : 1, items: [] }
        blocks.push(list)
      }
      list.items.push({ level: Math.min(3, Math.floor(((ul || ol)[1] || '').replace(/\t/g, '  ').length / 2)), c: parseInline(ul ? ul[2] : ol[3]) })
      continue
    }
    if (list && /^\s{2,}\S/.test(line)) {   // continuación de un punto de lista
      const it = list.items[list.items.length - 1]
      it.c.push({ t: 'br' }, ...parseInline(line.trim()))
      continue
    }
    if (quote) { quote.lines.push(parseInline(line.trim())); continue }
    if (!para) { list = null; para = { type: 'p', lines: [] }; blocks.push(para) }
    para.lines.push(parseInline(line))
  }
  return blocks
}

// Texto plano, sin marcas (para recortes «…» y búsquedas): recortar antes de quitar las marcas dejaría «**» sueltos.
export function stripMarkdown (text) {
  return String(text ?? '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/^\s{0,3}([-*_])(\s*\1){2,}\s*$/gm, '')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s{0,3}>\s?/gm, '')
    .replace(/^\s*[-*•+]\s+/gm, '• ')
    .replace(/(\*\*\*|\*\*|__)(\S(?:.*?\S)?)\1/g, '$2')
    .replace(/(^|[^*\w])\*(\S(?:[^*\n]*?\S)?)\*/g, '$1$2')
    .replace(/(^|[^\p{L}\p{N}_])_(\S(?:[^_\n]*?\S)?)_(?![\p{L}\p{N}_])/gu, '$1$2')
    .replace(/`([^`\n]+)`/g, '$1')
}

// ---------- pintado ----------
const pintarInline = (nodos) => nodos.map(n => {
  if (n.t === 'text') return n.v
  if (n.t === 'br') return h('br')
  if (n.t === 'code') return h('code', { class: 'inline-code' }, n.v)
  return h(n.t, pintarInline(n.c))
})
const conSaltos = (lineas) => lineas.flatMap((l, i) => (i ? [h('br'), ...pintarInline(l)] : pintarInline(l)))

const pintarLista = (b) => {
  const attrs = { class: b.type === 'ul' ? 'md-ul' : 'md-ol' }
  if (b.type === 'ol' && b.start !== 1) attrs.start = b.start
  return h(b.type, attrs, b.items.map(it => h('li', { class: b.type === 'ul' ? 'md-li' : 'md-oli', 'data-level': it.level || undefined }, pintarInline(it.c))))
}

/**
 * <MiniMarkdown :text="..." />
 *   inline        — una sola línea de trozos en un <span> (para textos que se recortan con line-clamp)
 *   headings      — «#» como títulos de verdad (h2–h5); por defecto, párrafo en negrita (un post no mete títulos en el esquema de la página)
 *   strip-leading-heading — quita un «## Título» inicial que ya se pinta fuera
 */
export const MiniMarkdown = defineComponent({
  name: 'MiniMarkdown',
  props: {
    text: { type: [String, Number], default: '' },
    inline: { type: Boolean, default: false },
    headings: { type: Boolean, default: false },
    stripLeadingHeading: { type: Boolean, default: false },
    tag: { type: String, default: null },
  },
  setup (props) {
    const blocks = computed(() => (props.inline ? null : parseBlocks(props.text, { stripLeadingHeading: props.stripLeadingHeading })))
    // en una línea, las marcas de bloque (#, >, viñetas, ```) sobran: se quitan y los saltos pasan a espacios
    const inl = computed(() => (props.inline ? parseInline(String(props.text ?? '')
      .replace(/```/g, '').replace(/^\s{0,3}#{1,6}\s+/gm, '').replace(/^\s{0,3}>\s?/gm, '')
      .replace(/^\s*[-*•+]\s+/gm, '• ').replace(/\s*\n\s*/g, ' ')) : null))
    return () => {
      if (props.inline) return h(props.tag || 'span', { class: 'mini-md' }, pintarInline(inl.value))
      return h(props.tag || 'div', { class: 'mini-md' }, blocks.value.map(b => {
        switch (b.type) {
          case 'p': return h('p', { class: 'md-p' }, conSaltos(b.lines))
          case 'ul': case 'ol': return pintarLista(b)
          case 'quote': return h('blockquote', { class: 'md-quote' }, conSaltos(b.lines))
          case 'hr': return h('hr', { class: 'md-hr' })
          case 'code': return h('pre', { class: 'code-block' }, h('code', b.v))
          case 'h': {
            if (!props.headings) return h('p', { class: 'md-p md-heading' }, h('strong', pintarInline(b.c)))
            const lvl = Math.min(5, b.level + 1)   // «#» → h2 … «####» → h5 (el h1 es el de la página)
            return h('h' + lvl, { class: 'md-h' + lvl }, pintarInline(b.c))
          }
          default: return null
        }
      }))
    }
  },
})

export default MiniMarkdown
