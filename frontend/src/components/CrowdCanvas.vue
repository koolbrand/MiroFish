<template>
  <!-- Multitud de ejemplo para la portada: puntos que opinan, se agrupan y
       reaccionan a «eventos» ronda tras ronda. Es decorativa (aria-hidden):
       el contenido real de la página no depende de ella. -->
  <div ref="root" class="crowd" aria-hidden="true">
    <canvas ref="canvas" class="crowd-canvas"></canvas>

    <div
      v-for="b in bubbles"
      :key="b.id"
      :ref="el => setBubbleEl(b.id, el)"
      class="crowd-bubble"
      :class="[`is-${b.bucket}`, `to-${b.side}`]"
      :style="{ maxWidth: `${b.width}px` }"
    >
      <span class="crowd-bubble-who"><i class="swatch" :class="`is-${b.bucket}`"></i>{{ bucketLabel(b.bucket) }}</span>
      <span class="crowd-bubble-text">{{ b.text }}</span>
    </div>

    <div ref="readout" class="crowd-readout" :style="{ bottom: `${bottomInset + 28}px` }">
      <div class="readout-head">
        <span>{{ $t('home.crowdCaption') }}</span>
        <span class="readout-round">{{ $t('home.crowdRound') }} {{ String(round).padStart(2, '0') }}/{{ ROUNDS }}</span>
      </div>
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
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  // Elemento con el texto de la portada: bajo él los puntos se atenúan y no
  // aparecen bocadillos, para que el titular se lea siempre.
  quietEl: { type: Object, default: null },
  // Alto (px) que tapa la tarjeta que monta sobre el borde inferior.
  bottomInset: { type: Number, default: 0 },
})

const { t } = useI18n()

const ROUNDS = 10
const ROUND_SECONDS = 5.2
const LIME = '#CCE673'
const AGAINST = '#8A8A8A'
// Valencia de cada ronda: el guion alterna noticias buenas y malas para que
// se vea la opinión moverse, no solo crecer.
const VALENCE = [0.55, -0.45, 0.4, -0.4, 0.5, -0.3, 0.45, -0.35, 0.4, 0.3]

const root = ref(null)
const canvas = ref(null)
const readout = ref(null)
const round = ref(0)
const stats = reactive({ favor: 0, undecided: 100, against: 0 })
const bubbles = ref([])

let ctx = null
let W = 0, H = 0, dpr = 1
let agents = []
let rings = []
let quiet = [] // rectángulos del texto de portada { l, t, r, b }
let raf = null
let running = false
let visible = true
let last = 0
let roundClock = 0
let bubbleClock = 0
let statsClock = 0
let resetClock = -1
let bubbleSeq = 0
const bubbleEls = new Map()
let resizeObs = null
let interObs = null
const reducedMotion = typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const bucketOf = (o) => (o > 0.33 ? 'favor' : o < -0.33 ? 'against' : 'undecided')
const bucketLabel = (b) => t({ favor: 'home.crowdFor', undecided: 'home.crowdUndecided', against: 'home.crowdAgainst' }[b])

const setBubbleEl = (id, el) => { if (el) bubbleEls.set(id, el); else bubbleEls.delete(id) }

const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5
// Predisposición: hacia dónde tiende cada persona cuando la conversación se calienta.
const randomLean = () => Math.max(-1, Math.min(1, gauss() * 1.6 + 0.12))

const distToRect = (x, y, q) => Math.hypot(Math.max(q.l - x, 0, x - q.r), Math.max(q.t - y, 0, y - q.b))

// Atenuación bajo el texto de portada: 0,14 encima, 1 a partir de 70 px.
const quietFactor = (x, y) => {
  let f = 1
  for (const q of quiet) {
    const k = Math.min(1, distToRect(x, y, q) / 70)
    f = Math.min(f, 0.14 + 0.86 * k * k * (3 - 2 * k))
  }
  return f
}

const overlapsQuiet = (box, pad) => quiet.some(q =>
  box.l < q.r + pad && box.r > q.l - pad && box.t < q.b + pad && box.b > q.t - pad)

