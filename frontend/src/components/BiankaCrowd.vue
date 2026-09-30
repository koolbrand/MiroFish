<template>
  <!-- Muro de Biankas en pixel art: cada una es una persona simulada que opina
       (lima a favor, blanca indecisa, tinta en contra), conversa con sus
       vecinas y cambia de idea. Decorativo: el contenido no depende de él. -->
  <div ref="root" class="bianka-crowd" aria-hidden="true">
    <canvas
      ref="canvas"
      class="crowd-canvas"
      :class="{ 'is-hovering': hovering }"
      @click="onClick"
    ></canvas>

    <div
      v-for="b in bubbles"
      :key="b.id"
      :ref="el => setBubbleEl(b.id, el)"
      class="crowd-bubble"
      :class="[`is-${b.bucket}`, `to-${b.side}`, `kind-${b.kind}`, `dir-${b.dir}`, { 'is-stacked': b.stacked }]"
      :style="{ maxWidth: `${b.width}px` }"
    >
      <span class="crowd-bubble-who">
        <i class="swatch" :class="`is-${b.bucket}`"></i>
        <span class="who-text">{{ b.who }}</span>
        <span class="who-tag">{{ b.tag }}</span>
      </span>
      <span class="crowd-bubble-text">{{ b.text }}</span>
    </div>

    <div ref="readout" class="crowd-readout" :style="{ bottom: `${bottomInset + 24}px` }">
      <div class="readout-head">
        <span>{{ $t('home.crowdCaption') }}</span>
        <span class="readout-round">{{ $t('home.crowdRound') }} {{ String(round).padStart(2, '0') }}/{{ ROUNDS }}</span>
      </div>
      <div class="readout-event"><span class="event-tag">{{ $t('home.crowdEventTag') }}</span>{{ eventLabel || '—' }}</div>
      <div class="readout-bar">
        <span class="seg is-favor" :style="{ width: `${stats.favor}%` }"></span>
        <span class="seg is-undecided" :style="{ width: `${stats.undecided}%` }"></span>
        <span class="seg is-against" :style="{ width: `${stats.against}%` }"></span>
      </div>
      <div class="readout-legend">
        <span><i class="swatch is-favor"></i>{{ $t('home.crowdFor') }} <b>{{ stats.favor }} %</b></span>
        <span><i class="swatch is-undecided"></i>{{ $t('home.crowdUndecided') }} <b>{{ stats.undecided }} %</b></span>
        <span><i class="swatch is-against"></i>{{ $t('home.crowdAgainst') }} <b>{{ stats.against }} %</b></span>
      </div>
      <div class="readout-hint">{{ $t('home.crowdHint') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  bucketOf, rand, pick, gauss, randomLean, initialOpinion, makeLook, drawBianka, PAL,
} from '../lib/biankaSprite'

const props = defineProps({
  // Tarjeta central: nadie «habla» debajo de ella ni le pone bocadillos encima.
  avoidEl: { type: Object, default: null },
  // Alto (px) de la parte inferior que tapa el formulario que monta sobre la portada.
  bottomInset: { type: Number, default: 0 },
  // Alto (px) reservado arriba para la barra de navegación flotante: nadie habla ahí debajo.
  topInset: { type: Number, default: 0 },
})

const { t } = useI18n()
// Alto real del marcador: la portada reserva ese hueco bajo la tarjeta (cambia con el idioma y el ancho).
const emit = defineEmits(['readout'])

const ROUNDS = 10
const ROUND_SECONDS = 6.5
// Un tira y afloja, no una victoria: el lima sube y baja entre ≈ 15 y 45 %, la tinta llega a ≈ 20 % y el
// blanco (indecisos) sigue siendo mayoría casi todo el ensayo (simulado: ver el arco en la conversación).
const VALENCE = [0.35, -0.45, 0.3, -0.4, 0.35, -0.3, 0.32, -0.32, 0.3, 0.25]

const root = ref(null)
const canvas = ref(null)
const readout = ref(null)
const round = ref(0)
const eventLabel = ref('')
const stats = reactive({ favor: 0, undecided: 100, against: 0 })
const bubbles = ref([])
const hovering = ref(false)

let ctx = null
let W = 0, H = 0, dpr = 1, P = 4, CX = 68, RY = 76
let agents = []
let avoid = []
let waves = []
let threads = []
let leaders = []   // hilos de un bocadillo lejano hasta su Bianka
let raf = null, running = false, visible = true, last = 0, now = 0
let roundClock = 0, talkClock = 0.9, statsClock = 0, measureClock = 0, resetClock = -1
let bubbleSeq = 0
let epoch = 0
let seededFor = null   // tarjeta con la que se sembró el muro (la primera fila se alinea con la franja de arriba)
let pointer = null
const bubbleEls = new Map()
let resizeObs = null, interObs = null, readoutObs = null
const reducedMotion = typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Lo último que se ha dicho: en pantalla no se repite la misma frase (ni dos «¡Eso mismo!» a la vez).
const recentTexts = []
const shownTexts = () => new Set([...bubbles.value.map(b => b.text), ...recentTexts])
const say = (keys) => {
  const shown = shownTexts()
  const fresh = keys.filter(k => !shown.has(t(k)))
  const text = t(pick(fresh.length ? fresh : keys))
  recentTexts.push(text)
  if (recentTexts.length > 8) recentTexts.shift()
  return text
}
const bucketLabel = (b) => t({ favor: 'home.crowdFor', undecided: 'home.crowdUndecided', against: 'home.crowdAgainst' }[b])
const setBubbleEl = (id, el) => { if (el) bubbleEls.set(id, el); else bubbleEls.delete(id) }
const seedAgents = () => {
  // Personajes grandes y solapados (una multitud, no una retícula): el píxel crece con la pantalla.
  // Cada Bianka se lee entera (orejas, cara y complemento): unas ~45 a la vista en un escritorio de
  // 1440 px, con un solape moderado (≈ 14 % de lado a lado y ≈ 18 % de arriba abajo).
  P = W >= 1800 ? 8 : W >= 1500 ? 7 : W >= 1000 ? 6 : 5
  CX = 17 * P
  RY = 21 * P
  // La primera fila se coloca de modo que su cara quepa entera en la franja de muro que queda entre la barra y
  // la tarjeta (si no, ahí solo asomarían orejas); el resto de filas cuelga de esa; y la primera columna, con la
  // cara entera dentro del lienzo por la izquierda.
  seededFor = props.avoidEl
  const card = props.avoidEl && avoid.length ? avoid[0] : null
  const stripTop = (props.topInset || 0) + 3
  const stripBottom = card ? card.t - 3 : stripTop + 90
  const yFirst = Math.round(stripTop + Math.max(0, (stripBottom - stripTop - 8 * P) / 2) - 13 * P)
  const xFirst = 10 - 7 * P
  const cols = Math.ceil((W - xFirst) / CX) + 1
  const rows = Math.ceil((H - yFirst) / RY) + 1
  agents = []
  const parts = {}
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      // ningún vecino se parece: ni el mismo aspecto entero ni el mismo gorro, cuerpo o cara que el de
      // la izquierda o los de la fila de arriba (así no hay dos conejos «lisos» seguidos)
      let look = makeLook()
      for (let tries = 0; tries < 16; tries++) {
        const near = [parts[`${row}:${col - 1}`], parts[`${row}:${col - 2}`], parts[`${row - 1}:${col}`], parts[`${row - 1}:${col - 1}`], parts[`${row - 1}:${col + 1}`]].filter(Boolean)
        const clash = near.some(n => n.key === look.key || (look.head && n.head === look.head.id) || (look.body && n.body === look.body.id) || (look.face && n.face === look.face.id))
        if (!clash) break
        look = makeLook()
      }
      parts[`${row}:${col}`] = { key: look.key, head: look.head?.id, body: look.body?.id, face: look.face?.id }
      const x = xFirst + col * CX + (row % 2 ? CX / 2 : 0) + Math.round(rand(-1, 1)) * P
      const y = yFirst + row * RY + (row ? Math.round(rand(-1, 1)) * P : 0)
      agents.push({
        x, y, row, col,
        look,
        mirror: Math.random() < 0.5,
        o: initialOpinion(),
        lean: randomLean(),
        stub: Math.random() ** 2 * 0.8,
        bobPeriod: rand(1.6, 2.8),
        bobPhase: Math.random(),
        nextBlink: rand(0, 5),
        blinkUntil: 0,
        hopAt: -10,
        glyph: null,
        glyphUntil: 0,
        talkUntil: 0,
        lookAt: null,
        lookUntil: 0,
        idleGaze: [0, 0],
        nextIdle: rand(1, 5),
        happyUntil: 0,
        shown: true,          // ¿se le ve la cara? (se mide contra la tarjeta, la barra, el marcador y el formulario)
        born: 0,
        hopAmp: 3,
        nextHop: rand(3, 14),
      })
    }
  }
  // Entrada: una ola desde el centro (< 1 s). Con «reducir movimiento» aparecen ya colocadas.
  const maxD = Math.hypot(W / 2, H / 2) || 1
  for (const a of agents) {
    const d = Math.hypot(a.x + 12.5 * P - W / 2, a.y + 16 * P - H / 2)
    a.born = reducedMotion ? -1 : now + 0.05 + (d / maxD) * 0.85 + Math.random() * 0.12
  }
}

