// Motor del grafo de Simuloo: el panel de relaciones de las cinco pantallas del proceso.
//
// · Canvas 2D (no SVG): con 1.500 nodos el DOM no aguanta 60 fps; el canvas sí.
// · Layout con d3-force, pero los ticks los da este bucle (no el temporizador de d3): así, al pausar el bucle
//   (panel fuera de pantalla o pestaña oculta) también se para el cálculo del layout.
// · Tres capas en caché: fondo + aristas, nodos, y etiquetas. Solo se repintan cuando algo cambia (tick,
//   zoom, foco…). Lo que se mueve siempre se pinta en cada fotograma ENTRE los nodos y las etiquetas:
//   flujo de partículas por cada relación, cometas con reacción en cadena, latido de los nodos principales,
//   destellos y un barrido tipo sonar. Por delante de los nodos (antes iba por detrás y los tapaban) y por
//   detrás del texto (que nunca queda bajo una chispa). Anillo de selección y ondas, encima de todo.
// · Todo se dibuja en coordenadas de PANTALLA: texto y trazos tienen el mismo tamaño a cualquier zoom.
// · Colores: solo los tokens de koolbrand.css, leídos en tiempo de ejecución (las reservas son los mismos valores).

import {
  forceSimulation, forceLink, forceManyBody, forceCollide, forceX, forceY,
  zoom as d3zoom, zoomIdentity, drag as d3drag, select, interpolateZoom,
} from 'd3'

// ── Tokens de marca ───────────────────────────────────────────────────────────
export const TOKEN_FALLBACK = {
  '--lime-50': '#EFF8D8',
  '--lime-500': '#CCE673',
  '--lime-600': '#ACC451',
  '--lime-700': '#94AA3D',
  '--lime-800': '#5C6C16',
  '--ink-950': '#111111',
  '--ink-800': '#2A2A2A',
  '--gray-600': '#6E6E6E',
  '--gray-500': '#8A8A8A',
  '--gray-400': '#858585',
  '--gray-300': '#CFCFCF',
  '--gray-200': '#DDDDDD',
  '--gray-100': '#ECECEC',
  '--cream-100': '#F2F1EF',
  '--cream-50': '#F7F6F3',
  '--kb-surface': '#FFFFFF',
}

export function readTokens() {
  const cs = typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : null
  const out = {}
  for (const [k, v] of Object.entries(TOKEN_FALLBACK)) {
    const got = cs ? cs.getPropertyValue(k).trim() : ''
    out[k] = /^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(got) ? got : v
  }
  return out
}

const rgbCache = new Map()
const rgbOf = (hex) => {
  let v = rgbCache.get(hex)
  if (v) return v
  let h = hex.replace('#', '')
  if (h.length === 3) h = h.split('').map(c => c + c).join('')
  v = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
  rgbCache.set(hex, v)
  return v
}
export const rgba = (hex, a) => {
  const [r, g, b] = rgbOf(hex)
  return `rgba(${r},${g},${b},${a <= 0 ? 0 : a >= 1 ? 1 : Math.round(a * 1000) / 1000})`
}

// ── Formas y estilos por tipo de entidad ─────────────────────────────────────
// Trazados unitarios (radio ≈ 1) en sintaxis SVG: el canvas los usa con Path2D y la leyenda con <path>,
// así la muestra de la leyenda es exactamente la forma del grafo. Rombo y triángulo pasan de 1 para
// compensar su menor área (a igual radio parecerían más pequeños).
export const SHAPES = {
  circle: 'M1 0A1 1 0 1 1 -1 0A1 1 0 1 1 1 0Z',
  square: 'M-0.56 -0.86H0.56A0.3 0.3 0 0 1 0.86 -0.56V0.56A0.3 0.3 0 0 1 0.56 0.86H-0.56A0.3 0.3 0 0 1 -0.86 0.56V-0.56A0.3 0.3 0 0 1 -0.56 -0.86Z',
  diamond: 'M0 -1.24L1.24 0L0 1.24L-1.24 0Z',
  hexagon: 'M0 -1.1L0.953 -0.55L0.953 0.55L0 1.1L-0.953 0.55L-0.953 -0.55Z',
  triangle: 'M0 -1.32L1.143 0.66L-1.143 0.66Z',
}

// La marca no tiene azules, rosas ni violetas: los tipos se distinguen por FORMA y por LUMINOSIDAD dentro de
// la paleta (lima 500–700, crema, blanco, grises y tinta con borde). Orden pensado para que dos tipos
// seguidos nunca compartan forma ni tono.
export const TYPE_STYLES = [
  { shape: 'circle', fill: '--lime-500' },
  { shape: 'square', fill: '--cream-100' },
  { shape: 'diamond', fill: '--lime-700' },
  { shape: 'hexagon', fill: '--ink-950', stroke: '--lime-500' },
  { shape: 'triangle', fill: '--lime-600' },
  { shape: 'circle', fill: '--ink-950', stroke: '--cream-100' },
  { shape: 'square', fill: '--gray-500' },
  { shape: 'diamond', fill: '--ink-950', stroke: '--lime-600' },
  { shape: 'hexagon', fill: '--kb-surface' },
]
export const OTHER_KEY = '__other__'
export const OTHER_STYLE = { shape: 'circle', fill: '--gray-600', other: true }
export const styleColorToken = (s) => s.stroke || s.fill

// «LESS_PROFITABLE_THAN» → «less profitable than». Sin recortar: la etiqueta se parte en líneas si hace falta.
export const humanizeRelation = (raw) => {
  if (!raw) return ''
  const s = String(raw).replace(/_/g, ' ').replace(/\s+/g, ' ').trim()
  return /[a-z]/.test(s) ? s : s.toLowerCase()
}

const fnv = (str) => {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) }
  return h >>> 0
}

// ── Modelo: de la respuesta de /api/graph/data a nodos y aristas listos para pintar ──────────────────
// `styleMemory` (Map tipo → índice de estilo, -1 = «otros») vive en el componente: un tipo conserva su
// forma y su tono entre refrescos aunque cambien las frecuencias.
export function buildGraphModel(graphData, styleMemory = new Map()) {
  const rawNodes = Array.isArray(graphData?.nodes) ? graphData.nodes : []
  const rawEdges = Array.isArray(graphData?.edges) ? graphData.edges : []
  const nodes = []
  const nodeById = new Map()
  for (const n of rawNodes) {
    if (!n || n.uuid == null || nodeById.has(n.uuid)) continue
    const type = (n.labels || []).find(l => l !== 'Entity') || 'Entity'
    const node = { id: n.uuid, name: String(n.name || '').trim() || '—', type, raw: n, degree: 0, nbr: new Set(), links: [], selfLoops: 0 }
    nodes.push(node)
    nodeById.set(node.id, node)
  }

  const valid = rawEdges.filter(e => e && nodeById.has(e.source_node_uuid) && nodeById.has(e.target_node_uuid))
  const pairKey = (a, b) => (a < b ? `${a}|${b}` : `${b}|${a}`)
  const pairCount = new Map()
  const selfGroups = new Map()
  for (const e of valid) {
    const s = e.source_node_uuid, t = e.target_node_uuid
    if (s === t) {
      if (!selfGroups.has(s)) selfGroups.set(s, [])
      selfGroups.get(s).push(e)
    } else {
      const k = pairKey(s, t)
      pairCount.set(k, (pairCount.get(k) || 0) + 1)
    }
  }

  const edges = []
  const edgeById = new Map()
  const pairIdx = new Map()
  let relationCount = 0
  for (const e of valid) {
    const s = e.source_node_uuid, t = e.target_node_uuid
    const sN = nodeById.get(s), tN = nodeById.get(t)
    if (s === t) {
      const id = `self:${s}`
      if (edgeById.has(id)) continue
      const all = selfGroups.get(s).map(x => ({ ...x, source_name: sN.name, target_name: sN.name }))
      const edge = {
        id, sid: s, tid: s, self: true, name: '', count: all.length,
        raw: { isSelfLoopGroup: true, source_name: sN.name, target_name: sN.name, selfLoopCount: all.length, selfLoopEdges: all },
      }
      sN.selfLoops = all.length
      sN.links.push(edge)
      relationCount += all.length
      edges.push(edge)
      edgeById.set(id, edge)
      continue
    }
    const k = pairKey(s, t)
    const total = pairCount.get(k)
    const idx = pairIdx.get(k) || 0
    pairIdx.set(k, idx + 1)
    // una curva suave incluso con una sola arista (las rectas se ven a plantilla); varias entre el mismo par
    // se abren en abanico, con el signo referido al par ordenado para que no se pisen.
    let curv = 0.12
    if (total > 1) {
      const range = Math.min(1.1, 0.5 + total * 0.12)
      curv = (idx / (total - 1) - 0.5) * range
      if (s > t) curv = -curv
    }
    let id = e.uuid || `e:${s}:${t}:${idx}`
    if (edgeById.has(id)) id = `${id}#${idx}`
    const edge = {
      id, sid: s, tid: t, source: s, target: t, self: false, name: e.name || e.fact_type || 'RELATED', curv, pairTotal: total,
      raw: { ...e, source_name: sN.name, target_name: tN.name },
    }
    sN.degree++; tN.degree++
    sN.nbr.add(t); tN.nbr.add(s)
    sN.links.push(edge); tN.links.push(edge)
    relationCount++
    edges.push(edge)
    edgeById.set(id, edge)
  }

  // tipos: por frecuencia; «Entity» (sin tipo concreto) cede en los empates
  // tipos: por frecuencia; a igualdad, el más conectado (los que acaban en «otros» son los menos relevantes);
  // «Entity» (sin tipo concreto) cede en los empates
  const counts = new Map(), degs = new Map()
  for (const n of nodes) { counts.set(n.type, (counts.get(n.type) || 0) + 1); degs.set(n.type, (degs.get(n.type) || 0) + n.degree + n.selfLoops) }
  const order = [...counts.keys()].sort((a, b) =>
    (counts.get(b) - counts.get(a)) || (degs.get(b) - degs.get(a)) || ((a === 'Entity') - (b === 'Entity')) || a.localeCompare(b))
  const limit = order.length > TYPE_STYLES.length ? TYPE_STYLES.length - 1 : TYPE_STYLES.length
  const used = new Set([...styleMemory.values()].filter(v => v >= 0))
  for (const ty of order) {
    if (styleMemory.has(ty)) continue
    let idx = -1
    for (let i = 0; i < limit; i++) if (!used.has(i)) { idx = i; break }
    styleMemory.set(ty, idx)
    if (idx >= 0) used.add(idx)
  }
  const types = []
  const other = { key: OTHER_KEY, name: OTHER_KEY, count: 0, style: OTHER_STYLE, members: [] }
  for (const ty of order) {
    const idx = styleMemory.get(ty)
    if (idx >= 0) types.push({ key: ty, name: ty, count: counts.get(ty), style: TYPE_STYLES[idx], members: [ty] })
    else { other.count += counts.get(ty); other.members.push(ty) }
  }
  if (other.count) types.push(other)
  const typeOf = new Map()
  for (const ty of types) for (const m of ty.members) typeOf.set(m, ty)
  for (const n of nodes) { const ty = typeOf.get(n.type); n.legend = ty.key; n.style = ty.style }

  // prioridad: los más conectados primero (etiquetas que nunca se esconden, lista accesible, búsqueda vacía)
  const byPriority = [...nodes].sort((a, b) =>
    (b.degree + b.selfLoops * 0.5) - (a.degree + a.selfLoops * 0.5) || a.name.length - b.name.length || a.name.localeCompare(b.name))
  byPriority.forEach((n, i) => { n.rank = i })

  const signature = fnv(nodes.map(n => n.id).join('|') + '#' + edges.map(e => `${e.id}:${e.count || 1}`).join('|'))
  return { nodes, edges, nodeById, edgeById, types, byPriority, relationCount, signature }
}