// Se mide el texto de cada bloque marcado con data-quiet (no la caja entera,
// que en pantallas medianas ocupa todo el ancho y dejaba sin sitio a la multitud).
const measureQuiet = () => {
  const el = props.quietEl
  if (!el || !root.value) { quiet = []; return }
  const c = root.value.getBoundingClientRect()
  const blocks = el.querySelectorAll('[data-quiet]')
  const range = document.createRange()
  const rel = (r) => ({ l: r.left - c.left, t: r.top - c.top, r: r.right - c.left, b: r.bottom - c.top })
  quiet = Array.from(blocks.length ? blocks : [el]).map(b => {
    range.selectNodeContents(b)
    return rel(range.getBoundingClientRect())
  })
  // El marcador también se reserva: ni puntos brillantes ni bocadillos encima.
  if (readout.value) quiet.push(rel(readout.value.getBoundingClientRect()))
  quiet = quiet.filter(q => q.r > q.l && q.b > q.t)
}

const seedAgents = () => {
  const n = Math.max(90, Math.min(320, Math.round((W * H) / 3400)))
  agents = Array.from({ length: n }, () => ({
    x: Math.random() * W,
    y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.3,
    o: gauss() * 0.18,
    lean: randomLean(),
    stub: Math.random() ** 2 * 0.85,
    r: 1.8 + Math.random() * 2.2,
    links: [],
  }))
}

const resize = () => {
  const el = root.value
  if (!el || !canvas.value) return
  const w = el.clientWidth
  const h = el.clientHeight
  if (!w || !h) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.value.width = Math.round(w * dpr)
  canvas.value.height = Math.round(h * dpr)
  canvas.value.style.width = `${w}px`
  canvas.value.style.height = `${h}px`
  ctx = canvas.value.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  if (agents.length && W && H) {
    // Reescalar en vez de resembrar: la multitud no «salta» al redimensionar.
    const sx = w / W, sy = h / H
    for (const a of agents) { a.x *= sx; a.y *= sy }
  }
  W = w; H = h
  if (!agents.length) seedAgents()
  measureQuiet()
  if (!running) draw()
}

// ── Dinámica ────────────────────────────────────────────────────────────────
const CELL = 64

const step = (dt) => {
  const f = dt * 60
  const heat = round.value / ROUNDS
  const cols = Math.ceil(W / CELL) + 1
  const grid = new Map()
  agents.forEach((a, i) => {
    const key = Math.floor(a.x / CELL) + Math.floor(a.y / CELL) * cols
    let cell = grid.get(key)
    if (!cell) grid.set(key, (cell = []))
    cell.push(i)
  })

  for (let i = 0; i < agents.length; i++) {
    const a = agents[i]
    let ax = (Math.random() - 0.5) * 0.5
    let ay = (Math.random() - 0.5) * 0.5
    const gx = Math.floor(a.x / CELL), gy = Math.floor(a.y / CELL)
    let best1 = null, best2 = null, d1 = Infinity, d2 = Infinity
    for (let ox = -1; ox <= 1; ox++) {
      for (let oy = -1; oy <= 1; oy++) {
        const cell = grid.get(gx + ox + (gy + oy) * cols)
        if (!cell) continue
        for (const j of cell) {
          if (j === i) continue
          const b = agents[j]
          const dx = b.x - a.x, dy = b.y - a.y
          const d = Math.hypot(dx, dy)
          if (d < 0.5 || d > CELL) continue
          const similar = Math.abs(a.o - b.o) < 0.35
          if (d < 13) { ax -= (dx / d) * (13 - d) * 0.09; ay -= (dy / d) * (13 - d) * 0.09 }
          else if (similar) { ax += (dx / d) * 0.05; ay += (dy / d) * 0.05 }
          else if (d < 42) { ax -= (dx / d) * 0.07; ay -= (dy / d) * 0.07 }
          // Confianza acotada (Deffuant): solo te convence quien ya piensa parecido.
          if (similar && Math.random() < 0.015 * f) a.o += 0.3 * (b.o - a.o) * (1 - a.stub)
          if (similar && d < 58) {
            if (d < d1) { d2 = d1; best2 = best1; d1 = d; best1 = j }
            else if (d < d2) { d2 = d; best2 = j }
          }
        }
      }
    }
    a.links = [best1, best2].filter(j => j !== null && j > i)
    a.o += (a.lean * 0.9 - a.o) * 0.0028 * heat * f * (1 - a.stub * 0.5)
    a.vx = (a.vx + ax * 0.02 * f) * Math.pow(0.95, f)
    a.vy = (a.vy + ay * 0.02 * f) * Math.pow(0.95, f)
    const sp = Math.hypot(a.vx, a.vy)
    if (sp > 0.42) { a.vx *= 0.42 / sp; a.vy *= 0.42 / sp }
    a.x += a.vx * f
    a.y += a.vy * f
    if (a.x < -10) a.x += W + 20; else if (a.x > W + 10) a.x -= W + 20
    if (a.y < -10) a.y += H + 20; else if (a.y > H + 10) a.y -= H + 20
  }

  // Las ondas de cada evento empujan la opinión de quien alcanzan.
  for (const ring of rings) {
    ring.r += 230 * dt
    ring.age += dt
    for (let i = 0; i < agents.length; i++) {
      if (ring.hit.has(i)) continue
      const a = agents[i]
      if (Math.abs(Math.hypot(a.x - ring.x, a.y - ring.y) - ring.r) < 12) {
        ring.hit.add(i)
        const affinity = 1 + 1.3 * Math.max(0, Math.sign(ring.v) * a.lean)
        a.o = Math.max(-1, Math.min(1, a.o + ring.v * (0.3 + 0.7 * Math.random()) * (1 - a.stub) * affinity))
      }
    }
  }
  rings = rings.filter(r => r.r < Math.hypot(W, H))
}