const headOf = (a) => ({ x: a.x + 12.5 * P, y: a.y + 16 * P })

const measureAvoid = () => {
  if (!root.value) return
  const c = root.value.getBoundingClientRect()
  const rel = (r) => ({ l: r.left - c.left, t: r.top - c.top, r: r.right - c.left, b: r.bottom - c.top })
  avoid = []
  if (props.avoidEl) {
    // La tarjeta entra con una animación que la desplaza unos píxeles al principio: se usa su caja de
    // maquetación (sin transformaciones) para que la primera fila del muro se alinee con su posición final.
    const el = props.avoidEl
    avoid.push(el.offsetParent && el.offsetParent === root.value.offsetParent
      ? { l: el.offsetLeft, t: el.offsetTop, r: el.offsetLeft + el.offsetWidth, b: el.offsetTop + el.offsetHeight }
      : rel(el.getBoundingClientRect()))
  }
  if (props.bottomInset) avoid.push({ l: 0, t: H - props.bottomInset, r: W, b: H })
  if (props.topInset) avoid.push({ l: 0, t: 0, r: W, b: props.topInset })
  if (readout.value) avoid.push(rel(readout.value.getBoundingClientRect()))
  for (const a of agents) a.shown = faceShown(a)
}

// La cara (ojos, boca y mejillas) tiene que verse entera frente a lo que tapa el muro y al menos en un 60 %
// dentro del lienzo: una Bianka de la que solo asoman las orejas por encima de la tarjeta no se dibuja
// (en el muro solo hay individuos legibles, no fragmentos), ni cuenta en el marcador ni se puede pulsar.
const faceShown = (a) => {
  const f = { l: a.x + 7 * P, r: a.x + 19 * P, t: a.y + 13 * P, b: a.y + 21 * P }
  if (hitsAvoid(f, 3)) return false
  const iw = Math.min(f.r, W) - Math.max(f.l, 0), ih = Math.min(f.b, H) - Math.max(f.t, 0)
  return iw > 0 && ih > 0 && (iw * ih) / ((f.r - f.l) * (f.b - f.t)) >= 0.6
}
const hitsAvoid = (box, pad) => avoid.some(q => box.l < q.r + pad && box.r > q.l - pad && box.t < q.b + pad && box.b > q.t - pad)
const coveredAt = (x, y) => hitsAvoid({ l: x, r: x, t: y, b: y }, 0)
const headVisible = (a) => a.shown && now >= a.born + 0.3

