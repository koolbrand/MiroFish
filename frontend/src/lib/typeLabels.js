// Nombres legibles para los tipos de la ontología (entidades, relaciones, atributos).
//
// El motor trabaja con identificadores en inglés (`SmallBusinessOwner`, `WORKS_FOR`, `years_in_business`).
// Aquí se muestran en el idioma de la interfaz: «Dueño de pequeño negocio», «trabaja para». Solo para
// mostrar; el identificador no cambia en ningún sitio (búsquedas, colores y datos usan el original).
//
// Uso: `typeLabel(name, 'entity' | 'relation' | 'attribute')`, en plantillas o en código. Es reactivo:
// devuelve al instante el identificador separado en palabras y, en cuanto el servidor trae la traducción
// (un diccionario compartido por todos los proyectos), la plantilla se repinta sola. No hace falta pasar
// ningún id de proyecto ni cargar nada antes.
import { reactive, ref } from 'vue'
import i18n from '../i18n'
import service from '../api'

const KINDS = ['entity', 'relation', 'attribute']
// Idiomas que el servidor traduce. En el resto (inglés) basta con separar el identificador en palabras.
const TRANSLATED = new Set(['es', 'zh'])
const BATCH_MS = 150
const RETRY_MS = 60000
const MAX_PER_REQUEST = 80

const labels = reactive({})            // `${locale}|${kind}|${name}` → etiqueta
const asked = new Map()                // misma clave → cuándo se pidió (no se vuelve a pedir en RETRY_MS)
let queue = { locale: null, entity: new Set(), relation: new Set(), attribute: new Set() }
let timer = null

// Sube cada vez que llega algo nuevo: para lo que no es una plantilla (el lienzo del grafo) y debe repintarse
export const typeLabelsVersion = ref(0)

const key = (locale, kind, name) => `${locale}|${kind}|${name}`

// «SmallBusinessOwner» → «Small business owner» · «WORKS_FOR» → «works for» · «years_in_business» → «years in business»
export function humanizeType(name, kind = 'entity') {
  if (!name) return ''
  const words = String(name)
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
  return kind === 'entity' ? words.charAt(0).toUpperCase() + words.slice(1) : words
}

const currentLocale = () => i18n.global.locale.value

async function flush() {
  timer = null
  const q = queue
  queue = { locale: null, entity: new Set(), relation: new Set(), attribute: new Set() }
  const body = { locale: q.locale }
  let total = 0
  for (const kind of KINDS) {
    body[kind] = [...q[kind]].slice(0, Math.max(0, MAX_PER_REQUEST - total))
    total += body[kind].length
  }
  if (!total) return
  try {
    const res = await service.post('/api/graph/type-labels', body)
    const got = res?.data?.labels || {}
    let any = false
    for (const kind of KINDS) {
      for (const [name, label] of Object.entries(got[kind] || {})) {
        if (typeof label === 'string' && label) { labels[key(q.locale, kind, name)] = label; any = true }
      }
    }
    if (any) typeLabelsVersion.value++
  } catch (_) {
    // de mejor esfuerzo: se sigue viendo el identificador en palabras y se reintenta pasado un rato
  }
}

function want(locale, kind, name) {
  const k = key(locale, kind, name)
  const at = asked.get(k)
  if (at && Date.now() - at < RETRY_MS) return
  asked.set(k, Date.now())
  if (queue.locale && queue.locale !== locale) { clearTimeout(timer); flush() }   // cambió el idioma a medias
  queue.locale = locale
  queue[kind].add(name)
  if (!timer) timer = setTimeout(flush, BATCH_MS)
}

// Un identificador del motor: sin espacios ni acentos. Lo demás ya es texto escrito para personas (el grafo
// también trae relaciones en prosa, «busca atraer») y se deja tal cual.
const IDENTIFIER = /^[A-Za-z][A-Za-z0-9_]*$/

export function typeLabel(name, kind = 'entity') {
  if (!name) return ''
  if (!IDENTIFIER.test(String(name))) return String(name)
  const locale = currentLocale()
  if (!TRANSLATED.has(locale)) return humanizeType(name, kind)
  const known = labels[key(locale, kind, name)]
  if (known) return known
  want(locale, kind, name)
  return humanizeType(name, kind)
}

export const entityLabel = (name) => typeLabel(name, 'entity')
export const relationLabel = (name) => typeLabel(name, 'relation')
export const attributeLabel = (name) => typeLabel(name, 'attribute')