const BUBBLE_H = 76
const bubbleW = () => (W < 700 ? 180 : W < 1280 ? 200 : 230)

// Caja que ocuparía el bocadillo de un agente: se abre hacia el lado con más sitio.
const bubbleBox = (a) => {
  const w = bubbleW()
  const side = a.x > W / 2 ? 'left' : 'right'
  const l = side === 'right' ? a.x - 18 : a.x + 18 - w
  return { side, l, r: l + w, t: a.y - 12 - BUBBLE_H, b: a.y - 12 }
}

const pickAgent = (forBubble) => {
  // Por debajo queda la tarjeta del formulario, que tapa la portada.
  const maxY = H - props.bottomInset - (forBubble ? 12 : 70)
  for (let tries = 0; tries < 60; tries++) {
    const i = Math.floor(Math.random() * agents.length)
    const a = agents[i]
    if (a.y > maxY || a.y < 40) continue
    if (!forBubble) {
      if (quietFactor(a.x, a.y) < 1 || a.x < 40 || a.x > W - 40) continue
      return i
    }
    const box = bubbleBox(a)
    if (box.l < 8 || box.r > W - 8 || box.t < 8) continue
    if (overlapsQuiet(box, 14)) continue
    // ni encima de otro bocadillo (el que se va y el que llega conviven un momento)
    if (bubbles.value.some(bb => {
      const o = agents[bb.agent]
      if (!o) return false
      const ob = bubbleBox(o)
      return box.l < ob.r + 16 && box.r > ob.l - 16 && box.t < ob.b + 16 && box.b > ob.t - 16
    })) continue
    return i
  }
  return null
}

const fireEvent = () => {
  round.value += 1
  const i = pickAgent(false)
  const a = i !== null ? agents[i] : { x: W * 0.2, y: H * 0.3 }
  const n = ((round.value - 1) % ROUNDS) + 1
  rings.push({ x: a.x, y: a.y, r: 0, age: 0, v: VALENCE[n - 1], hit: new Set(), label: t(`home.crowdEvent${n}`) })
}