const resize = () => {
  const el = root.value
  if (!el || !canvas.value) return
  const w = el.clientWidth, h = el.clientHeight
  if (!w || !h) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.value.width = Math.round(w * dpr)
  canvas.value.height = Math.round(h * dpr)
  canvas.value.style.width = `${w}px`
  canvas.value.style.height = `${h}px`
  ctx = canvas.value.getContext('2d')
  const reseed = !agents.length || Math.abs(w - W) > 40 || Math.abs(h - H) > 80
  W = w; H = h
  if (reseed) { measureAvoid(); epoch++; seedAgents(); bubbles.value = []; threads = []; leaders = [] }
  measureAvoid()
  updateStats()
  if (!running) draw()
}

// ── Opinión y conversación ─────────────────────────────────────────────────
const react = (a, glyph, dur = 0.9) => {
  a.hopAt = now
  a.hopAmp = 3
  a.glyph = glyph
  a.glyphUntil = now + dur
}

const shift = (a, delta) => {
  const before = bucketOf(a.o)
  a.o = Math.max(-1, Math.min(1, a.o + delta))
  const after = bucketOf(a.o)
  if (before !== after) {
    react(a, after === 'favor' ? 'heart' : after === 'against' ? 'bang' : 'question', 1.1)
    if (after === 'favor') a.happyUntil = now + 1.6
  }
  return before !== after
}

const fireEvent = () => {
  round.value += 1
  const n = ((round.value - 1) % ROUNDS) + 1
  eventLabel.value = t(`home.crowdEvent${n}`)
  waves.push({ dir: Math.random() < 0.5 ? 1 : -1, start: now, v: VALENCE[n - 1], hit: new Set() })
}

const stepWaves = () => {
  const speed = (W + 400) / 2.2
  for (const w of waves) {
    const front = w.dir > 0 ? -200 + speed * (now - w.start) : W + 200 - speed * (now - w.start)
    agents.forEach((a, i) => {
      if (w.hit.has(i)) return
      const cx = a.x + 12.5 * P
      if (Math.abs(cx - front) < CX * 0.6) {
        w.hit.add(i)
        const affinity = 1 + 1.3 * Math.max(0, Math.sign(w.v) * a.lean)
        const changed = shift(a, 0.8 * w.v * (0.3 + 0.7 * Math.random()) * (1 - a.stub) * affinity)
        if (!changed) { a.hopAt = now; a.hopAmp = 3; if (Math.random() < 0.18) react(a, w.v > 0 ? 'bang' : 'question', 0.7) }
      }
    })
  }
  waves = waves.filter(w => now - w.start < 3)
}

const drift = (dt) => {
  const heat = round.value / ROUNDS
  for (const a of agents) a.o += (a.lean * 0.9 - a.o) * 0.02 * heat * dt * (1 - a.stub * 0.5)
}

// ── Colocación de bocadillos ─────────────────────────────────────────────────
// Un bocadillo va encima de la cabeza (lo habitual), debajo o a un lado; hacia
// el lado con más pared y, si ahí no cabe, hacia el otro; y si ni así, se
// estrecha (hasta MIN_BW). Nunca pisa la tarjeta, el marcador ni el borde.
const MIN_BW = 150
const bubbleW = () => (W < 700 ? 180 : W < 1280 ? 200 : 230)
const heightFor = (w) => (w >= 210 ? 76 : w >= 175 ? 88 : 104)
// Cabecera del bocadillo: muestra de color + persona + postura, en mono de 10 px con tracking 0,1 em
// (cada carácter ocupa 7 px; los CJK, 11). Si la postura no cabe junto al nombre pasa a una segunda
// fila (14 px más de alto) y un ancho en el que ni el nombre cabe se descarta: ningún texto se corta.
const monoW = (s) => [...s].reduce((n, ch) => n + (ch.codePointAt(0) > 0x2e80 ? 11 : 7), 0)
const BUBBLE_CHROME = 26    // relleno lateral (2 × 11 px) + borde (2 × 2 px)
const whoNeed = (a) => 14 + monoW(t(`home.biankas.${a.look.persona}`))   // muestra + hueco + nombre
const tagNeed = () => Math.max(...['favor', 'undecided', 'against'].map(b => monoW(bucketLabel(b))))
const headerRows = (a, w) => (whoNeed(a) + 14 + tagNeed() <= w - BUBBLE_CHROME ? 1 : 2)
const bubbleWidths = (a, full) => {
  const all = [full, 170, MIN_BW].filter((w, i, arr) => w <= full && arr.indexOf(w) === i)
  const fit = all.filter(w => whoNeed(a) <= w - BUBBLE_CHROME)
  return fit.length ? fit : [full]
}
const bubbleHeight = (a, w) => heightFor(w) + (headerRows(a, w) === 2 ? 14 : 0)
const otherSide = (side) => (side === 'left' ? 'right' : 'left')

