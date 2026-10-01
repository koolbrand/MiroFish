// El razonamiento con el que el modelo configuró la simulación llega como UN bloque de texto por apartado
// («Configuración de tiempo: …» | «Configuración de eventos: …»). Se pintaba tal cual: cien caracteres por línea y
// un muro de texto. Aquí se parte en título + párrafos de 2–3 frases, y las enumeraciones «(1) … ; (2) …» pasan
// a lista. Todo se devuelve como DATOS (nunca HTML): el texto lo escribe un modelo y no debe interpretarse.

// Abreviaturas cuyo punto no cierra una frase
const ABBREVIATIONS = ['p. ej.', 'p.ej.', 'etc.', 'aprox.', 'núm.', 'vs.', 'sr.', 'sra.', 'dr.', 'dra.', 'ee. uu.', 'ej.', 'pág.']
const SENTENCE_END = /[.!?…]/
const STARTS_SENTENCE = /[A-ZÁÉÍÓÚÜÑ¿¡"“«(\d]/
const MAX_PARAGRAPH_CHARS = 360
const MAX_SENTENCES_PER_PARAGRAPH = 3

// Frases de un texto. Sin lookbehind (Safari < 16.4 no lo entiende y rompería todo el bundle).
export function splitSentences(text) {
  const src = String(text || '').replace(/\s+/g, ' ').trim()
  if (!src) return []
  const out = []
  let start = 0
  for (let i = 0; i < src.length - 1; i++) {
    if (!SENTENCE_END.test(src[i]) || src[i + 1] !== ' ') continue
    const next = src[i + 2]
    if (!next || !STARTS_SENTENCE.test(next)) continue
    const head = src.slice(start, i + 1).toLowerCase()
    if (ABBREVIATIONS.some(a => head.endsWith(a))) continue
    // «… 1.500 vecinos»: el punto de un número no cierra la frase (aquí ya hay un espacio detrás, así que no es el caso)
    out.push(src.slice(start, i + 1).trim())
    start = i + 2
  }
  out.push(src.slice(start).trim())
  return out.filter(Boolean)
}

// «… combina dos perfiles: (1) vecinos…; (2) oficinistas…» → { intro, items }. null si no es una enumeración.
export function asList(sentence) {
  const first = sentence.indexOf('(1)')
  if (first < 0 || !/\(2\)/.test(sentence)) return null
  const intro = sentence.slice(0, first).trim().replace(/[:：]$/, '')
  const parts = sentence.slice(first).split(/\(\d{1,2}\)\s*/).map(s => s.trim().replace(/[;,]\s*(y|e)?$/i, '').replace(/[;]$/, '')).filter(Boolean)
  if (parts.length < 2) return null
  return { intro, items: parts }
}

// Frases → bloques: { type: 'p', text } o { type: 'list', intro, items }
export function toBlocks(body) {
  const blocks = []
  let current = []
  const flush = () => { if (current.length) blocks.push({ type: 'p', text: current.join(' ') }); current = [] }
  for (const sentence of splitSentences(body)) {
    const list = asList(sentence)
    if (list) {
      if (list.intro) current.push(list.intro + ':')
      flush()
      blocks.push({ type: 'list', items: list.items })
      continue
    }
    const joined = [...current, sentence].join(' ')
    if (current.length && (current.length >= MAX_SENTENCES_PER_PARAGRAPH || joined.length > MAX_PARAGRAPH_CHARS)) flush()
    current.push(sentence)
  }
  flush()
  return blocks
}

// Un apartado completo: «Configuración de tiempo: Simulación…» → { label: 'Configuración de tiempo', blocks: [...] }
export function parseReasoning(part) {
  const text = String(part || '').replace(/\s+/g, ' ').trim()
  const m = text.match(/^([^:：]{3,48})[:：]\s+(.+)$/)
  const label = m ? m[1].trim() : ''
  return { label, blocks: toBlocks(m ? m[2] : text) }
}

// Los apartados de `generation_reasoning` (unidos con « | ») que se enseñan: los dos del modelo (tiempo y eventos)
export function reasoningSections(reasoning, max = 2) {
  return String(reasoning || '').split('|').slice(0, max).map(parseReasoning).filter(s => s.blocks.length)
}