const spawnBubble = () => {
  const max = W < 700 ? 1 : 2
  if (bubbles.value.length >= max) return
  const i = pickAgent(true)
  if (i === null) return
  const bucket = bucketOf(agents[i].o)
  const side = bubbleBox(agents[i]).side
  const pool = { favor: [1, 2, 3], undecided: [4, 5, 6], against: [7, 8, 9] }[bucket]
  const text = t(`home.crowdVoice${pool[Math.floor(Math.random() * pool.length)]}`)
  const id = ++bubbleSeq
  bubbles.value.push({ id, agent: i, bucket, text, side, width: bubbleW() })
  setTimeout(() => { bubbles.value = bubbles.value.filter(b => b.id !== id) }, 3600)
}

const updateStats = () => {
  if (!agents.length) return
  const c = { favor: 0, undecided: 0, against: 0 }
  for (const a of agents) c[bucketOf(a.o)]++
  const n = agents.length
  const favor = Math.round((c.favor / n) * 100)
  const against = Math.round((c.against / n) * 100)
  stats.favor = favor
  stats.against = against
  stats.undecided = Math.max(0, 100 - favor - against)
}

// ── Dibujo ──────────────────────────────────────────────────────────────────
const draw = () => {
  if (!ctx) return
  ctx.clearRect(0, 0, W, H)

  ctx.lineWidth = 1
  for (const a of agents) {
    for (const j of a.links) {
      const b = agents[j]
      if (Math.abs(a.x - b.x) > 80 || Math.abs(a.y - b.y) > 80) continue
      const q = Math.min(quietFactor(a.x, a.y), quietFactor(b.x, b.y))
      const fav = bucketOf(a.o) === 'favor' && bucketOf(b.o) === 'favor'
      ctx.strokeStyle = fav ? `rgba(204,230,115,${0.22 * q})` : `rgba(242,241,239,${0.08 * q})`
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke()
    }
  }

  for (const ring of rings) {
    const life = Math.max(0, 1 - ring.r / Math.max(W, H))
    ctx.strokeStyle = ring.v > 0 ? `rgba(204,230,115,${0.5 * life})` : `rgba(242,241,239,${0.28 * life})`
    ctx.lineWidth = 1.2
    ctx.beginPath(); ctx.arc(ring.x, ring.y, ring.r, 0, Math.PI * 2); ctx.stroke()
    if (ring.age < 1.8) {
      const al = ring.age < 0.2 ? ring.age / 0.2 : 1 - (ring.age - 0.2) / 1.6
      ctx.font = '500 11px "JetBrains Mono", ui-monospace, monospace'
      ctx.fillStyle = `rgba(204,230,115,${Math.max(0, al)})`
      ctx.textAlign = 'center'
      ctx.fillText(ring.label.toUpperCase(), ring.x, ring.y - 14)
      ctx.beginPath(); ctx.arc(ring.x, ring.y, 3, 0, Math.PI * 2); ctx.fill()
    }
  }

  for (const a of agents) {
    const q = quietFactor(a.x, a.y)
    const b = bucketOf(a.o)
    ctx.beginPath()
    ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2)
    if (b === 'favor') {
      ctx.globalAlpha = q
      ctx.fillStyle = LIME
      ctx.fill()
    } else if (b === 'undecided') {
      ctx.globalAlpha = 0.58 * q
      ctx.fillStyle = '#F2F1EF'
      ctx.fill()
    } else {
      ctx.globalAlpha = 0.9 * q
      ctx.strokeStyle = AGAINST
      ctx.lineWidth = 1.2
      ctx.stroke()
    }
  }
  ctx.globalAlpha = 1

  // Los bocadillos siguen a su agente.
  for (const bub of bubbles.value) {
    const el = bubbleEls.get(bub.id)
    const a = agents[bub.agent]
    if (el && a) el.style.transform = `translate(${Math.round(a.x)}px, ${Math.round(a.y)}px)`
  }
}