// Punto de la cabeza al que se ancla el bocadillo
const anchorOf = (a, dir = 'up', side = 'right') => {
  if (dir === 'side') return { x: a.x + (side === 'right' ? 19.5 : 5.5) * P, y: a.y + 16 * P }
  return { x: a.x + 12.5 * P, y: a.y + (dir === 'down' ? 22 : 11) * P }
}
const preferredSide = (a) => (anchorOf(a).x > W / 2 ? 'left' : 'right')
const boxFor = (a, dir, side, w, h) => {
  const { x, y } = anchorOf(a, dir, side)
  if (dir === 'side') {
    const l = side === 'right' ? x + 12 : x - 12 - w
    return { l, r: l + w, t: y - h / 2, b: y + h / 2 }
  }
  const l = side === 'right' ? x - 18 : x + 18 - w
  return dir === 'down'
    ? { l, r: l + w, t: y + 12, b: y + 12 + h }
    : { l, r: l + w, t: y - 12 - h, b: y - 12 }
}
const boxOf = (bb) => (bb.dir === 'free'
  ? { l: bb.box.l, r: bb.box.l + bb.width, t: bb.box.t, b: bb.box.t + bb.height }
  : boxFor(agents[bb.agent], bb.dir, bb.side, bb.width, bb.height))
const boxesTouch = (p, q, gap) => p.l < q.r + gap && p.r > q.l - gap && p.t < q.b + gap && p.b > q.t - gap

// ignoreBubbles: solo cuentan los bordes, la tarjeta y el marcador
const boxFree = (box, ignoreBubbles = false) => {
  if (box.l < 8 || box.r > W - 8 || box.t < 8 || box.b > H - 8) return false
  if (hitsAvoid(box, 12)) return false
  if (ignoreBubbles) return true
  return !bubbles.value.some(bb => agents[bb.agent] && boxesTouch(box, boxOf(bb), 14))
}

// Dónde poner el bocadillo de una Bianka: { dir, side, width, height } o null.
// Prefiere el ancho completo en cualquiera de los dos lados antes de estrecharlo.
const placeBubble = (a, dirs = ['up', 'side'], ignoreBubbles = false) => {
  const first = preferredSide(a)
  const widths = bubbleWidths(a, bubbleW())
  for (const dir of dirs) {
    for (const width of widths) {
      const height = bubbleHeight(a, width)
      for (const side of [first, otherSide(first)]) {
        if (boxFree(boxFor(a, dir, side, width, height), ignoreBubbles)) return { dir, side, width, height, rows: headerRows(a, width) }
      }
    }
  }
  return null
}

// Último recurso (al pulsar una Bianka pegada a la tarjeta o al borde): el bocadillo
// va al hueco libre más cercano y un hilo de puntos lo une a la Bianka.
const MAX_LEASH = 420
const leashClear = (x0, y0, x1, y1) => {
  const n = Math.max(2, Math.round(Math.hypot(x1 - x0, y1 - y0) / 14))
  for (let i = 1; i < n; i++) {
    const u = i / n
    if (coveredAt(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u)) return false
  }
  return true
}
// `from`: punto de partida del hilo (al pulsar, donde se pulsó: la cabeza puede estar medio tapada por la tarjeta)
const placeFree = (a, ignoreBubbles = false, from = null) => {
  const head = from || { x: a.x + 12.5 * P, y: a.y + 14 * P }
  const widths = bubbleWidths(a, bubbleW())
  for (const width of widths) {
    const height = bubbleHeight(a, width)
    const cands = []
    for (let t = 8; t + height <= H - 8; t += 16) {
      for (let l = 8; l + width <= W - 8; l += 16) {
        const box = { l, r: l + width, t, b: t + height }
        if (!boxFree(box, ignoreBubbles)) continue
        const qx = Math.min(Math.max(head.x, box.l), box.r)
        const qy = Math.min(Math.max(head.y, box.t), box.b)
        cands.push({ l, t, d: Math.hypot(qx - head.x, qy - head.y), qx, qy })
      }
    }
    cands.sort((u, v) => u.d - v.d)
    for (const c of cands.slice(0, 40)) {
      if (c.d > MAX_LEASH) break
      if (leashClear(head.x, head.y, c.qx, c.qy)) return { dir: 'free', side: 'right', width, height, rows: headerRows(a, width), box: { l: c.l, t: c.t } }
    }
  }
  return null
}

const speaking = (i) => bubbles.value.some(b => b.agent === i)

const addBubble = (i, text, kind, life, place) => {
  const a = agents[i]
  const bucket = bucketOf(a.o)
  const id = ++bubbleSeq
  bubbles.value.push({
    id, agent: i, bucket, text, kind,
    who: t(`home.biankas.${a.look.persona}`),
    tag: bucketLabel(bucket),
    side: place.side,
    dir: place.dir,
    width: place.width,
    height: place.height,
    stacked: place.rows === 2,
    box: place.box || null,
  })
  if (place.dir === 'free') leaders.push({ id, agent: i, box: boxOf(bubbles.value[bubbles.value.length - 1]), until: now + life })
  a.talkUntil = now + Math.min(life - 0.6, 2.2)
  setTimeout(() => { bubbles.value = bubbles.value.filter(b => b.id !== id) }, life * 1000)
  return id
}

const neighborsOf = (i, radius) => {
  const a = agents[i]
  const h = headOf(a)
  return agents
    .map((b, j) => ({ j, d: Math.hypot(headOf(b).x - h.x, headOf(b).y - h.y) }))
    .filter(n => n.j !== i && n.d < radius)
}