// ── Utilidades ───────────────────────────────────────────────────────────────
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v)
const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3)
const easeOutBack = (x) => { const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2) }
const easeInOut = (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2)
const TAU = Math.PI * 2
const FONT_SANS = '"Inter Tight", "Noto Sans SC", system-ui, sans-serif'
const LABEL_MAX_W = 140
const EDGE_LABEL_MAX_W = 150
const SELF_ANGLE = -Math.PI / 4   // los autobucles salen arriba a la derecha

// Órbita de los nodos sueltos: elipse con la proporción del hueco disponible (en un panel alto, más alta que ancha)
const orbitForce = (rx, ry, strength) => {
  let nodes = []
  const force = (alpha) => {
    for (const n of nodes) {
      if (!n.ring) continue
      const a = Math.atan2(n.y / ry, n.x / rx)
      n.vx += (Math.cos(a) * rx - n.x) * strength * alpha
      n.vy += (Math.sin(a) * ry - n.y) * strength * alpha
    }
  }
  force.initialize = (ns) => { nodes = ns }
  return force
}

const segDist = (px, py, ax, ay, bx, by) => {
  const dx = bx - ax, dy = by - ay
  const l2 = dx * dx + dy * dy
  let u = l2 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0
  u = u < 0 ? 0 : u > 1 ? 1 : u
  const x = ax + dx * u - px, y = ay + dy * u - py
  return Math.sqrt(x * x + y * y)
}

// Rejilla espacial para que las etiquetas no se pisen entre sí ni tapen nodos
class BoxGrid {
  constructor(cell = 48) { this.cell = cell; this.map = new Map() }
  _each(b, fn) {
    const c = this.cell
    const x0 = Math.floor(b.x0 / c), x1 = Math.floor(b.x1 / c), y0 = Math.floor(b.y0 / c), y1 = Math.floor(b.y1 / c)
    for (let gx = x0; gx <= x1; gx++) for (let gy = y0; gy <= y1; gy++) if (fn((gx + 2048) * 4096 + (gy + 2048)) === false) return
  }
  add(b) { this._each(b, k => { let a = this.map.get(k); if (!a) this.map.set(k, (a = [])); a.push(b) }) }
  // área solapada con lo ya colocado (para elegir el mal menor cuando no queda sitio libre)
  overlap(b, owner) {
    let area = 0
    const seen = new Set()
    this._each(b, k => {
      const a = this.map.get(k)
      if (!a) return
      for (const o of a) {
        if (o.owner === owner || seen.has(o)) continue
        seen.add(o)
        const w = Math.min(o.x1, b.x1) - Math.max(o.x0, b.x0), h = Math.min(o.y1, b.y1) - Math.max(o.y0, b.y0)
        if (w > 0 && h > 0) area += w * h
      }
    })
    return area
  }
  hits(b, owner) {
    let hit = false
    this._each(b, k => {
      const a = this.map.get(k)
      if (!a) return
      for (const o of a) {
        if (o.owner === owner) continue
        if (o.x0 < b.x1 && o.x1 > b.x0 && o.y0 < b.y1 && o.y1 > b.y0) { hit = true; return false }
      }
    })
    return hit
  }
}