const tick = (now) => {
  raf = null
  if (!running) return
  const dt = Math.min(0.05, (now - last) / 1000 || 0.016)
  last = now
  step(dt)

  if (resetClock >= 0) {
    // Fin de las 10 rondas: pausa para leer el resultado y vuelta a empezar.
    resetClock += dt
    if (resetClock > 3.2) {
      for (const a of agents) { a.o = gauss() * 0.18; a.lean = randomLean() }
      round.value = 0
      rings = []
      roundClock = 0
      resetClock = -1
    }
  } else {
    roundClock += dt
    if (roundClock >= (round.value === 0 ? 1.4 : ROUND_SECONDS)) {
      roundClock = 0
      if (round.value >= ROUNDS) resetClock = 0
      else fireEvent()
    }
  }

  bubbleClock += dt
  if (bubbleClock > 2.4) { bubbleClock = 0; spawnBubble() }
  statsClock += dt
  if (statsClock > 0.4) { statsClock = 0; updateStats() }

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

// Sin animación: se calculan las 10 rondas de golpe y se deja el resultado.
const renderStatic = () => {
  for (let r = 0; r < ROUNDS; r++) {
    fireEvent()
    for (let s = 0; s < 90; s++) step(1 / 30)
  }
  rings = []
  updateStats()
  draw()
}

watch(() => props.quietEl, () => { measureQuiet(); if (!running) draw() })

onMounted(() => {
  resize()
  resizeObs = new ResizeObserver(() => resize())
  resizeObs.observe(root.value)
  document.fonts?.ready?.then(() => { measureQuiet(); if (!running) draw() })
  // El texto de portada entra con animación: se vuelve a medir cuando termina.
  setTimeout(() => { measureQuiet(); if (!running) draw() }, 1600)
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
  interObs?.disconnect()
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.crowd {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.crowd-canvas { display: block; }

.crowd-bubble {
  position: absolute;
  top: 0;
  left: 0;
  width: max-content;
  max-width: 230px;
  margin: 0;
  /* el pico del bocadillo queda sobre el agente */
  translate: -18px calc(-100% - 12px);
  padding: 8px 11px 9px;
  background: var(--cream-100);
  color: var(--kb-text);
  border-radius: 10px;
  box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.6);
  display: grid;
  gap: 3px;
  animation: bubble-life 3.6s ease forwards;
}
.crowd-bubble.to-left { translate: calc(-100% + 18px) calc(-100% - 12px); }
.crowd-bubble::after {
  content: '';
  position: absolute;
  left: 12px;
  bottom: -6px;
  width: 12px;
  height: 12px;
  background: inherit;
  transform: rotate(45deg);
  border-radius: 2px;
}
.crowd-bubble.to-left::after { left: auto; right: 12px; }
.crowd-bubble-who {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--kb-font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--kb-muted);
  white-space: nowrap;
}
.crowd-bubble-text {
  font-family: var(--kb-font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  text-wrap: pretty;
}
@keyframes bubble-life {
  0% { opacity: 0; scale: 0.92; }
  10%, 82% { opacity: 1; scale: 1; }
  100% { opacity: 0; scale: 0.96; }
}

.swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}
.swatch.is-favor { background: var(--lime-500); }
.swatch.is-undecided { background: var(--gray-300); }
.swatch.is-against { border: 1.5px solid var(--gray-500); }

.crowd-readout {
  position: absolute;
  inset-inline-start: clamp(16px, 4vw, 48px);
  width: min(390px, calc(100% - 32px));
  color: var(--cream-100);
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
}
.readout-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: rgba(242, 241, 239, 0.62);
}
.readout-round { color: var(--lime-500); font-variant-numeric: tabular-nums; }
.readout-bar {
  display: flex;
  height: 6px;
  margin: 10px 0;
  border-radius: 3px;
  overflow: hidden;
  background: rgba(242, 241, 239, 0.08);
}
.readout-bar .seg { transition: width 0.6s ease; }
.readout-bar .is-favor { background: var(--lime-500); }
.readout-bar .is-undecided { background: rgba(242, 241, 239, 0.4); }
.readout-bar .is-against { background: var(--gray-600); }
.readout-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  color: rgba(242, 241, 239, 0.78);
}
.readout-legend span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.readout-legend b { font-weight: 600; color: var(--cream-100); font-variant-numeric: tabular-nums; }

@media (max-width: 700px) {
  .crowd-readout { inset-inline-start: 16px; }
}
</style>