const startConversation = (forced = null, forcedPlace = null) => {
  const max = 2
  if (bubbles.value.length >= max && forced === null) return
  let i = forced
  let place = forcedPlace
  if (i === null) {
    for (let tries = 0; tries < 60; tries++) {
      const k = Math.floor(Math.random() * agents.length)
      if (speaking(k) || !headVisible(agents[k])) continue
      const found = placeBubble(agents[k]) || (W < 700 ? placeFree(agents[k]) : null)
      if (found) { i = k; place = found; break }
    }
  }
  if (i === null || speaking(i) || !place) return
  const a = agents[i]
  const bucket = bucketOf(a.o)                     // postura con la que habla: la respuesta se ajusta a ésta
  const pool = { favor: [1, 2, 3, 10, 11, 12], undecided: [4, 5, 6, 13, 14, 15], against: [7, 8, 9, 16, 17, 18] }[bucket]
  addBubble(i, say(pool.map(n => `home.crowdVoice${n}`)), 'say', 3.6, place)
  const myEpoch = epoch
  a.hopAt = now
  // Las vecinas giran los ojos hacia quien habla
  const near = neighborsOf(i, CX * 2.6)
  for (const n of near) { agents[n.j].lookAt = i; agents[n.j].lookUntil = now + 2.4 }
  // y una contesta
  // (otra persona distinta: nunca dos «Adicto al café» charlando entre sí)
  const candidates = near.filter(n => !speaking(n.j) && headVisible(agents[n.j]) && agents[n.j].look.persona !== a.look.persona)
  setTimeout(() => {
    if (myEpoch !== epoch || (!running && !forced)) return
    const opts = candidates
      .map(n => ({ j: n.j, place: placeBubble(agents[n.j]) || (W < 700 ? placeFree(agents[n.j]) : null) }))
      .filter(o => o.place)
    if (!opts.length) return
    const { j, place: replyPlace } = pick(opts)
    const b = agents[j]
    const before = bucketOf(b.o)
    let changed = false
    if (Math.abs(b.o - a.o) < 0.9) changed = shift(b, 0.55 * (a.o - b.o) * (1 - b.stub))
    const after = bucketOf(b.o)
    // Lo que dice quien contesta depende de qué piensa ella y de qué acaba de decir la otra:
    // si la convencen lo reconoce; si coinciden se apoyan; si no, discrepa con su propio tono.
    const replyKeys = changed && after === bucket
      ? [`home.crowdReChanged_${after}`, `home.crowdReChanged_${after}_2`]
      : after === bucket
        ? [1, 2, 3].map(n => `home.crowdReSame_${after}_${n}`)
        : [`home.crowdReDiff_${after}_${bucket}`, `home.crowdReDiff_${after}_${bucket}_2`]
    if (!changed && before !== bucket) react(b, 'question', 0.9)
    const id = addBubble(j, say(replyKeys), 'reply', 3.0, replyPlace)
    b.lookAt = i; b.lookUntil = now + 2.6
    a.lookAt = j; a.lookUntil = now + 2.6
    threads.push({ from: i, to: j, until: now + 2.8, id })
  }, 1300)
}

const updateStats = () => {
  if (!agents.length) return
  const c = { favor: 0, undecided: 0, against: 0 }
  // Solo las que están a la vista (no las tapadas por la tarjeta, el marcador o el formulario):
  // el marcador dice lo mismo que enseña el muro.
  const born = agents.filter(a => now >= a.born + 0.3)
  const seen = born.filter(a => a.shown)
  // cuántas se ven y cuántos aspectos distintos hay entre ellas (medible desde fuera, sin tocar el lienzo)
  if (root.value) { root.value.dataset.agents = String(seen.length); root.value.dataset.looks = String(new Set(seen.map(a => a.look.key)).size) }
  // Con muy pocas a la vista (un móvil enseña ~5) el reparto saltaría de 20 en 20 %: ahí cuenta a toda la multitud.
  const pool = seen.length >= 12 ? seen : born
  let n = 0
  for (const a of pool) { c[bucketOf(a.o)]++; n++ }
  if (!n) return
  stats.favor = Math.round((c.favor / n) * 100)
  stats.against = Math.round((c.against / n) * 100)
  stats.undecided = Math.max(0, 100 - stats.favor - stats.against)
}

// ── Dibujo ──────────────────────────────────────────────────────────────────
const GLYPHS = {
  bang: { color: PAL.k, rows: ['k', 'k', 'k', '.', 'k'] },
  question: { color: PAL.k, rows: ['.kk.', 'k..k', '..k.', '.k..', '....', '.k..'] },
  heart: { color: '#94AA3D', rows: ['.k.k.', 'kkkkk', 'kkkkk', '.kkk.', '..k..'] },
}

const drawGlyph = (a, dy) => {
  const g = GLYPHS[a.glyph]
  if (!g) return
  const w = g.rows[0].length
  const x0 = a.x + (12.5 - w / 2) * P
  const y0 = a.y + dy - (g.rows.length + 2) * P
  ctx.fillStyle = g.color
  g.rows.forEach((row, r) => {
    for (let c = 0; c < row.length; c++) if (row[c] === 'k') ctx.fillRect(x0 + c * P, y0 + r * P, P, P)
  })
}

const gazeOf = (a) => {
  let target = null
  if (a.lookAt !== null && now < a.lookUntil && agents[a.lookAt]) target = headOf(agents[a.lookAt])
  else if (pointer) {
    const h = headOf(a)
    if (Math.hypot(pointer.x - h.x, pointer.y - h.y) < 380) target = pointer
  }
  if (!target) return a.idleGaze
  const h = headOf(a)
  const dx = target.x - h.x, dy = target.y - h.y
  return [Math.abs(dx) > 18 ? Math.sign(dx) : 0, Math.abs(dy) > 18 ? Math.sign(dy) : 0]
}