// ── Renderer ─────────────────────────────────────────────────────────────────
export class GraphRenderer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {{ onSelect?: Function, onHover?: Function }} opts
   *   onSelect({ kind: 'node'|'edge', id } | null) al hacer clic; onHover(id | null)
   */
  constructor(canvas, opts = {}) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')
    this.opts = opts
    this.edgeLayer = document.createElement('canvas')
    this.nodeLayer = document.createElement('canvas')
    this.labelLayer = document.createElement('canvas')
    this.ectx = this.edgeLayer.getContext('2d')
    this.nctx = this.nodeLayer.getContext('2d')
    this.lctx = this.labelLayer.getContext('2d')
    this.mctx = document.createElement('canvas').getContext('2d')   // solo para medir texto
    this.tk = readTokens()
    this.W = 0; this.H = 0; this.dpr = 1
    this.model = null
    this.nodes = []; this.edges = []
    this.nodeById = new Map(); this.edgeById = new Map()
    this.t = zoomIdentity
    this.hoverId = null; this.hoverEdgeId = null; this.previewId = null
    this.selected = null; this.highlight = null
    this.focus = null; this.fadeFocus = null; this.focusMix = 0; this.focusAnimating = false
    this.showEdgeLabels = true
    this.live = false
    this.reduced = false
    this.visible = true
    this.hidden = typeof document !== 'undefined' && document.hidden
    this.interacted = false
    this.insets = { top: 0, right: 0, bottom: 0, left: 0 }
    this.pulses = []; this.effects = []; this.flashes = []
    this.spawnAcc = 0; this.focusAcc = 0; this.pingAcc = 0; this.twinkleAcc = 0
    this.sweep = null; this.sweepNext = 0
    this.fxLevel = 1; this._fxN = 0; this._fxSum = 0; this._fxCalm = 0   // 1 → 0,5 → 0,25 si el equipo va justo
    this.entry = null; this.entryDur = 0
    this.zoomTween = null
    this.dirty = true
    this.raf = 0; this.last = 0
    this.simActive = false; this.needsRefit = false
    this.dragging = null
    this.glow = new Map()
    this.textCache = new Map()
    this.paths = {}
    for (const [k, d] of Object.entries(SHAPES)) this.paths[k] = new Path2D(d)
    this.strings = { selfLoop: (n) => `↻ ${n}`, relation: humanizeRelation }   // `relation`: cómo se nombra una relación sobre el lienzo (la interfaz pone el idioma)
    this.perf = { intervals: [], work: [] }
    this._pt = { x: 0, y: 0 }
    this.ringR = 0
    this.dprCap = 2
    this.sim = forceSimulation([]).stop()
    this._frameBound = (now) => this._frame(now)
    this._bind()
    // las fuentes de marca llegan después del primer pintado: al cargarse, se vuelven a medir las etiquetas
    if (typeof document !== 'undefined' && document.fonts) {
      Promise.all([
        document.fonts.load(`500 12px ${FONT_SANS}`), document.fonts.load(`600 13px ${FONT_SANS}`),
      ]).catch(() => {}).then(() => document.fonts.ready).then(() => {
        if (this.destroyed) return
        this.textCache.clear(); this.dirty = true; this._schedule()
      })
    }
  }

  // ── API pública ──────────────────────────────────────────────────────────
  setStrings(s) { Object.assign(this.strings, s); this.textCache.clear(); this._invalidate() }
  setInsets(ins) { this.insets = { top: 0, right: 0, bottom: 0, left: 0, ...ins } }
  setShowEdgeLabels(v) { this.showEdgeLabels = !!v; this._invalidate() }
  setLive(v) { this.live = !!v; this._invalidate() }
  setHighlight(set) { this.highlight = set && set.size ? set : null; this._refocus() }
  setPreview(id) { if (id !== this.previewId) { this.previewId = id || null; this._refocus() } }
  setSelected(sel) { this.selected = sel || null; this._refocus() }
  setVisible(v) { this.visible = !!v; if (v) { this.last = 0; this._schedule() } }
  setHidden(v) { this.hidden = !!v; if (!v) { this.last = 0; this._schedule() } }
  setReducedMotion(v) {
    this.reduced = !!v
    if (this.reduced) {
      this.pulses = []; this.effects = []; this.flashes = []; this.sweep = null; this.entry = null; this.zoomTween = null
      if (this.simActive) { this.simActive = false; this.settling = true }
    }
    this._invalidate()
  }

  resize(w, h) {
    w = Math.max(0, Math.round(w)); h = Math.max(0, Math.round(h))
    const dpr = Math.min(typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1, this.dprCap)
    if (w === this.W && h === this.H && dpr === this.dpr) return
    const prevW = this.W, prevH = this.H
    this.W = w; this.H = h; this.dpr = dpr
    this._allocate()
    if (w && h) this.zoomB.extent([[0, 0], [w, h]])
    if (this.nodes.length && w && h && this.ringR && !this.interacted) {
      const asp = this._targetAspect()
      if (Math.abs(Math.log(asp / (this.orbitAspect || 1))) > 0.2) {
        this._configure()
        this.sim.alpha(Math.max(this.sim.alpha(), 0.3))
        if (this.reduced) this._settle(250, this.sim.alphaMin())
        else { this.simActive = true; this.needsRefit = true }
      }
    }
    if (this.nodes.length && w && h) {
      // un ajuste animado pedido antes (con el ancho de entonces) pisaría cada fotograma el ajuste nuevo y, si
      // termina después del último cambio de tamaño, dejaría el grafo descentrado: con el panel ensanchándose
      // al cambiar de vista pasaba casi siempre en equipos lentos
      if (!this.interacted || !prevW) { this.zoomTween = null; this._applyTransform(this._fitTransform()) }
      else this._applyTransform(zoomIdentity.translate(this.t.x + (w - prevW) / 2, this.t.y + (h - prevH) / 2).scale(this.t.k))
    }
    this._invalidate()
  }

  _allocate() {
    for (const cv of [this.canvas, this.edgeLayer, this.nodeLayer, this.labelLayer]) {
      cv.width = Math.max(1, Math.round(this.W * this.dpr))
      cv.height = Math.max(1, Math.round(this.H * this.dpr))
    }
  }

  setModel(model) {
    const now = performance.now()
    if (!model || !model.nodes.length) {
      this.model = model || null
      this.nodes = []; this.edges = []; this.nodeById = new Map(); this.edgeById = new Map()
      this.sim.nodes([]); this.pulses = []; this.effects = []; this.simActive = false; this.entry = null
      this.hoverId = this.hoverEdgeId = this.previewId = null
      this._refocus()
      return
    }
    const first = !this.nodes.length
    const same = !first && this.model && this.model.signature === model.signature
    const oldNodes = this.nodeById, oldEdges = this.edgeById
    const c0 = this._centroid()
    const born = []
    for (const n of model.nodes) {
      const o = oldNodes.get(n.id)
      if (o) {
        n.x = o.x; n.y = o.y; n.vx = o.vx; n.vy = o.vy; n.fx = o.fx; n.fy = o.fy
        n.bornAt = o.bornAt; n.labelPos = o.labelPos; n._norm = o._norm
      } else if (!first) {
        // aparece junto a un vecino que ya estaba (o en la órbita, si llega suelto)
        let nb = null
        for (const id of n.nbr) { nb = oldNodes.get(id); if (nb) break }
        const a = Math.random() * TAU
        const d = nb ? 26 + Math.random() * 14 : (this.ringRx || 90)
        n.x = (nb ? nb.x : c0.x) + Math.cos(a) * d
        n.y = (nb ? nb.y : c0.y) + Math.sin(a) * d
        n.bornAt = now
        born.push(n)
      }
    }
    for (const e of model.edges) {
      const o = oldEdges.get(e.id)
      if (o) e.bornAt = o.bornAt
      else if (!first) e.bornAt = now
    }
    this.model = model
    this.nodes = model.nodes; this.edges = model.edges
    this.nodeById = model.nodeById; this.edgeById = model.edgeById
    for (const e of this.edges) if (e.self) { e.source = e.target = this.nodeById.get(e.sid) }
    // las aristas son objetos nuevos: los pulsos en curso pasan a la arista equivalente (si sigue existiendo)
    this.pulses = this.pulses.map(p => { const e = this.edgeById.get(p.e.id); return e ? { ...p, e } : null }).filter(Boolean)
    this._sizeNodes()
    this._configure()

    if (same) {
      // mismos ids: cambian datos (resúmenes, hechos), no la forma. Nada se mueve ni se recalienta.
    } else if (first) {
      this._seedPositions()
      this.sim.alpha(1)
      // un bloque síncrono corto (≤ 50 ms) para no empezar con una maraña; el resto, en vivo
      this._settle(50, this.reduced ? this.sim.alphaMin() : 0.03)
      this.simActive = !this.reduced && this.sim.alpha() > this.sim.alphaMin()
      this.settling = this.reduced && this.sim.alpha() > this.sim.alphaMin()
      this.needsRefit = this.simActive
      if (!this.interacted) this._applyTransform(this._fitTransform())
      if (!this.reduced) {
        const N = this.nodes.length
        const spread = Math.min(420, 120 + N * 6)
        for (const n of this.nodes) n.entryDelay = (n.rank / Math.max(1, N - 1)) * spread
        // si el panel aún no se ve (modo «Mesa de trabajo»), la entrada espera al primer fotograma visible
        this.entry = { t0: this.W && this.visible && !this.hidden ? now : null }
        this.entryDur = spread + 560
      }
    } else {
      this.sim.alpha(Math.max(this.sim.alpha(), 0.45))
      if (this.reduced) {
        this._settle(50, this.sim.alphaMin())
        this.simActive = false
        this.settling = this.sim.alpha() > this.sim.alphaMin()
        if (!this.settling && !this.interacted) this._applyTransform(this._fitTransform())
      } else {
        this.simActive = true
        this.needsRefit = !this.interacted
        for (const n of born) this._ripple(n.id, now)
      }
    }
    if (this.hoverId && !this.nodeById.has(this.hoverId)) this.hoverId = null
    if (this.hoverEdgeId && !this.edgeById.has(this.hoverEdgeId)) this.hoverEdgeId = null
    if (this.previewId && !this.nodeById.has(this.previewId)) this.previewId = null
    this._refocus()
  }

  fit(animate = true) {
    if (!this.nodes.length) return
    this.interacted = false
    const t = this._fitTransform()
    if (animate && !this.reduced) this._tweenTo(t, 560)
    else this._applyTransform(t)
  }

  zoomBy(f) {
    if (!this.W) return
    const ins = this.insets
    const cx = ins.left + (this.W - ins.left - ins.right) / 2, cy = ins.top + (this.H - ins.top - ins.bottom) / 2
    const t = this.t, [k0, k1] = this.zoomB.scaleExtent()
    const k = clamp(t.k * f, k0, k1)
    const nt = zoomIdentity.translate(cx - (cx - t.x) * (k / t.k), cy - (cy - t.y) * (k / t.k)).scale(k)
    this.interacted = true
    if (this.reduced) this._applyTransform(nt)
    else this._tweenTo(nt, 220)
  }

  panBy(dx, dy) {
    const t = this.t
    this.interacted = true
    const nt = zoomIdentity.translate(t.x + dx, t.y + dy).scale(t.k)
    if (this.reduced) this._applyTransform(nt)
    else this._tweenTo(nt, 160)
  }

  centerOn(id, { zoomIn = false } = {}) {
    const n = this.nodeById.get(id)
    if (!n || !this.W) return
    const ins = this.insets
    const k = zoomIn ? clamp(this.t.k * 1.8, 1.2, 4) : clamp(Math.max(this.t.k, 1.05), 0.05, 4)
    const cx = ins.left + (this.W - ins.left - ins.right) / 2, cy = ins.top + (this.H - ins.top - ins.bottom) / 2
    this.interacted = true
    const nt = zoomIdentity.translate(cx - n.x * k, cy - n.y * k).scale(k)
    if (this.reduced) this._applyTransform(nt)
    else this._tweenTo(nt, 520)
  }

  // si el nodo queda bajo un panel, se desplaza la vista; `minK` acerca hasta un zoom legible (móvil)
  ensureVisible(id, { minK = 0 } = {}) {
    const n = this.nodeById.get(id)
    if (!n || !this.W || n.sx == null) return
    const ins = this.insets, m = 28
    const inside = n.sx > ins.left + m && n.sx < this.W - ins.right - m && n.sy > ins.top + m && n.sy < this.H - ins.bottom - m
    if (inside && this.t.k >= minK) return
    const cx = ins.left + (this.W - ins.left - ins.right) / 2, cy = ins.top + (this.H - ins.top - ins.bottom) / 2
    const k = Math.max(this.t.k, minK)
    const nt = zoomIdentity.translate(cx - n.x * k, cy - n.y * k).scale(k)
    this.interacted = true
    if (this.reduced) this._applyTransform(nt)
    else this._tweenTo(nt, 420)
  }

  getPerf() {
    const iv = this.perf.intervals, wk = this.perf.work
    const avg = (a) => (a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0)
    const sorted = [...wk].sort((a, b) => a - b)
    return {
      fps: iv.length ? 1000 / avg(iv) : 0,
      workMs: avg(wk),
      workP95: sorted.length ? sorted[Math.floor(sorted.length * 0.95)] : 0,
      frames: iv.length,
      nodes: this.nodes.length, edges: this.edges.length, simActive: this.simActive, pulses: this.pulses.length, dpr: this.dpr,
    }
  }
  resetPerf() { this.perf = { intervals: [], work: [] } }

  destroy() {
    this.destroyed = true
    if (this.raf) cancelAnimationFrame(this.raf)
    this.raf = 0
    this.sim.stop()
    const c = this.canvas
    select(c).on('.zoom', null).on('.drag', null)
    c.removeEventListener('pointermove', this._onMove)
    c.removeEventListener('pointerleave', this._onLeave)
    c.removeEventListener('click', this._onClick)
    c.removeEventListener('dblclick', this._onDbl)
  }

  // ── Interacción ──────────────────────────────────────────────────────────
  _bind() {
    const c = this.canvas
    const sel = select(c)
    this.dragB = d3drag()
      .container(c)
      .clickDistance(4)
      .filter((ev) => !ev.ctrlKey && !ev.button)
      .subject((ev) => { const n = this._hitNode(ev.x, ev.y); return n ? { n, x: n.sx, y: n.sy } : null })
      .on('start', (ev) => {
        const n = ev.subject.n
        this.dragging = n; this.dragMoved = false
        n.fx = n.x; n.fy = n.y
        this._refocus()
      })
      .on('drag', (ev) => {
        const n = ev.subject.n
        if (!this.dragMoved) {
          if (Math.hypot(ev.x - ev.subject.x, ev.y - ev.subject.y) < 3) return
          this.dragMoved = true
          this.interacted = true
          c.style.cursor = 'grabbing'
          if (!this.reduced) {
            this.sim.alphaTarget(0.2)
            if (this.sim.alpha() < 0.2) this.sim.alpha(0.2)
            this.simActive = true
          }
        }
        n.fx = (ev.x - this.t.x) / this.t.k
        n.fy = (ev.y - this.t.y) / this.t.k
        n.x = n.fx; n.y = n.fy   // sigue al puntero en cada fotograma aunque la física vaya a su ritmo
        this._invalidate()
      })
      .on('end', (ev) => {
        const n = ev.subject.n
        this.sim.alphaTarget(0)
        n.fx = null; n.fy = null
        this.dragging = null
        c.style.cursor = ''
        this._refocus()
      })
    this.zoomB = d3zoom()
      .scaleExtent([0.03, 8])
      .clickDistance(4)
      .on('zoom', (ev) => {
        this.t = ev.transform
        if (ev.sourceEvent) { this.interacted = true; this.zoomTween = null }
        this._invalidate()
      })
    sel.call(this.dragB).call(this.zoomB).on('dblclick.zoom', null)

    const local = (ev) => { const r = c.getBoundingClientRect(); return [ev.clientX - r.left, ev.clientY - r.top] }
    this._onMove = (ev) => {
      if (ev.pointerType === 'touch') return
      this.pointer = local(ev)
      if (this.hoverPending) return
      this.hoverPending = true
      requestAnimationFrame(() => { this.hoverPending = false; this._updateHover() })
    }
    this._onLeave = () => { this.pointer = null; this._setHover(null, null) }
    this._onClick = (ev) => {
      const [x, y] = local(ev)
      const n = this._hitNode(x, y)
      if (n) return this.opts.onSelect?.({ kind: 'node', id: n.id })
      const e = this._hitEdge(x, y)
      if (e) return this.opts.onSelect?.({ kind: 'edge', id: e.id })
      this.opts.onSelect?.(null)
    }
    this._onDbl = (ev) => {
      const [x, y] = local(ev)
      const n = this._hitNode(x, y)
      if (!n) return
      this.centerOn(n.id, { zoomIn: true })
      this.opts.onSelect?.({ kind: 'node', id: n.id })
    }
    c.addEventListener('pointermove', this._onMove)
    c.addEventListener('pointerleave', this._onLeave)
    c.addEventListener('click', this._onClick)
    c.addEventListener('dblclick', this._onDbl)
  }

  _updateHover() {
    if (!this.pointer || this.dragging) return
    const [x, y] = this.pointer
    const n = this._hitNode(x, y)
    const e = n ? null : this._hitEdge(x, y)
    this._setHover(n?.id || null, e?.id || null)
    this.canvas.style.cursor = n || e ? 'pointer' : ''
  }

  _setHover(nid, eid) {
    if (nid === this.hoverId && eid === this.hoverEdgeId) return
    const changedNode = nid !== this.hoverId
    this.hoverId = nid; this.hoverEdgeId = eid
    this._refocus()
    if (changedNode) this.opts.onHover?.(nid)
  }

  _hitNode(x, y) {
    let best = null, bd = Infinity
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i]
      if (!n.vis || n.a < 0.3) continue
      const dx = x - n.sx, dy = y - n.sy, d2 = dx * dx + dy * dy
      const rr = Math.max(n.sr * 1.25, 6) + 4
      if (d2 < rr * rr && d2 < bd) { bd = d2; best = n }
    }
    return best
  }

  _hitEdge(x, y) {
    let best = null, bd = 6
    for (const e of this.edges) {
      if (!e.vis || e.p < 1) continue
      if (e.self) {
        const d = Math.abs(Math.hypot(x - e.lcx, y - e.lcy) - e.lr)
        if (d < bd) { bd = d; best = e }
        continue
      }
      const s = e.source, t = e.target
      if (x < Math.min(s.sx, t.sx, e.cx) - 6 || x > Math.max(s.sx, t.sx, e.cx) + 6 || y < Math.min(s.sy, t.sy, e.cy) - 6 || y > Math.max(s.sy, t.sy, e.cy) + 6) continue
      let px = s.sx, py = s.sy
      for (let i = 1; i <= 16; i++) {
        const p = this._curvePoint(e, i / 16)
        const d = segDist(x, y, px, py, p.x, p.y)
        if (d < bd) { bd = d; best = e }
        px = p.x; py = p.y
      }
    }
    return best
  }

  _refocus() {
    const f = this._computeFocus()
    if (f) { this.focus = f; this.fadeFocus = null }
    else if (this.focus) { this.fadeFocus = this.focus; this.focus = null }
    this.focusAnimating = true
    this._invalidate()
  }

  _computeFocus() {
    const ofNode = (id) => {
      const n = this.nodeById.get(id)
      if (!n) return null
      return { nodes: new Set([id, ...n.nbr]), edges: new Set(n.links.map(e => e.id)), center: id }
    }
    const ofEdge = (id) => {
      const e = this.edgeById.get(id)
      if (!e) return null
      return { nodes: new Set([e.sid, e.tid]), edges: new Set([e.id]), edge: id }
    }
    if (this.dragging) return ofNode(this.dragging.id)
    if (this.hoverId) return ofNode(this.hoverId)
    if (this.hoverEdgeId) return ofEdge(this.hoverEdgeId)
    if (this.previewId) return ofNode(this.previewId)
    if (this.selected?.kind === 'node') return ofNode(this.selected.id)
    if (this.selected?.kind === 'edge') return ofEdge(this.selected.id)
    if (this.highlight) {
      const es = new Set()
      for (const e of this.edges) if (this.highlight.has(e.sid) && this.highlight.has(e.tid)) es.add(e.id)
      return { nodes: this.highlight, edges: es }
    }
    return null
  }

  // ── Layout ───────────────────────────────────────────────────────────────
  _sizeNodes() {
    const N = this.nodes.length
    const scale = N > 900 ? 0.6 : N > 300 ? 0.74 : 1
    for (const n of this.nodes) {
      n.r = Math.min(26, 7 + 4 * Math.sqrt(n.degree + (n.selfLoops ? 0.5 : 0))) * scale
      // en grafos enormes los poco conectados pesan menos: la estructura (los hubs) se lee primero
      n.quiet = N > 900 && n.degree <= 2
      if (n.quiet) n.r *= 0.8
      n.hub = n.rank < 6 && n.degree >= 3
    }
  }

  _configure() {
    const N = this.nodes.length
    const big = N > 300, huge = N > 900
    const iso = this.nodes.filter(n => n.degree === 0)
    // Muchos nodos sueltos (lo normal mientras se construye el grafo): en vez de mezclarse con los grupos, giran
    // en una órbita alrededor del núcleo conectado. Se lee de un vistazo qué entidades aún no tienen relaciones.
    const useRing = !big && iso.length >= 6 && iso.length >= N * 0.2 && iso.length < N
    const connected = N - iso.length
    this.ringR = useRing ? Math.max(90 + 48 * Math.sqrt(connected), (iso.length * 70) / TAU) : 0
    // la proporción sale del hueco visible descontando lo que ocupan las etiquetas a los lados
    this.orbitAspect = this._targetAspect()
    const asp = Math.sqrt(this.orbitAspect)
    this.ringRx = this.ringR / asp
    this.ringRy = this.ringR * asp
    for (const n of this.nodes) n.ring = useRing && n.degree === 0
    const links = this.edges.filter(e => !e.self)
    this.sim
      .nodes(this.nodes)
      .force('link', forceLink(links).id(d => d.id)
        .distance(e => (huge ? 16 : big ? 28 : N <= 80 ? 92 : 64) + (e.source.r + e.target.r) * 1.1 + (e.pairTotal > 1 ? 22 : 0)))
      .force('charge', forceManyBody().strength(huge ? -34 : big ? -55 : -240).distanceMax(huge ? 240 : big ? 380 : 560).theta(huge ? 1.1 : 0.9))
      // con más de 900 nodos la repulsión basta para separarlos; la colisión costaría un tercio de cada tick
      .force('collide', huge ? null : forceCollide(d => d.r + (big ? 5 : 16)).strength(0.85).iterations(2))
      .force('x', forceX(0).strength(d => (d.ring ? 0 : d.degree === 0 ? 0.09 : 0.05)))
      .force('y', forceY(0).strength(d => (d.ring ? 0 : d.degree === 0 ? 0.09 : 0.05)))
      .force('ring', useRing ? orbitForce(this.ringRx, this.ringRy, 0.55) : null)
      .velocityDecay(0.42)
      .alphaDecay(huge ? 0.045 : big ? 0.032 : 0.0228)
      .alphaMin(0.004)
      .stop()
  }

  _targetAspect() {
    const ins = this.insets
    const aw = (this.W || 800) - ins.left - ins.right - 260
    const ah = (this.H || 800) - ins.top - ins.bottom - 80
    return clamp(ah / Math.max(120, aw), 0.6, 1.7)
  }

  _seedPositions() {
    // filotaxis por prioridad: los nodos con más conexiones nacen en el centro; los sueltos, ya en su órbita
    const ring = this.nodes.filter(n => n.ring)
    let i = 0
    for (const n of this.model.byPriority) {
      if (n.ring) continue
      const r = 14 * Math.sqrt(i + 0.5), a = i * 2.399963
      n.x = r * Math.cos(a); n.y = r * Math.sin(a); n.vx = n.vy = 0
      i++
    }
    ring.forEach((n, j) => {
      const a = (j / ring.length) * TAU - Math.PI / 2
      n.x = Math.cos(a) * this.ringRx; n.y = Math.sin(a) * this.ringRy; n.vx = n.vy = 0
    })
  }

  _settle(budgetMs, stopAlpha) {
    const end = performance.now() + budgetMs
    let ticks = 0
    while (this.sim.alpha() > stopAlpha && performance.now() < end) { this.sim.tick(); ticks++ }
    return ticks
  }

  _centroid() {
    const ns = this.nodes
    if (!ns.length) return { x: 0, y: 0 }
    let x = 0, y = 0
    for (const n of ns) { x += n.x || 0; y += n.y || 0 }
    return { x: x / ns.length, y: y / ns.length }
  }

  _sizeScale(k) { return clamp(Math.pow(k, 0.55), 0.42, 2.2) }

  // Encuadre: el mayor zoom con el que caben nodos Y etiquetas (las etiquetas no escalan, por eso se busca por
  // bisección en vez de una sola división). Por encima de 120 nodos solo cuentan los nodos.
  _fitTransform() {
    const ns = this.nodes, W = this.W, H = this.H, ins = this.insets
    if (!ns.length || !W || !H) return this.t
    const availW = Math.max(80, W - ins.left - ins.right - 28)
    const availH = Math.max(80, H - ins.top - ins.bottom - 20)
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const n of ns) {
      minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x)
      minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y)
    }
    const cxw = (minX + maxX) / 2, cyw = (minY + maxY) / 2
    const withLabels = ns.length <= 120
    const extents = (k) => {
      const ss = this._sizeScale(k)
      let l = Infinity, r = -Infinity, t = Infinity, b = -Infinity
      for (const n of ns) {
        const x = (n.x - cxw) * k, y = (n.y - cyw) * k, sr = n.r * ss * 1.25 + 4
        l = Math.min(l, x - sr); r = Math.max(r, x + sr); t = Math.min(t, y - sr); b = Math.max(b, y + sr)
        if (withLabels) {
          const info = this._labelInfo(n)
          const dir = this._prefDir(x, y)
          const bx = this._labelBoxAt(x, y, sr, info, dir)
          l = Math.min(l, bx.x0); r = Math.max(r, bx.x1); t = Math.min(t, bx.y0); b = Math.max(b, bx.y1)
        }
      }
      return { l, r, t, b, ok: r - l <= availW && b - t <= availH }
    }
    const kMax = ns.length < 12 ? 1.5 : 1.7
    // zoom solo con nodos (las etiquetas no escalan: en un panel estrecho obligarían a un grafo diminuto)
    const bw = Math.max(1, maxX - minX), bh = Math.max(1, maxY - minY)
    const kNodes = clamp(Math.min((availW - 40) / bw, (availH - 40) / bh), 0.03, kMax)
    let k
    if (extents(kMax).ok) k = kMax
    else {
      let lo = 0.03, hi = kMax
      if (!extents(lo).ok) k = lo
      else {
        for (let i = 0; i < 18; i++) { const mid = (lo + hi) / 2; if (extents(mid).ok) lo = mid; else hi = mid }
        k = lo
      }
    }
    // las etiquetas que no quepan se esconden (y salen al acercar o al pasar el ratón): el grafo no encoge de más
    k = Math.max(k, kNodes * 0.62)
    const ex = extents(k)
    // si las etiquetas desbordan, se centra por los nodos para no descolocar el conjunto
    if (!ex.ok) {
      const ss = this._sizeScale(k)
      let l = Infinity, r = -Infinity, tt = Infinity, b = -Infinity
      for (const n of ns) {
        const x = (n.x - cxw) * k, y = (n.y - cyw) * k, sr = n.r * ss * 1.25 + 4
        l = Math.min(l, x - sr); r = Math.max(r, x + sr); tt = Math.min(tt, y - sr); b = Math.max(b, y + sr)
      }
      ex.l = l; ex.r = r; ex.t = tt; ex.b = b
    }
    const scx = ins.left + (W - ins.left - ins.right) / 2
    const scy = ins.top + (H - ins.top - ins.bottom) / 2
    return zoomIdentity.translate(scx - (ex.l + ex.r) / 2 - cxw * k, scy - (ex.t + ex.b) / 2 - cyw * k).scale(k)
  }

  _applyTransform(t) {
    this._tweening = true
    select(this.canvas).call(this.zoomB.transform, t)
    this._tweening = false
    this.t = t
  }

  _tweenTo(t1, dur) {
    const t0 = this.t, W = this.W || 1, H = this.H || 1
    const v0 = [(W / 2 - t0.x) / t0.k, (H / 2 - t0.y) / t0.k, W / t0.k]
    const v1 = [(W / 2 - t1.x) / t1.k, (H / 2 - t1.y) / t1.k, W / t1.k]
    this.zoomTween = { i: interpolateZoom(v0, v1), start: performance.now(), dur, W, H }
    this._schedule()
  }

  // ── Bucle ────────────────────────────────────────────────────────────────
  _invalidate() { this.dirty = true; this._schedule() }

  _schedule() {
    if (this.inFrame || this.raf || this.destroyed || !this.visible || this.hidden || !this.W || !this.H) return
    this.raf = requestAnimationFrame(this._frameBound)
  }

  _wantsLoop() {
    if (this.settling || this.simActive || this.entry || this.zoomTween || this.focusAnimating || this.dirty) return true
    if (this.reduced) return false
    if (this.effects.length || this.pulses.length) return true
    if (this.live && this.nodes.length) return true
    if (this.edges.length) return true          // pulsos de ambiente
    if (this.selected?.kind === 'node') return true  // anillo de selección que gira
    if (this.nodes.some(n => n.bornAt && performance.now() - n.bornAt < 700)) return true
    return false
  }

  _frame(now) {
    this.raf = 0
    if (this.destroyed || !this.visible || this.hidden || !this.W || !this.H) return
    this.inFrame = true
    try { this._step(now) } finally { this.inFrame = false }
    if (this._wantsLoop()) this.raf = requestAnimationFrame(this._frameBound)
  }

  _step(now) {
    const w0 = performance.now()
    const dt = this.last ? Math.min(0.05, (now - this.last) / 1000) : 1 / 60
    if (this.last) { const iv = this.perf.intervals; iv.push(now - this.last); if (iv.length > 240) iv.shift() }
    this.last = now

    if (this.zoomTween) {
      const z = this.zoomTween
      const u = clamp((now - z.start) / z.dur, 0, 1)
      const v = z.i(easeInOut(u))
      const k = z.W / v[2]
      this._applyTransform(zoomIdentity.translate(z.W / 2 - v[0] * k, z.H / 2 - v[1] * k).scale(k))
      if (u >= 1) this.zoomTween = null
      this.dirty = true
    }
    if (this.settling) {
      // movimiento reducido: el layout se calcula en trozos de ~10 ms y no se pinta hasta que está quieto
      const end = performance.now() + 10
      while (this.sim.alpha() > this.sim.alphaMin() && performance.now() < end) this.sim.tick()
      if (this.sim.alpha() <= this.sim.alphaMin()) {
        this.settling = false
        if (!this.interacted) this._applyTransform(this._fitTransform())
        this.dirty = true
      } else {
        this.ctx.setTransform(1, 0, 0, 1, 0, 0)
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
        return
      }
    }
    if (this.simActive) {
      // Si un tick es caro (grafos enormes en equipos lentos), la física avanza en fotogramas alternos: el
      // pintado, el paneo y los pulsos siguen a 60 fps.
      const ema = this.tickMs || 0
      this.tickPhase = (this.tickPhase || 0) + 1
      const every = ema > 14 ? 3 : ema > 7 ? 2 : 1
      if (this.tickPhase % every === 0) {
        const t0 = performance.now()
        this.sim.tick()
        if (ema < 3 && this.sim.alpha() > 0.3) this.sim.tick()   // el principio, más deprisa si sobra tiempo
        this.tickMs = ema * 0.8 + (performance.now() - t0) * 0.2
        this.dirty = true
      }
      if (this.sim.alpha() < this.sim.alphaMin() && !this.dragging && this.sim.alphaTarget() === 0) {
        this.simActive = false
        if (this.needsRefit && !this.interacted) this.fit(true)
        this.needsRefit = false
      }
    }
    if (this.entry) {
      if (this.entry.t0 == null) this.entry.t0 = now
      this.dirty = true
      if (now - this.entry.t0 > this.entryDur) this.entry = null
    }
    if (this.focusAnimating) {
      const target = this.focus ? 1 : 0
      if (this.reduced) this.focusMix = target
      else this.focusMix = clamp(this.focusMix + (target ? 1 : -1) * dt / 0.16, 0, 1)
      if (this.focusMix === target) { this.focusAnimating = false; if (!target) this.fadeFocus = null }
      this.dirty = true
    }
    if (!this.dirty && this.nodes.some(n => n.bornAt && now - n.bornAt < 700)) this.dirty = true
    if (!this.dirty && this.edges.some(e => e.bornAt && now - e.bornAt < 700)) this.dirty = true

    const wasDirty = this.dirty
    const r0 = performance.now()
    if (this.dirty) { this.dirty = false; this._renderStatic(now) }
    this._busy = wasDirty   // se repinta la escena entera (paneo, zoom, física): la animación cede
    this._composite(now, dt)
    if (wasDirty) this._adaptResolution(performance.now() - r0)   // solo el pintado (no la física)

    const wk = this.perf.work
    wk.push(performance.now() - w0)
    if (wk.length > 240) wk.shift()
  }

  // Equipos sin aceleración gráfica: si el repintado completo pasa de ~22 ms de forma sostenida, se baja la
  // densidad de píxeles (2 → 1,5 → 1). Con GPU nunca llega a activarse.
  _adaptResolution(ms) {
    const a = (this._slow = this._slow || { n: 0, sum: 0 })
    a.n++; a.sum += ms
    if (a.n < 24) return
    const avg = a.sum / a.n
    a.n = 0; a.sum = 0
    if (avg > 22 && this.dprCap > 1) {
      this.dprCap = this.dprCap > 1.5 ? 1.5 : 1
      this.dpr = Math.min(window.devicePixelRatio || 1, this.dprCap)
      this._allocate()
      this.dirty = true
    }
  }

  // ── Pintado de las capas en caché ────────────────────────────────────────
  _renderStatic(now) {
    const { W, H, t } = this
    const ss = this._sizeScale(t.k)
    const c = this._centroid()
    const entry = this.entry, ent = entry ? now - (entry.t0 ?? now) : 0
    for (const n of this.nodes) {
      let p = 1, sc = 1, x = n.x, y = n.y
      if (entry) {
        p = clamp((ent - n.entryDelay) / 520, 0, 1)
        sc = easeOutBack(p)
        const e = easeOutCubic(p)
        x = c.x + (n.x - c.x) * (0.2 + 0.8 * e)
        y = c.y + (n.y - c.y) * (0.2 + 0.8 * e)
      } else if (n.bornAt && now - n.bornAt < 520) {
        p = (now - n.bornAt) / 520
        sc = easeOutBack(p)
      }
      n.ap = p
      n.sx = x * t.k + t.x
      n.sy = y * t.k + t.y
      n.sr = Math.max(0.01, n.r * ss * Math.max(0, sc))
      n.a = clamp(p * 1.7, 0, 1)
      n.vis = n.a > 0 && n.sx > -90 && n.sx < W + 90 && n.sy > -90 && n.sy < H + 90
    }
    for (const e of this.edges) {
      const s = e.source, tg = e.target
      if (!s || !tg) { e.vis = false; continue }
      let p = 1
      if (entry) p = easeInOut(clamp((Math.min(s.ap, tg.ap) - 0.3) / 0.7, 0, 1))
      else if (e.bornAt && now - e.bornAt < 650) p = easeInOut((now - e.bornAt) / 650)
      e.p = p
      if (e.self) {
        e.lr = Math.max(8, s.sr * 0.8 + 7)
        const d = s.sr + e.lr * 0.45
        e.lcx = s.sx + Math.cos(SELF_ANGLE) * d
        e.lcy = s.sy + Math.sin(SELF_ANGLE) * d
        e.len = TAU * e.lr
        e.vis = s.vis && p > 0
        continue
      }
      const dx = tg.sx - s.sx, dy = tg.sy - s.sy
      const len = Math.hypot(dx, dy) || 1
      const off = e.curv * len
      e.cx = (s.sx + tg.sx) / 2 - (dy / len) * off
      e.cy = (s.sy + tg.sy) / 2 + (dx / len) * off
      e.len = len
      e.vis = p > 0 && !(
        Math.max(s.sx, tg.sx, e.cx) < -10 || Math.min(s.sx, tg.sx, e.cx) > W + 10 ||
        Math.max(s.sy, tg.sy, e.cy) < -10 || Math.min(s.sy, tg.sy, e.cy) > H + 10)
    }
    this.cScreen = { x: c.x * t.k + t.x, y: c.y * t.k + t.y }
    const F = this.focus || this.fadeFocus
    const fm = F ? this.focusMix : 0
    const T = performance.now
    const p0 = T.call(performance)
    this._drawBackground(this.ectx)
    this._drawOrbit(this.ectx)
    const p1 = T.call(performance)
    this._drawEdges(this.ectx, F, fm)
    const p2 = T.call(performance)
    this._drawNodes(this.nctx, F, fm)
    const p3 = T.call(performance)
    this.lctx.setTransform(1, 0, 0, 1, 0, 0)
    this.lctx.globalAlpha = 1
    this.lctx.clearRect(0, 0, this.labelLayer.width, this.labelLayer.height)
    this._drawLabels(this.lctx, F, fm)
    const p4 = T.call(performance)
    this.perf.parts = { pre: p0 - now, bg: p1 - p0, edges: p2 - p1, nodes: p3 - p2, labels: p4 - p3 }
  }

  // El brillo del escenario es CSS (un degradado a pantalla completa cuesta ~10 ms por fotograma con
  // rasterizado por software). Aquí solo la retícula de puntos, que sigue al paneo y escala más despacio que
  // el grafo (se lee como un plano de fondo).
  _drawBackground(ctx) {
    const { W, H, tk } = this
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    ctx.clearRect(0, 0, this.edgeLayer.width, this.edgeLayer.height)
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    const s = clamp(26 * Math.pow(this.t.k, 0.5), 15, 46)
    const ox = ((this.t.x % s) + s) % s, oy = ((this.t.y % s) + s) % s
    ctx.fillStyle = rgba(tk['--gray-600'], 0.3)
    ctx.beginPath()
    for (let x = ox; x < W; x += s) for (let y = oy; y < H; y += s) ctx.rect(x - 0.7, y - 0.7, 1.4, 1.4)
    ctx.fill()
  }

  _drawOrbit(ctx) {
    if (!this.ringR || this.nodes.length > 300) return
    const t = this.t
    const a = this.entry ? clamp((performance.now() - (this.entry.t0 ?? performance.now())) / 700, 0, 1) : 1
    ctx.save()
    ctx.beginPath()
    ctx.ellipse(t.x, t.y, this.ringRx * t.k, this.ringRy * t.k, 0, 0, TAU)
    ctx.setLineDash([2, 7])
    ctx.lineWidth = 1
    ctx.strokeStyle = this.tk['--gray-600']
    ctx.globalAlpha = 0.55 * a
    ctx.stroke()
    ctx.restore()
  }

  _edgePath(ctx, e, p = e.p) {
    if (e.self) {
      const a0 = SELF_ANGLE + Math.PI
      ctx.moveTo(e.lcx + Math.cos(a0) * e.lr, e.lcy + Math.sin(a0) * e.lr)
      ctx.arc(e.lcx, e.lcy, e.lr, a0, a0 + TAU * p)
      return
    }
    const s = e.source, t = e.target
    ctx.moveTo(s.sx, s.sy)
    if (p >= 1) { ctx.quadraticCurveTo(e.cx, e.cy, t.sx, t.sy); return }
    // De Casteljau: el tramo [0, p] de la curva es otra cuadrática (para el «dibujado» de una arista nueva)
    const q0x = s.sx + (e.cx - s.sx) * p, q0y = s.sy + (e.cy - s.sy) * p
    const q1x = e.cx + (t.sx - e.cx) * p, q1y = e.cy + (t.sy - e.cy) * p
    ctx.quadraticCurveTo(q0x, q0y, q0x + (q1x - q0x) * p, q0y + (q1y - q0y) * p)
  }

  _curvePoint(e, u) {
    const o = this._pt
    if (e.self) {
      const a = SELF_ANGLE + Math.PI + u * TAU
      o.x = e.lcx + Math.cos(a) * e.lr; o.y = e.lcy + Math.sin(a) * e.lr
      return o
    }
    const s = e.source, t = e.target, v = 1 - u
    o.x = v * v * s.sx + 2 * v * u * e.cx + u * u * t.sx
    o.y = v * v * s.sy + 2 * v * u * e.cy + u * u * t.sy
    return o
  }

  _colorOf(n) { return this.tk[styleColorToken(n.style)] }

  // Suma de grados por encima de la cual una arista cuenta como «estructura» (el 28 % más conectado)
  _hubCut() {
    const sig = `${this.model?.signature}|${this.edges.length}`
    if (this._cutSig === sig) return this._cut
    const w = []
    for (const e of this.edges) if (!e.self && e.source && e.target) w.push(e.source.degree + e.target.degree)
    w.sort((a, b) => a - b)
    this._cut = w.length ? Math.max(3, w[Math.floor(w.length * 0.72)]) : 3
    this._cutSig = sig
    return this._cut
  }

  _drawEdges(ctx, F, fm) {
    const { tk } = this
    const lime = tk['--lime-500']
    const E = this.edges.length
    const big = E > 250
    const dimK = F ? 1 - 0.86 * fm : 1
    const selEdge = this.selected?.kind === 'edge' ? this.selected.id : null
    ctx.lineCap = 'round'
    if (big) {
      // muchas aristas: pocas pasadas (miles de degradados por fotograma no caben en 16 ms). Dos niveles: las que
      // tocan a los nodos más conectados se leen como la estructura (claras y con halo); el resto, como el tejido
      // de fondo, pero ya no a un 30 % que se perdía entre los nodos.
      const cut = this._hubCut()
      const isHub = (e) => !e.self && e.source.degree + e.target.degree >= cut
      ctx.beginPath()
      for (const e of this.edges) if (e.vis && !(F && F.edges.has(e.id)) && !isHub(e)) this._edgePath(ctx, e)
      ctx.globalAlpha = (E > 900 ? 0.24 : 0.42) * dimK
      ctx.strokeStyle = lime
      ctx.lineWidth = E > 900 ? 1 : 1.15
      ctx.stroke()
      ctx.beginPath()
      let hubs = 0
      for (const e of this.edges) if (e.vis && !(F && F.edges.has(e.id)) && isHub(e)) { this._edgePath(ctx, e); hubs++ }
      if (hubs) {
        // con cientos de relaciones principales los halos aditivos se suman en el núcleo y lo lavan: proporcional
        const dens = clamp(160 / hubs, 0.25, 1)
        if (dens > 0.5) {   // con tantas, el halo ancho aditivo es casi invisible y es lo más caro de repintar
          ctx.globalCompositeOperation = 'lighter'
          ctx.globalAlpha = 0.07 * dens * dimK
          ctx.lineWidth = 6
          ctx.stroke()
          ctx.globalCompositeOperation = 'source-over'
        }
        ctx.globalAlpha = (0.5 + 0.18 * dens) * dimK
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
    } else {
      // halo suave bajo cada arista (aditivo): las conexiones brillan sobre la tinta
      ctx.globalCompositeOperation = 'lighter'
      ctx.strokeStyle = lime
      for (const e of E > 150 ? [] : this.edges) {
        if (!e.vis || (F && F.edges.has(e.id))) continue
        const a = dimK * Math.min(e.source.a, e.target.a)
        if (a <= 0.01) continue
        ctx.globalAlpha = 0.075 * a
        ctx.lineWidth = 6
        ctx.beginPath(); this._edgePath(ctx, e); ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
      for (const e of this.edges) {
        if (!e.vis || (F && F.edges.has(e.id))) continue
        const a = dimK * Math.min(e.source.a, e.target.a)
        if (a <= 0.01) continue
        if (e.self) {
          ctx.strokeStyle = this._colorOf(e.source)
          ctx.globalAlpha = 0.65 * a
        } else {
          const g = ctx.createLinearGradient(e.source.sx, e.source.sy, e.target.sx, e.target.sy)
          g.addColorStop(0, rgba(this._colorOf(e.source), 0.9))
          g.addColorStop(0.5, rgba(lime, 0.42))
          g.addColorStop(1, rgba(this._colorOf(e.target), 0.9))
          ctx.strokeStyle = g
          ctx.globalAlpha = a
        }
        ctx.lineWidth = 1.4
        ctx.beginPath()
        this._edgePath(ctx, e)
        ctx.stroke()
      }
    }
    if (F) {
      ctx.globalCompositeOperation = 'lighter'
      for (const e of this.edges) {
        if (!e.vis || !F.edges.has(e.id)) continue
        const sel = e.id === selEdge
        ctx.beginPath()
        this._edgePath(ctx, e)
        ctx.strokeStyle = lime
        ctx.globalAlpha = 0.14 * fm
        ctx.lineWidth = sel ? 8 : 5
        ctx.stroke()
        ctx.globalAlpha = 0.45 + 0.5 * fm
        ctx.lineWidth = sel ? 2.4 : 1.2 + 0.5 * fm
        ctx.stroke()
      }
      ctx.globalCompositeOperation = 'source-over'
    }
    ctx.globalAlpha = 1
  }

  // Halo de `px` píxeles de dispositivo, cuantizado a cuartos de octava: se dibuja 1:1 (escalar un sprite en
  // cada nodo cuesta ~4 veces más con rasterizado por software)
  _glowSprite(color, px = 64) {
    const D = Math.max(8, Math.round(Math.pow(2, Math.round(Math.log2(px) * 4) / 4)))
    const key = `${color}|${D}`
    let c = this.glow.get(key)
    if (c) return c
    c = document.createElement('canvas')
    c.width = c.height = D
    const g = c.getContext('2d')
    const h = D / 2
    const gr = g.createRadialGradient(h, h, 0, h, h, h)
    gr.addColorStop(0, rgba(color, 0.95))
    gr.addColorStop(0.2, rgba(color, 0.5))
    gr.addColorStop(0.5, rgba(color, 0.13))
    gr.addColorStop(1, rgba(color, 0))
    g.fillStyle = gr
    g.fillRect(0, 0, D, D)
    this.glow.set(key, c)
    return c
  }

  // pinta un halo centrado en (x, y) CSS, de radio r CSS, sin escalar el sprite
  _blitGlow(ctx, color, x, y, r) {
    const d = this.dpr
    const spr = this._glowSprite(color, r * 2 * d)
    const D = spr.width
    ctx.drawImage(spr, Math.round(x * d - D / 2), Math.round(y * d - D / 2))
  }

  _drawNodes(ctx, F, fm) {
    const { dpr, tk } = this
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, this.nodeLayer.width, this.nodeLayer.height)
    const N = this.nodes.length
    const big = N > 300
    const ink = tk['--ink-950']
    const dimOf = (n) => (F && !F.nodes.has(n.id) ? 1 - 0.8 * fm : 1)
    // halo (aditivo). En grafos grandes, solo los más conectados y el foco: el resto no se distinguiría y cuesta.
    ctx.globalCompositeOperation = 'lighter'
    for (const n of this.nodes) {
      if (!n.vis) continue
      const inF = F && F.nodes.has(n.id)
      if (big && n.rank > 90 && !inF) continue
      const boost = inF ? 1 + 0.5 * fm : 1
      const ga = (big ? 0.26 : 0.36) * (n.degree ? 1 : 0.55) * n.a * dimOf(n) * boost
      if (ga < 0.02) continue
      ctx.globalAlpha = Math.min(1, ga)
      this._blitGlow(ctx, this._colorOf(n), n.sx, n.sy, n.sr * (big ? 2.4 : 3) + 4)
    }
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1

    if (big) {
      // un trazado por estilo (y por estado de foco) en vez de un fill por nodo
      const groups = new Map()
      for (const n of this.nodes) {
        if (!n.vis) continue
        const alpha = n.a * dimOf(n) * (n.quiet && !(F && F.nodes.has(n.id)) ? 0.62 : 1)
        if (alpha <= 0.01) continue
        const key = `${n.style.shape}|${n.style.fill}|${n.style.stroke || ''}|${Math.round(alpha * 10)}`
        let g = groups.get(key)
        if (!g) groups.set(key, (g = { st: n.style, alpha: Math.round(alpha * 10) / 10, path: new Path2D() }))
        const r = n.sr * dpr
        g.path.addPath(this.paths[n.style.shape] || this.paths.circle, new DOMMatrix([r, 0, 0, r, n.sx * dpr, n.sy * dpr]))
      }
      const ordered = [...groups.values()].sort((a, b) => a.alpha - b.alpha)
      for (const g of ordered) {
        ctx.globalAlpha = g.alpha
        ctx.fillStyle = tk[g.st.fill]
        ctx.fill(g.path)
        if (g.st.stroke) {
          ctx.lineWidth = 1.6 * dpr
          ctx.strokeStyle = tk[g.st.stroke]
          ctx.stroke(g.path)
        }
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.globalAlpha = 1
      return
    }

    // formas: primero lo atenuado, encima lo que está en foco
    const draw = (n) => {
      const st = n.style
      const alpha = n.a * dimOf(n)
      if (alpha <= 0.01) return
      ctx.globalAlpha = alpha
      ctx.setTransform(dpr * n.sr, 0, 0, dpr * n.sr, dpr * n.sx, dpr * n.sy)
      const path = this.paths[st.shape] || this.paths.circle
      ctx.fillStyle = tk[st.fill]
      ctx.fill(path)
      if (st.stroke) {
        ctx.lineWidth = Math.min(0.5, 2 / n.sr)
        ctx.strokeStyle = tk[st.stroke]
        ctx.stroke(path)
      } else if (n.sr > 3) {
        ctx.lineWidth = 1.5 / n.sr
        ctx.strokeStyle = ink
        ctx.stroke(path)
      }
      if (n.degree > 0) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
        ctx.beginPath()
        ctx.arc(n.sx, n.sy, n.sr * 1.25 + 4, 0, TAU)
        ctx.lineWidth = 1
        ctx.strokeStyle = this._colorOf(n)
        ctx.globalAlpha = alpha * (F && F.nodes.has(n.id) ? 0.3 + 0.3 * fm : 0.3)
        ctx.stroke()
      }
    }
    if (F) {
      for (const n of this.nodes) if (n.vis && !F.nodes.has(n.id)) draw(n)
      for (const n of this.nodes) if (n.vis && F.nodes.has(n.id)) draw(n)
    } else {
      for (const n of this.nodes) if (n.vis) draw(n)
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.globalAlpha = 1
  }

  // ── Etiquetas ────────────────────────────────────────────────────────────
  _wrap(text, font, maxW) {
    const key = `${font}|${maxW}|${text}`
    let info = this.textCache.get(key)
    if (info) return info
    const m = this.mctx
    m.font = font
    const width = (s) => m.measureText(s).width
    const lines = []
    let cur = ''
    for (const w of String(text).split(/\s+/).filter(Boolean)) {
      const test = cur ? `${cur} ${w}` : w
      if (width(test) <= maxW) { cur = test; continue }
      if (cur) lines.push(cur)
      if (width(w) <= maxW) { cur = w; continue }
      // palabra más larga que la línea (o texto sin espacios, como el chino): se parte por caracteres
      let chunk = ''
      for (const ch of w) {
        if (chunk && width(chunk + ch) > maxW) { lines.push(chunk); chunk = ch } else chunk += ch
      }
      cur = chunk
    }
    if (cur) lines.push(cur)
    if (!lines.length) lines.push(String(text))
    const widths = lines.map(width)
    info = { lines, widths, w: Math.ceil(Math.max(...widths)), font }
    this.textCache.set(key, info)
    return info
  }

  _labelInfo(n) {
    const font = n.hub ? `600 13px ${FONT_SANS}` : `500 12px ${FONT_SANS}`
    const info = this._wrap(n.name, font, LABEL_MAX_W)
    if (info.lh == null) { info.lh = n.hub ? 16 : 15; info.h = info.lines.length * info.lh }
    return info
  }

  _prefDir(dx, dy) {
    const d = Math.hypot(dx, dy)
    if (d < 24) return 'b'
    if (Math.abs(dx) / d > 0.72) return dx > 0 ? 'r' : 'l'
    return dy > 0 ? 'b' : 't'
  }

  _labelBoxAt(x, y, ext, info, dir) {
    const w = info.w + 4, h = info.h + 2, gap = 4
    let x0, y0, align
    if (dir === 'b') { x0 = x - w / 2; y0 = y + ext + gap; align = 'center' }
    else if (dir === 't') { x0 = x - w / 2; y0 = y - ext - gap - h; align = 'center' }
    else if (dir === 'r') { x0 = x + ext + gap; y0 = y - h / 2; align = 'left' }
    else { x0 = x - ext - gap - w; y0 = y - h / 2; align = 'right' }
    return { x0, y0, x1: x0 + w, y1: y0 + h, dir, align }
  }

  _drawLabels(ctx, F, fm) {
    const { W, H, tk, t } = this
    const N = this.nodes.length
    const grid = new BoxGrid(48)
    this.labelRects = []   // dónde hay texto: la composición solo copia esos rectángulos de la capa (no el lienzo entero)
    const focusOnly = F && fm > 0.5
    // la franja de los controles de arriba (búsqueda, interruptor) también estorba: nada se coloca debajo
    if (this.insets.top > 8) grid.add({ x0: 0, y0: 0, x1: W, y1: this.insets.top - 6, owner: '__ui__' })
    for (const n of this.nodes) {
      if (!n.vis || n.a < 0.5) continue
      if (focusOnly && !F.nodes.has(n.id)) continue   // los atenuados no estorban a las etiquetas del foco
      const r = n.sr * 1.25 + 1
      grid.add({ x0: n.sx - r, y0: n.sy - r, x1: n.sx + r, y1: n.sy + r, owner: n.id })
    }
    const forced = new Set()
    if (this.selected?.kind === 'node') forced.add(this.selected.id)
    if (this.hoverId) forced.add(this.hoverId)
    if (this.previewId) forced.add(this.previewId)
    if (this.dragging) forced.add(this.dragging.id)
    if (F && F.center) forced.add(F.center)
    const showAll = N <= 80
    const budget = showAll ? Infinity : clamp((W * H) / 7000, 12, 140)
    const cs = this.cScreen
    const cream = tk['--cream-100'], gray = tk['--gray-300'], lime = tk['--lime-500'], ink = tk['--ink-950']
    const selId = this.selected?.kind === 'node' ? this.selected.id : null
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.textBaseline = 'top'
    ctx.lineJoin = 'round'
    let free = 0

    // mode 0: solo si hay hueco · 1 (blando): el hueco con menos solape, si no tapa más de un tercio · 2 (duro): siempre
    const place = (n, mode) => {
      const isForced = mode > 0
      const info = this._labelInfo(n)
      const ext = n.sr * 1.25 + 2
      const pref = this._prefDir(n.sx - cs.x, n.sy - cs.y)
      const dirs = [...new Set([this.entry ? null : n.labelPos, pref, 'b', 't', 'r', 'l'].filter(Boolean))]
      let box = null, best = null, bestA = Infinity
      for (const dir of dirs) {
        const b = this._labelBoxAt(n.sx, n.sy, ext, info, dir)
        b.owner = n.id
        if (mode < 2 && (b.x0 < 2 || b.x1 > W - 2 || b.y0 < 2 || b.y1 > H - 2)) continue
        if (!grid.hits(b, n.id)) { box = b; break }
        if (isForced) { const a = grid.overlap(b, n.id); if (a < bestA) { bestA = a; best = b } }
      }
      let crowded = false
      if (!box && best && (mode === 2 || bestA < (best.x1 - best.x0) * (best.y1 - best.y0) * 0.33)) { box = best; crowded = bestA > 0 }
      if (!box && mode === 2) { box = this._labelBoxAt(n.sx, n.sy, ext, info, dirs[0]); box.owner = n.id; crowded = true }
      if (!box) return false
      grid.add(box)
      if (!this.entry) n.labelPos = box.dir
      const la = clamp((n.ap - 0.55) / 0.45, 0, 1) * (F && !F.nodes.has(n.id) ? 1 - 2 * fm : 1)
      if (la <= 0.02) return true
      this.labelRects.push([box.x0 - 8, box.y0 - 6, box.x1 + 8, box.y1 + 6])
      ctx.globalAlpha = la
      if (crowded) {
        // sobre otros nodos: píldora de tinta detrás para que se lea
        ctx.fillStyle = rgba(ink, 0.82)
        ctx.beginPath()
        ctx.roundRect(box.x0 - 3, box.y0 - 1, box.x1 - box.x0 + 6, box.y1 - box.y0 + 2, 5)
        ctx.fill()
      }
      ctx.font = info.font
      ctx.lineWidth = 4
      ctx.strokeStyle = ink
      ctx.fillStyle = n.id === selId ? lime : (n.hub || (F && F.nodes.has(n.id) && fm > 0.5) || isForced ? cream : gray)
      for (let i = 0; i < info.lines.length; i++) {
        const lw = info.widths[i]
        const lx = box.align === 'center' ? box.x0 + (box.x1 - box.x0 - lw) / 2 : box.align === 'right' ? box.x1 - 2 - lw : box.x0 + 2
        const ly = box.y0 + 1 + i * info.lh
        ctx.strokeText(info.lines[i], lx, ly)
        ctx.fillText(info.lines[i], lx, ly)
      }
      return true
    }

    // Etiquetas de relación (interruptor). Se prueban varios puntos de la curva y, si ninguno está libre,
    // la de la relación bajo el ratón o seleccionada se pinta igualmente.
    const E = this.edges.length
    const selEdge = this.selected?.kind === 'edge' ? this.selected.id : null
    const efont = `500 12px ${FONT_SANS}`
    const placeEdge = (e, mode) => {
      const forcedE = mode > 0
      if (!e.vis || e.p < 1) return
      const inF = F && F.edges.has(e.id)
      const text = e.self ? this.strings.selfLoop(e.count) : this.strings.relation(e.name)
      const info = this._wrap(text, efont, EDGE_LABEL_MAX_W)
      const lh = 15, h = info.lines.length * lh + 2, w = info.w + 6
      const cands = []
      if (e.self) cands.push([e.lcx + e.lr + 6 + w / 2, e.lcy - e.lr * 0.3])
      else {
        const nx = -(e.target.sy - e.source.sy) / e.len, ny = (e.target.sx - e.source.sx) / e.len
        for (const u of [0.5, 0.4, 0.6, 0.3, 0.7]) {
          const p = this._curvePoint(e, u), px = p.x, py = p.y
          for (const off of [0, h / 2 + 4, -(h / 2 + 4), h + 10, -(h + 10)]) cands.push([px + nx * off, py + ny * off])
        }
      }
      let b = null, best = null, bestA = Infinity
      for (const [mx, my] of cands) {
        const c = { x0: mx - w / 2, y0: my - h / 2, x1: mx + w / 2, y1: my + h / 2, owner: e.id, mx }
        if (c.x0 < 2 || c.x1 > W - 2 || c.y0 < 2 || c.y1 > H - 2) continue
        if (!grid.hits(c, e.id)) { b = c; break }
        if (forcedE) { const a = grid.overlap(c, e.id); if (a < bestA) { bestA = a; best = c } }
      }
      if (!b && best && (mode === 2 || bestA < w * h * 0.33)) b = best
      if (!b && mode === 2) { const [mx, my] = cands[0]; b = { x0: mx - w / 2, y0: my - h / 2, x1: mx + w / 2, y1: my + h / 2, owner: e.id, mx } }
      if (!b) return
      grid.add(b)
      ctx.globalAlpha = inF ? 1 : 1 - (F ? Math.min(1, 2 * fm) : 0)
      if (ctx.globalAlpha <= 0.02) return
      this.labelRects.push([b.x0 - 8, b.y0 - 6, b.x1 + 8, b.y1 + 6])
      ctx.font = efont
      ctx.lineWidth = 4
      ctx.strokeStyle = ink
      ctx.fillStyle = inF && fm > 0.5 ? lime : tk['--gray-500']
      for (let i = 0; i < info.lines.length; i++) {
        const lx = b.mx - info.widths[i] / 2, ly = b.y0 + 1 + i * lh
        ctx.strokeText(info.lines[i], lx, ly)
        ctx.fillText(info.lines[i], lx, ly)
      }
    }

    // 1) las forzadas (seleccionada, bajo el ratón, centro del foco)
    const order = this.model?.byPriority || this.nodes
    for (const n of order) if (forced.has(n.id) && n.vis) place(n, 2)
    if (focusOnly) {
      // 2) en foco: primero cómo se conecta (sus relaciones), luego con quién
      const few = F.edges.size <= 8
      const hardE = (e) => e.id === selEdge || e.id === this.hoverEdgeId
      if (this.showEdgeLabels) for (const e of this.edges) if (F.edges.has(e.id) && hardE(e)) placeEdge(e, 2)
      for (const n of order) if (!forced.has(n.id) && n.vis && F.nodes.has(n.id) && n.a > 0.5) place(n, F.nodes.size <= 14 ? 1 : 0)
      if (this.showEdgeLabels && few) for (const e of this.edges) if (F.edges.has(e.id) && !hardE(e)) placeEdge(e, 1)
    } else {
      // 2) por prioridad (los más conectados nunca se esconden), con presupuesto en grafos grandes
      // las principales (más conectadas) siempre, aunque tengan que apoyarse sobre nodos pequeños
      const mainCount = showAll ? 0 : Math.min(10, Math.ceil(N / 30))
      for (const n of order) {
        if (forced.has(n.id) || !n.vis || n.a < 0.5) continue
        if (free >= budget) break
        if (!showAll && !(n.rank < 12 || n.sr >= 5.5)) continue
        if (place(n, n.rank < mainCount && n.degree >= 3 ? 2 : 0)) free++
      }
      if (this.showEdgeLabels) {
        for (const e of this.edges) {
          const inF = F && F.edges.has(e.id)
          if (!inF && !(E <= 60 || t.k >= 1.3)) continue
          placeEdge(e, e.id === selEdge || e.id === this.hoverEdgeId ? 2 : 0)
        }
      }
    }
    ctx.globalAlpha = 1
  }

  // ── Capa viva ────────────────────────────────────────────────────────────
  // Orden: aristas → nodos → [flujo, latido, barrido, cometas, destellos] → etiquetas → anillos y ondas.
  // La animación va POR DELANTE de los nodos (por detrás la tapaban) y por detrás del texto.
  _composite(now, dt) {
    const ctx = this.ctx, d = this.dpr
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
    ctx.drawImage(this.edgeLayer, 0, 0)
    ctx.drawImage(this.nodeLayer, 0, 0)
    if (!this.reduced) {
      const f0 = performance.now()
      ctx.setTransform(d, 0, 0, d, 0, 0)
      this._flow(ctx, dt)
      this._bloom(ctx, now)
      this._sweepFx(ctx, now)
      this._pulses(ctx, now, dt)
      this._flashFx(ctx, now)
      this._fxAdapt(performance.now() - f0)
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    this._blitLabels(ctx)
    ctx.setTransform(d, 0, 0, d, 0, 0)
    this._overlays(ctx, now, dt)
  }

  // Las etiquetas ocupan una fracción mínima de la pantalla: se copian solo sus rectángulos (volcar el lienzo
  // entero cada fotograma costaba, sin GPU, más que toda la animación).
  _blitLabels(ctx) {
    const rects = this.labelRects
    if (!rects || !rects.length) return
    const d = this.dpr, cw = this.canvas.width, ch = this.canvas.height
    const L = this.labelLayer
    for (const r of rects) {
      const x = Math.max(0, Math.floor(r[0] * d)), y = Math.max(0, Math.floor(r[1] * d))
      const w = Math.min(cw, Math.ceil(r[2] * d)) - x, h = Math.min(ch, Math.ceil(r[3] * d)) - y
      if (w > 0 && h > 0) ctx.drawImage(L, x, y, w, h, x, y, w, h)
    }
  }

  // Sin GPU la animación se adelgaza sola: cada 30 fotogramas, si cuesta de media más de 6 ms, baja a la mitad de
  // partículas; si sobra tiempo de forma sostenida, vuelve a subir.
  _fxAdapt(ms) {
    this._fxN++; this._fxSum += ms
    if (this._fxN < 30) return
    const avg = this._fxSum / this._fxN
    this._fxN = 0; this._fxSum = 0
    if (avg > 6 && this.fxLevel > 0.25) { this.fxLevel /= 2; this._fxCalm = 0 }
    else if (avg < 1.8 && this.fxLevel < 1) { if (++this._fxCalm >= 6) { this.fxLevel *= 2; this._fxCalm = 0 } }
    else this._fxCalm = 0
  }

  // Una partícula recorre cada relación de origen a destino (alguna, al revés): los enlaces se ven vivos aunque
  // el grafo esté quieto. Entre los bordes de los dos nodos, para que no «atraviesen» las formas. En foco, las
  // relaciones del vecindario llevan partículas más grandes y rápidas; el resto se atenúa.
  _flow(ctx, dt) {
    const E = this.edges
    if (!E.length) return
    if (this._busy && E.length > 900) return   // grafo denso y escena repintándose entera (arrastre, zoom): las partículas esperan
    const F = this.focus, fm = F ? this.focusMix : 0
    const stride = (this.fxLevel >= 1 ? 1 : this.fxLevel >= 0.5 ? 2 : 4) * (this._busy ? 2 : 1)
    const lime = this.tk['--lime-500'], core = this.tk['--lime-50']
    // aditiva: es lo que deja ver la red POR ENCIMA de los nodos; en grafos densos las estelas son más finas y tenues
    // para que, sumadas en el núcleo, no lo laven
    const dense = E.length > 900 ? 0.72 : 1
    ctx.globalCompositeOperation = 'lighter'
    ctx.lineCap = 'round'
    for (let pass = 0; pass < (F ? 2 : 1); pass++) {
      const hot = pass === 1
      const tails = new Path2D()
      ctx.beginPath()
      let any = false
      for (let i = 0; i < E.length; i += hot ? 1 : stride) {
        const e = E[i]
        if (!e.vis || e.p < 1 || e.self) continue
        if (hot !== !!(F && F.edges.has(e.id))) continue
        if (e.fu === undefined) { const h = fnv(String(e.id)); e.fu = (h % 1000) / 1000; e.frev = ((h >>> 10) % 5) === 0 }
        const len = Math.max(40, e.len)
        e.fu = (e.fu + dt * clamp((hot ? 110 : 62) / len, 0.08, 0.7)) % 1
        const s = e.source, t = e.target
        const u0 = Math.min(0.4, (s.sr + 3) / len), u1 = 1 - Math.min(0.4, (t.sr + 3) / len)
        const q = u0 + e.fu * (u1 - u0)
        const u = e.frev ? 1 - q : q
        const pt = this._curvePoint(e, u)
        const hx = pt.x, hy = pt.y
        const uT = clamp(e.frev ? u + (hot ? 24 : 15) / len : u - (hot ? 24 : 15) / len, 0, 1)
        const p2 = this._curvePoint(e, uT)
        tails.moveTo(p2.x, p2.y); tails.lineTo(hx, hy)
        const r = hot ? 2.2 : 1.3
        ctx.moveTo(hx + r, hy); ctx.arc(hx, hy, r, 0, TAU)
        any = true
      }
      if (!any) continue
      ctx.globalAlpha = hot ? 0.95 : 0.5 * dense * (1 - 0.75 * fm)
      ctx.strokeStyle = lime
      ctx.lineWidth = hot ? 2.2 : 1.2 * dense
      ctx.stroke(tails)
      ctx.globalAlpha = hot ? 1 : 0.85 * (1 - 0.7 * fm)
      ctx.fillStyle = core
      ctx.fill()
    }
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }

  // Los nodos más conectados laten: un halo que respira, cada uno a su fase.
  _bloom(ctx, now) {
    const order = this.model?.byPriority
    if (!order || !order.length) return
    if (this._busy && this.edges.length > 900) return
    const F = this.focus, fm = F ? this.focusMix : 0
    const K = Math.min(order.length, Math.max(5, Math.round(this.nodes.length * 0.05)), this.edges.length > 900 ? 14 : 36)
    const lime = this.tk['--lime-500']
    ctx.globalCompositeOperation = 'lighter'
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    for (let i = 0; i < K; i++) {
      const n = order[i]
      if (!n.vis || n.degree < 2) continue
      if (n._ph === undefined) n._ph = (fnv(String(n.id)) % 628) / 100
      const w = 0.5 + 0.5 * Math.sin(now / 760 + n._ph)
      const dim = F && !F.nodes.has(n.id) ? 1 - 0.85 * fm : 1
      ctx.globalAlpha = (0.07 + 0.2 * w) * n.a * dim
      this._blitGlow(ctx, lime, n.sx, n.sy, n.sr * (2.5 + 0.8 * w) + 7)
    }
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }

  // Cada pocos segundos una onda sale del centro y enciende los nodos que cruza (como un sonar). No barre
  // mientras hay un foco o una selección: ahí manda lo que el usuario está mirando.
  _sweepFx(ctx, now) {
    if (!this.sweep) {
      if (this.focus || this.selected || this.entry || this.simActive) return
      if (!this.sweepNext) { this.sweepNext = now + 1800; return }
      if (now < this.sweepNext) return
      const c = this.cScreen || { x: this.W / 2, y: this.H / 2 }
      this.sweep = { t0: now, dur: 3600, cx: c.x, cy: c.y, maxR: Math.hypot(this.W, this.H) * 0.6 }
    }
    const sw = this.sweep
    const u = (now - sw.t0) / sw.dur
    if (u >= 1) { this.sweep = null; this.sweepNext = now + 5200 + Math.random() * 3600; return }
    const R = sw.maxR * (1 - Math.pow(1 - u, 2.2))   // sale deprisa y se frena: una onda que pierde fuerza
    const fade = Math.pow(1 - u, 1.1)
    const lime = this.tk['--lime-500']
    ctx.globalCompositeOperation = 'lighter'
    ctx.strokeStyle = lime
    ctx.globalAlpha = 0.06 * fade
    ctx.lineWidth = 22
    ctx.beginPath(); ctx.arc(sw.cx, sw.cy, R, 0, TAU); ctx.stroke()
    ctx.globalAlpha = 0.3 * fade
    ctx.lineWidth = 1.4
    ctx.beginPath(); ctx.arc(sw.cx, sw.cy, R, 0, TAU); ctx.stroke()
    const band = 34 + 20 * u
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    for (const n of this.nodes) {
      if (!n.vis) continue
      const dd = Math.abs(Math.hypot(n.sx - sw.cx, n.sy - sw.cy) - R)
      if (dd > band) continue
      const k = 1 - dd / band
      ctx.globalAlpha = 0.75 * k * k * fade * n.a
      this._blitGlow(ctx, lime, n.sx, n.sy, n.sr * 2.4 + 7)
    }
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }

  // Destello al llegar un cometa a un nodo (y, suelto, en nodos al azar)
  _flashFx(ctx, now) {
    if (!this.flashes.length) return
    const lime = this.tk['--lime-500']
    ctx.globalCompositeOperation = 'lighter'
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    const keep = []
    for (const f of this.flashes) {
      const u = (now - f.t0) / f.dur
      if (u >= 1) continue
      keep.push(f)
      const n = f.n
      if (u < 0 || !n.vis) continue
      ctx.globalAlpha = Math.min(1, f.a * Math.pow(1 - u, 1.6) * n.a)
      this._blitGlow(ctx, lime, n.sx, n.sy, n.sr * (f.r + 1.4 * easeOutCubic(u)) + 6)
    }
    this.flashes = keep
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
  }

  // Un cometa llega a un nodo: destello y, con probabilidad decreciente, lanza otros por sus demás relaciones
  // (hasta 3 generaciones): la información «se contagia» por la red.
  _arrive(nid, gen, now, live) {
    const n = this.nodeById.get(nid)
    if (!n || !n.vis) return
    if (this.flashes.length < 160) this.flashes.push({ n, t0: now, dur: 640, a: gen === 0 ? 0.9 : 0.7, r: 2.1 })
    if (live) this._ping(nid, now)
    if (gen >= 3 || this.pulses.length >= 130 || Math.random() > 0.64 - gen * 0.17) return
    const pool = n.links.filter(e => !e.self && e.vis && e.p >= 1)
    const k = pool.length > 1 && Math.random() < 0.35 ? 2 : 1
    for (let i = 0; i < k && pool.length; i++) {
      const e = pool.splice((Math.random() * pool.length) | 0, 1)[0]
      this._spawnPulse(now, null, { e, rev: e.tid === nid, gen: gen + 1 })
    }
  }

  _spawnPulse(now, pool, opts = null) {
    const speed = this.live ? 170 : 130
    if (opts) {
      const e = opts.e
      this.pulses.push({ e, t0: now, dur: clamp(e.len / speed, this.live ? 0.9 : 0.7, 2.6) * 1000, rev: opts.rev, live: this.live, gen: opts.gen || 0 })
      return
    }
    const E = pool || this.edges
    if (!E.length) return
    for (let tries = 0; tries < 6; tries++) {
      const e = E[(Math.random() * E.length) | 0]
      if (!e || !e.vis || e.p < 1) continue
      this.pulses.push({ e, t0: now, dur: clamp(e.len / speed, this.live ? 0.9 : 0.7, 2.6) * 1000, rev: !e.self && Math.random() < 0.2, live: this.live, gen: 0 })
      return
    }
  }

  _ripple(id, now) {
    if (this.reduced || this.effects.length > 240) return
    this.effects.push({ id, t0: now, dur: 1100, from: 3, grow: 40, a: 0.9, w: 1.6 })
    this.effects.push({ id, t0: now + 240, dur: 1100, from: 3, grow: 40, a: 0.6, w: 1.2 })
  }

  _ping(id, now, a = 0.7) {
    if (this.reduced || this.effects.length > 240) return
    this.effects.push({ id, t0: now, dur: 700, from: 1, grow: 18, a, w: 1.4 })
  }

  _pulses(ctx, now, dt) {
    const E = this.edges
    const live = this.live
    const F = this.focus
    if (E.length) {
      // en vivo (construyendo o simulando) la memoria se escribe: muchos más cometas que en reposo
      const rate = live ? Math.min(26, 4 + E.length * 0.6) : Math.min(14, 1.2 + E.length * 0.05)
      const cap = live ? 170 : 110
      this.spawnAcc += dt * rate * (this.fxLevel < 1 ? Math.max(0.5, this.fxLevel) : 1)
      while (this.spawnAcc >= 1) { this.spawnAcc -= 1; if (this.pulses.length < cap) this._spawnPulse(now) }
      // el vecindario bajo el ratón (o seleccionado) late más: la conexión se ve viva
      if (F && F.edges.size) {
        this.focusAcc += dt * Math.min(6, 2 + F.edges.size * 0.5)
        if (this.focusAcc >= 1) {
          const pool = []
          for (const id of F.edges) { const e = this.edgeById.get(id); if (e) pool.push(e) }
          while (this.focusAcc >= 1) { this.focusAcc -= 1; if (this.pulses.length < cap + 30) this._spawnPulse(now, pool) }
        }
      } else this.focusAcc = 0
    }
    // memoria actualizándose: «escrituras» sueltas en nodos al azar (también en los que aún no tienen relaciones)
    if (live && this.nodes.length) {
      this.pingAcc += dt * Math.min(6, 1.5 + this.nodes.length * 0.05)
      while (this.pingAcc >= 1) {
        this.pingAcc -= 1
        const n = this.nodes[(Math.random() * this.nodes.length) | 0]
        if (n && n.vis) this._ping(n.id, now, 0.75)
      }
    }
    // centelleo: nodos al azar se encienden un instante, para que ni el reposo esté quieto
    if (this.nodes.length) {
      this.twinkleAcc += dt * Math.min(5, 0.8 + this.nodes.length * 0.01)
      while (this.twinkleAcc >= 1) {
        this.twinkleAcc -= 1
        const n = this.nodes[(Math.random() * this.nodes.length) | 0]
        if (n && n.vis && n.degree && this.flashes.length < 160) this.flashes.push({ n, t0: now, dur: 900, a: 0.5, r: 1.8 })
      }
    }
    if (!this.pulses.length) return
    const lime = this.tk['--lime-500'], core = this.tk['--lime-50']
    const fm = F ? this.focusMix : 0
    ctx.globalCompositeOperation = 'lighter'
    ctx.lineCap = 'round'
    const keep = []
    const arrived = []
    for (const p of this.pulses) {
      const e = p.e
      const u = (now - p.t0) / p.dur
      if (u >= 1) { arrived.push(p); continue }
      keep.push(p)
      if (!e.vis || e.p < 1 || u < 0) continue
      const dim = F && !F.edges.has(e.id) ? 1 - 0.8 * fm : 1
      const pos = easeInOut(u)
      const tail = (p.live ? 80 : 58) / Math.max(30, e.len)
      // cola de cometa: tramos cada vez más finos y transparentes
      let prev = null
      for (let i = 0; i <= 9; i++) {
        const q = pos - (tail * i) / 9
        if (q < 0) break
        const pt = this._curvePoint(e, p.rev ? 1 - q : q)
        if (prev) {
          ctx.globalAlpha = dim * (p.live ? 0.85 : 0.7) * (1 - i / 10)
          ctx.strokeStyle = lime
          ctx.lineWidth = (p.live ? 3 : 2.5) * (1 - i / 11)
          ctx.beginPath(); ctx.moveTo(prev[0], prev[1]); ctx.lineTo(pt.x, pt.y); ctx.stroke()
        }
        prev = [pt.x, pt.y]
      }
      const h = this._curvePoint(e, p.rev ? 1 - pos : pos)
      const hx = h.x, hy = h.y
      ctx.globalAlpha = dim * (p.live ? 1 : 0.9)
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      this._blitGlow(ctx, lime, hx, hy, p.live ? 15 : 12)
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
      ctx.fillStyle = core
      ctx.beginPath(); ctx.arc(hx, hy, p.live ? 2.3 : 1.9, 0, TAU); ctx.fill()
    }
    this.pulses = keep
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    // al llegar: destello y, a veces, otro cometa por las demás relaciones del nodo
    for (const p of arrived) this._arrive(p.rev ? p.e.sid : p.e.tid, p.gen || 0, now, p.live)
  }

  _overlays(ctx, now) {
    const lime = this.tk['--lime-500'], cream = this.tk['--cream-100']
    if (this.effects.length) {
      const keep = []
      ctx.strokeStyle = lime
      for (const fx of this.effects) {
        const u = (now - fx.t0) / fx.dur
        if (u >= 1) continue
        keep.push(fx)
        if (u < 0) continue
        const n = this.nodeById.get(fx.id)
        if (!n || !n.vis) continue
        ctx.globalAlpha = Math.pow(1 - u, 1.4) * fx.a
        ctx.lineWidth = fx.w
        ctx.beginPath()
        ctx.arc(n.sx, n.sy, n.sr * 1.15 + fx.from + fx.grow * easeOutCubic(u), 0, TAU)
        ctx.stroke()
      }
      this.effects = keep
    }
    const sel = this.selected?.kind === 'node' ? this.nodeById.get(this.selected.id) : null
    if (sel && sel.vis) {
      const r = sel.sr * 1.25
      ctx.globalAlpha = 1
      ctx.strokeStyle = lime
      ctx.lineWidth = 2
      ctx.beginPath(); ctx.arc(sel.sx, sel.sy, r + 3, 0, TAU); ctx.stroke()
      ctx.globalAlpha = 0.75
      ctx.lineWidth = 1.25
      ctx.setLineDash([3, 5])
      ctx.lineDashOffset = this.reduced ? 0 : -now * 0.012
      ctx.beginPath(); ctx.arc(sel.sx, sel.sy, r + 8.5, 0, TAU); ctx.stroke()
      ctx.setLineDash([])
    }
    const hov = this.hoverId && this.hoverId !== sel?.id ? this.nodeById.get(this.hoverId) : null
    if (hov && hov.vis) {
      ctx.globalAlpha = 0.9
      ctx.strokeStyle = cream
      ctx.lineWidth = 1.5
      ctx.beginPath(); ctx.arc(hov.sx, hov.sy, hov.sr * 1.25 + 3, 0, TAU); ctx.stroke()
    }
    ctx.globalAlpha = 1
  }
}