const drawThreads = () => {
  threads = threads.filter(th => now < th.until && agents[th.from] && agents[th.to])
  ctx.fillStyle = PAL.k
  for (const th of threads) {
    const p = anchorOf(agents[th.from]), q = anchorOf(agents[th.to])
    const mx = (p.x + q.x) / 2, my = Math.min(p.y, q.y) - 40
    const steps = Math.max(6, Math.round(Math.hypot(q.x - p.x, q.y - p.y) / (P * 3)))
    for (let s = 1; s < steps; s++) {
      const u = s / steps
      const x = (1 - u) ** 2 * p.x + 2 * (1 - u) * u * mx + u ** 2 * q.x
      const y = (1 - u) ** 2 * p.y + 2 * (1 - u) * u * my + u ** 2 * q.y
      ctx.fillRect(Math.round(x / P) * P, Math.round(y / P) * P, P, P)
    }
  }
}

const drawLeaders = () => {
  leaders = leaders.filter(ld => now < ld.until && agents[ld.agent] && bubbles.value.some(b => b.id === ld.id))
  for (const ld of leaders) {
    const a = agents[ld.agent]
    const px = a.x + 12.5 * P, py = a.y + offsetOf(a) + 14 * P
    const qx = Math.min(Math.max(px, ld.box.l), ld.box.r), qy = Math.min(Math.max(py, ld.box.t), ld.box.b)
    const steps = Math.max(3, Math.round(Math.hypot(qx - px, qy - py) / (P * 3)))
    // primero un halo blanco y encima el punto de tinta: se lee sobre cualquier color del muro
    for (const [color, size, grow] of [[PAL.w, P * 2, P / 2], [PAL.k, P, 0]]) {
      ctx.fillStyle = color
      for (let s = 0; s <= steps; s++) {
        const u = s / steps
        ctx.fillRect(Math.round((px + (qx - px) * u) / P) * P - grow, Math.round((py + (qy - py) * u) / P) * P - grow, size, size)
      }
    }
  }
}

const offsetOf = (a) => {
  const bob = ((now / a.bobPeriod + a.bobPhase) % 1) < 0.5 ? 0 : P
  const hopT = now - a.hopAt
  const hop = hopT >= 0 && hopT < 0.32 ? Math.round(Math.sin((Math.PI * hopT) / 0.32) * (a.hopAmp || 3)) * P : 0
  return bob - hop
}

const draw = () => {
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, W, H)
  const paint = (a, thick) => {
    const k = Math.min(1, (now - a.born) / 0.3)
    if (k <= 0) return
    // al nacer sube desde abajo en tres escalones (pixel art: sin interpolar)
    const rise = k < 1 ? Math.ceil((1 - k) * 3) * P : 0
    const dy = offsetOf(a) + rise
    drawBianka(ctx, {
      x: a.x, y: a.y + dy, P, look: a.look, bucket: bucketOf(a.o), mirror: a.mirror, now, thick,
      gaze: gazeOf(a), blink: now < a.blinkUntil, happy: now < a.happyUntil, talking: now < a.talkUntil,
    })
  }
  const talking = new Set(bubbles.value.map(b => b.agent))
  agents.forEach((a, i) => { if (a.shown && !talking.has(i)) paint(a, false) })
  // quien habla sale al frente y con el contorno de tinta más grueso: el bocadillo siempre tiene dueña
  agents.forEach((a, i) => { if (a.shown && talking.has(i)) paint(a, true) })
  drawThreads()
  drawLeaders()
  for (const a of agents) if (a.shown && a.glyph && now < a.glyphUntil) drawGlyph(a, offsetOf(a))
  for (const bub of bubbles.value) {
    const el = bubbleEls.get(bub.id)
    const a = agents[bub.agent]
    if (!el || !a) continue
    if (bub.dir === 'free') {
      el.style.transform = `translate(${Math.round(bub.box.l)}px, ${Math.round(bub.box.t)}px)`
    } else {
      const { x, y } = anchorOf(a, bub.dir, bub.side)
      el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y + offsetOf(a))}px)`
    }
    el.style.visibility = hitsAvoid(boxOf(bub), 0) ? 'hidden' : ''
  }
}

const tick = (ts) => {
  raf = null
  if (!running) return
  const dt = Math.min(0.05, (ts - last) / 1000 || 0.016)
  last = ts
  now += dt
  for (const a of agents) {
    if (now > a.nextBlink) { a.blinkUntil = now + 0.13; a.nextBlink = now + rand(2.5, 6.5) }
    if (now > a.nextIdle) { a.idleGaze = [Math.round(rand(-1, 1)), Math.round(rand(-1, 0.4))]; a.nextIdle = now + rand(2, 6) }
    // saltito espontáneo, pequeño: la multitud no está quieta entre evento y evento
    if (now > a.nextHop && now > a.born + 0.5) { a.hopAt = now; a.hopAmp = 2; a.nextHop = now + rand(8, 20) }
  }
  stepWaves()
  drift(dt)
  if (resetClock >= 0) {
    resetClock += dt
    if (resetClock > 3.5) {
      for (const a of agents) { a.o = initialOpinion(); a.lean = randomLean() }
      round.value = 0
      eventLabel.value = ''
      resetClock = -1
      roundClock = 0
    }
  } else {
    roundClock += dt
    if (roundClock >= (round.value === 0 ? 0.7 : ROUND_SECONDS)) {
      roundClock = 0
      if (round.value >= ROUNDS) resetClock = 0
      else fireEvent()
    }
  }
  talkClock += dt
  if (talkClock > (W < 700 ? 2.6 : 1.7)) { talkClock = 0; startConversation() }
  statsClock += dt
  if (statsClock > 0.4) { statsClock = 0; updateStats() }
  measureClock += dt
  if (measureClock > 1.5) { measureClock = 0; measureAvoid() }
  draw()
  raf = requestAnimationFrame(tick)
}

const start = () => {
  if (running || reducedMotion || !visible || document.hidden) return
  running = true
  last = performance.now()
  raf = requestAnimationFrame(tick)
}
const stop = () => {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = null
}
const onVisibility = () => (document.hidden ? stop() : start())

// ── Interacción: te miran y, si tocas una, habla ────────────────────────────
const agentAt = (x, y) => {
  for (let k = agents.length - 1; k >= 0; k--) {
    const a = agents[k]
    if (!a.shown) continue
    const dy = offsetOf(a)
    if (x > a.x + 5 * P && x < a.x + 21 * P && y > a.y + dy + 12 * P && y < a.y + dy + 22 * P) return k
  }
  return null
}
// Bajo el marcador (que deja pasar los eventos) o la franja que tapa el formulario
// hay Biankas que no se ven: ahí ni cambia el cursor ni responde el clic.
const onPointerMove = (e) => {
  if (!root.value) return
  const c = root.value.getBoundingClientRect()
  const x = e.clientX - c.left, y = e.clientY - c.top
  pointer = x >= 0 && y >= 0 && x <= c.width && y <= c.height ? { x, y } : null
  hovering.value = pointer !== null && e.target === canvas.value && !coveredAt(x, y) && agentAt(x, y) !== null
}
const onClick = (e) => {
  const c = root.value.getBoundingClientRect()
  const x = e.clientX - c.left, y = e.clientY - c.top
  if (coveredAt(x, y)) return
  const k = agentAt(x, y)
  if (k === null || speaking(k)) return
  measureAvoid()
  const a = agents[k]
  const dirs = ['up', 'down', 'side']
  let place = placeBubble(a, dirs)
  if (!place) {
    // El clic manda: si solo estorban otros bocadillos, se retiran para dejarle sitio.
    place = placeBubble(a, dirs, true)
    if (place) {
      const box = boxFor(a, place.dir, place.side, place.width, place.height)
      bubbles.value = bubbles.value.filter(bb => agents[bb.agent] && !boxesTouch(box, boxOf(bb), 14))
    }
  }
  // Pegada a la tarjeta, al marcador o al borde: el bocadillo va al hueco libre más cercano
  // y un hilo de puntos lo une a ella.
  if (!place) place = placeFree(a, false, { x, y })
  if (!place) {
    place = placeFree(a, true, { x, y })
    if (place) {
      const box = { l: place.box.l, r: place.box.l + place.width, t: place.box.t, b: place.box.t + place.height }
      bubbles.value = bubbles.value.filter(bb => agents[bb.agent] && !boxesTouch(box, boxOf(bb), 14))
    }
  }
  if (place) startConversation(k, place)
  else react(a, 'bang', 0.8)
}

// Sin animación: las diez rondas de golpe y el resultado quieto.
const renderStatic = () => {
  for (let r = 0; r < ROUNDS; r++) {
    const v = VALENCE[r]
    for (const a of agents) {
      const affinity = 1 + 1.3 * Math.max(0, Math.sign(v) * a.lean)
      a.o = Math.max(-1, Math.min(1, a.o + v * (0.3 + 0.7 * Math.random()) * (1 - a.stub) * affinity))
      a.o += (a.lean * 0.9 - a.o) * 0.25 * (r / ROUNDS)
    }
  }
  round.value = ROUNDS
  eventLabel.value = t(`home.crowdEvent${ROUNDS}`)
  updateStats()
  draw()
}

watch(() => props.avoidEl, (el) => {
  if (!el || !agents.length || seededFor === el) return
  measureAvoid(); epoch++; seedAgents(); bubbles.value = []; threads = []; leaders = []
  measureAvoid(); updateStats(); if (!running) draw()
})

onMounted(() => {
  resize()
  resizeObs = new ResizeObserver(() => resize())
  resizeObs.observe(root.value)
  readoutObs = new ResizeObserver(() => emit('readout', Math.ceil(readout.value.offsetHeight)))
  readoutObs.observe(readout.value)
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.fonts?.ready?.then(() => { measureAvoid(); if (!running) draw() })
  if (reducedMotion) { renderStatic(); return }
  interObs = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    visible ? start() : stop()
  })
  interObs.observe(root.value)
  document.addEventListener('visibilitychange', onVisibility)
  start()
})

onUnmounted(() => {
  stop()
  resizeObs?.disconnect()
  readoutObs?.disconnect()
  interObs?.disconnect()
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.bianka-crowd {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.crowd-canvas { display: block; image-rendering: pixelated; }
.crowd-canvas.is-hovering { cursor: pointer; }

.crowd-bubble {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 3;
  width: max-content;
  translate: -18px calc(-100% - 12px);
  padding: 8px 11px 9px;
  background: var(--kb-surface);
  color: var(--kb-text);
  border: 2px solid var(--ink-950);
  border-radius: 4px;
  box-shadow: 4px 4px 0 var(--ink-950);
  display: grid;
  gap: 3px;
  pointer-events: none;
  animation: bubble-pop 0.22s steps(3, end) both;
}
.crowd-bubble.kind-reply { background: var(--cream-100); }
.crowd-bubble.to-left { translate: calc(-100% + 18px) calc(-100% - 12px); }
.crowd-bubble.dir-down { translate: -18px 12px; }
.crowd-bubble.dir-down.to-left { translate: calc(-100% + 18px) 12px; }
.crowd-bubble.dir-free { translate: 0 0; }
.crowd-bubble.dir-free::before,
.crowd-bubble.dir-free::after { display: none; }
.crowd-bubble.dir-side { translate: 12px -50%; }
.crowd-bubble.dir-side.to-left { translate: calc(-100% - 12px) -50%; }
/* pico escalonado, en píxeles */
.crowd-bubble::before,
.crowd-bubble::after {
  content: '';
  position: absolute;
  left: 12px;
  width: 8px;
  height: 6px;
  background: var(--ink-950);
}
.crowd-bubble::before { bottom: -8px; }
.crowd-bubble::after { bottom: -12px; left: 12px; width: 4px; height: 4px; }
.crowd-bubble.to-left::before,
.crowd-bubble.to-left::after { left: auto; right: 12px; }
/* si se abre hacia abajo, el pico va arriba */
.crowd-bubble.dir-down::before { bottom: auto; top: -8px; }
.crowd-bubble.dir-down::after { bottom: auto; top: -12px; }
/* al lado de la cabeza, el pico sale por el costado */
.crowd-bubble.dir-side::before { bottom: auto; top: calc(50% - 4px); left: -8px; width: 6px; height: 8px; }
.crowd-bubble.dir-side::after { bottom: auto; top: calc(50% - 2px); left: -12px; width: 4px; height: 4px; }
.crowd-bubble.dir-side.to-left::before { left: auto; right: -8px; }
.crowd-bubble.dir-side.to-left::after { left: auto; right: -12px; }
.crowd-bubble-who {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  font-family: var(--kb-font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kb-muted);
  white-space: nowrap;
}
.who-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.who-tag { flex: none; margin-inline-start: auto; padding-inline-start: 8px; color: var(--kb-text); font-weight: 700; }
/* estrecho: la postura baja a su propia fila, alineada bajo el nombre */
.crowd-bubble.is-stacked .crowd-bubble-who { flex-wrap: wrap; row-gap: 1px; }
.crowd-bubble.is-stacked .who-tag { flex-basis: 100%; margin-inline-start: 0; padding-inline-start: 14px; }
.crowd-bubble-text {
  font-family: var(--kb-font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  text-wrap: pretty;
}
/* Sin `scale`: la propiedad individual `scale` se aplica ANTES que el `transform` con el que se
   coloca el bocadillo y lo desplazaba hacia la esquina durante la aparición. */
@keyframes bubble-pop {
  from { opacity: 0; clip-path: inset(38% 24% 38% 24%); }
  to { opacity: 1; clip-path: inset(-16px); }
}

.swatch {
  display: inline-block;
  flex: none;
  width: 8px;
  height: 8px;
  border: 1.5px solid var(--ink-950);
}
.swatch.is-favor { background: var(--lime-500); }
.swatch.is-undecided { background: #fff; }
.swatch.is-against { background: #2A2A2A; }

.crowd-readout {
  position: absolute;
  z-index: 3;
  inset-inline-start: clamp(16px, 4vw, 48px);
  bottom: 24px;
  width: min(400px, calc(100% - 32px));
  padding: 14px 16px;
  background: var(--kb-surface);
  border: 2px solid var(--ink-950);
  border-radius: 6px;
  box-shadow: 4px 4px 0 var(--ink-950);
  color: var(--kb-text);
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  pointer-events: none;
}
.readout-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--kb-muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.readout-round { color: var(--kb-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.readout-event {
  margin-top: 6px;
  font-family: var(--kb-font-sans);
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: var(--kb-text);
}
.event-tag {
  margin-inline-end: 8px;
  font: 500 10px var(--kb-font-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kb-muted);
  vertical-align: 2px;
}
.readout-bar {
  display: flex;
  height: 12px;
  margin: 10px 0;
  overflow: hidden;
  border: 2px solid var(--ink-950);
  background: #fff;
}
.readout-bar .seg { transition: width 0.6s steps(6, end); }
.readout-bar .is-favor { background: var(--lime-500); }
.readout-bar .is-undecided { background: #fff; }
.readout-bar .is-against { background: #2A2A2A; }
.readout-legend { display: flex; flex-wrap: wrap; gap: 8px 16px; font-size: 13px; color: var(--kb-text-2); }
.readout-legend span { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.readout-legend .swatch { width: 12px; height: 12px; }
.readout-legend b { font-weight: 700; color: var(--kb-text); font-variant-numeric: tabular-nums; }
.readout-hint { margin-top: 9px; padding-top: 8px; border-top: 1px dashed rgba(17, 17, 17, 0.25); font-size: 11px; letter-spacing: 0.02em; color: var(--kb-muted); }

@media (max-width: 700px) {
  .crowd-readout { inset-inline-start: 16px; bottom: 16px; }
  /* en móvil la franja de muro sobre la tarjeta es corta y cada píxel del marcador se la quita a los
     bocadillos: sin la pista (se pulsa sin más) y con la leyenda en una sola línea */
  .readout-hint { display: none; }
}
@media (max-width: 480px) {
  .readout-legend { gap: 6px 12px; font-size: 12px; }
  .readout-legend span { gap: 5px; }
}
@media (prefers-reduced-motion: reduce) {
  .crowd-bubble { animation: none; }
  .readout-bar .seg { transition: none; }
}
</style>
