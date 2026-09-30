<template>
  <!-- Viñeta en pixel art de un paso del proceso, con la Bianka como protagonista.
       Sin texto dentro (sirve en cualquier idioma); decorativa: el paso se explica en el texto de al lado. -->
  <canvas ref="canvas" class="scene" :class="{ dim: !active }" aria-hidden="true"></canvas>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as LIB from '../lib/biankaSprite'

const { drawBianka, fixedLook, PAL } = LIB

const props = defineProps({
  // read · build · talk · report · chat
  scene: { type: String, required: true },
  // La viñeta arranca su bucle cuando pasa a activa (la Bianka que camina llega a su paso).
  active: { type: Boolean, default: true },
})

const canvas = ref(null)
let ctx = null
let W = 0, H = 0, dpr = 1
let raf = null, running = false, visible = false, activeSince = 0
let interObs = null
const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const P = 3
const LW = 208, LH = 160
const INK = PAL.k, LIME = PAL.l, DLIME = PAL.L, WHITE = PAL.w, GREY = PAL.g, CREAM = PAL.c

const look = (key, spec) => (LOOKS[key] ||= fixedLook(spec))
const LOOKS = {}

const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3)
const rect = (x, y, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)) }
const box = (x, y, w, h, fill = WHITE, shadow = true) => {
  if (shadow) rect(x + 3, y + 3, w, h, INK)
  rect(x, y, w, h, INK)
  rect(x + 2, y + 2, w - 4, h - 4, fill)
}
// bocadillo pixelado con pico hacia abajo (dir 1) o hacia arriba (dir -1)
const bubble = (x, y, w, h, tailX, dir = 1, fill = WHITE) => {
  box(x, y, w, h, fill)
  if (dir === 1) { rect(tailX, y + h, 6, 4, INK); rect(tailX + 2, y + h + 4, 3, 3, INK); rect(tailX + 2, y + h - 2, 2, 4, fill) }
  else { rect(tailX, y - 4, 6, 4, INK); rect(tailX + 2, y - 7, 3, 3, INK); rect(tailX + 2, y - 2, 2, 4, fill) }
}
const lines = (x, y, n, w, gap = 5, color = GREY, growth = 1) => {
  for (let i = 0; i < n; i++) rect(x, y + i * gap, i === n - 1 ? w * 0.6 * growth : w * growth, 2, color)
}
const typing = (x, y, t) => {
  for (let i = 0; i < 3; i++) rect(x + i * 6, y - Math.round(Math.max(0, Math.sin(t * 8 - i * 0.9)) * 2), 3, 3, INK)
}
const heart = (x, y, c = DLIME) => {
  ;[[1, 0], [3, 0], [0, 1], [1, 1], [2, 1], [3, 1], [4, 1], [0, 2], [1, 2], [2, 2], [3, 2], [4, 2], [1, 3], [2, 3], [3, 3], [2, 4]].forEach(([i, j]) => rect(x + i * 2, y + j * 2, 2, 2, c))
}
const bang = (x, y) => { rect(x, y, 3, 9, INK); rect(x, y + 12, 3, 3, INK) }
const quest = (x, y) => { ;[[0, 0], [1, 0], [2, 0], [2, 1], [1, 2], [1, 4]].forEach(([i, j]) => rect(x + i * 3, y + j * 3, 3, 3, INK)) }
const bob = (t, period = 1.4, amp = 1) => (((t / period) % 1) < 0.5 ? 0 : P * amp)
const blinkAt = (t) => (t % 3.2) > 3.05
const bianka = (lk, bucket, x, y, t, o = {}) => drawBianka(ctx, {
  x, y: y + (o.still ? 0 : bob(t + (o.phase || 0))) - (o.lift || 0), P, look: lk, bucket, mirror: !!o.mirror, now: t,
  gaze: o.gaze || [0, 0], blink: blinkAt(t + (o.phase || 0)), happy: !!o.happy, talking: !!o.talking,
})

// ── Escenas: cada una recibe t (s, en bucle) y dibuja sobre un lienzo de W×H ─────
const SCENES = {
  // 1 · Lee la realidad: recorre un documento y saca de él las entidades del grafo
  read: { period: 6, draw(t) {
    const reader = look('reader', { head: null, face: 'glasses', body: null })
    const sx = 96, sy = 18, sw = 50, sh = 76
    bianka(reader, 'undecided', 10, H - 29 * P - 4, t, { gaze: [1, Math.min(1, Math.floor(t / 1.5) - 1)] })
    box(sx, sy, sw, sh)
    lines(sx + 8, sy + 10, 8, sw - 16, 7, GREY)
    const scan = ease((t - 0.3) / 3.2)
    if (t > 0.3 && t < 3.6) rect(sx + 5, sy + 8 + scan * (sh - 24), sw - 10, 8, LIME)
    // entidades que salen del documento y se enlazan (el grafo)
    const nodes = [[W - 40, 24, 0], [W - 22, 54, 1], [W - 52, 62, 2], [W - 30, 94, 3], [W - 56, 100, 0]]
    const links = [[0, 1], [0, 2], [1, 3], [2, 4], [2, 3]]
    links.forEach(([a, b], i) => {
      const u = ease((t - 2.4 - i * 0.25) / 0.7); if (u <= 0) return
      const [ax, ay] = nodes[a], [bx, by] = nodes[b]
      for (let s = 0; s <= 8 * u; s++) rect(ax + (bx - ax) * (s / 8) + 3, ay + (by - ay) * (s / 8) + 3, 2, 2, INK)
    })
    nodes.forEach(([nx, ny, c], i) => {
      const u = ease((t - 1.0 - i * 0.35) / 0.4); if (u <= 0) return
      const s = Math.round(12 * u); const col = [LIME, WHITE, INK, LIME][c] || LIME
      rect(nx - s / 2 + 6, ny - s / 2 + 6, s, s, INK); rect(nx - s / 2 + 8, ny - s / 2 + 8, Math.max(0, s - 4), Math.max(0, s - 4), col)
    })
    // del papel a los nodos: puntitos de tinta viajando
    if (t > 1 && t < 5) for (let i = 0; i < 3; i++) { const u = ((t * 0.6 + i / 3) % 1); rect(sx + sw + (W - 56 - sx - sw) * u, sy + 30 + Math.sin((u + i) * 6) * 8, 3, 3, INK) }
  } },

  // 2 · Construye el mundo: personas que van apareciendo hasta llenar la cuadrícula
  build: { period: 7, poster: 3.9, draw(t) {
    const cols = 4, rows = 2, cw = 26 * P * 0.7, chh = 29 * P * 0.7
    const Q = 2
    const mk = (i) => look('b' + i, { ears: ['classic', 'up', 'v', 'flop', 'short'][i % 5], head: ['cap', 'beret', null, 'graduate', 'chef', null, 'beanie', 'hardhat'][i % 8], face: [null, 'glasses', null, null, 'mustache', null, 'sunglasses', null][i % 8], body: [null, null, 'bowtie', 'scarf', null, 'tie', null, 'coffee'][i % 8] })
    const buckets = ['favor', 'undecided', 'against', 'favor', 'undecided', 'favor', 'against', 'undecided']
    const total = cols * rows
    for (let i = 0; i < total; i++) {
      const col = i % cols, row = Math.floor(i / cols)
      const born = i < 3 ? 0 : 0.25 + (i - 3) * 0.35   // tres ya están al llegar; el resto se suma en ≈ 2 s (nunca una tarjeta a medio llenar)
      const u = ease((t - born) / 0.35); if (u <= 0) continue
      const x = 8 + col * ((W - 76) / (cols - 1)) + ((row % 2) ? 8 : 0), y = 8 + row * 58
      const wave = t > total * 0.5 + 1 && ((t - (total * 0.5 + 1)) * 6 - i) % (total * 3) < 1.2 ? -Q * 2 : 0
      drawBianka(ctx, { x, y: y + (u < 1 ? (1 - u) * 20 : 0) + wave + (u >= 1 ? bob(t + i * 0.3) / P : 0), P: Q, look: mk(i), bucket: buckets[i], mirror: i % 2 === 1, now: t, blink: blinkAt(t + i), gaze: [0, 0] })
    }
    // marco de «mundo» que se va completando
    const done = Math.min(1, t / 2.4)
    rect(4, H - 8, (W - 8) * done, 3, LIME); rect(4, H - 8, W - 8, 1, INK)
  } },

  // 3 · Ejecuta la simulación: dos conversan y una convence a la otra
  talk: { period: 8, draw(t) {
    const a = look('ta', { ears: 'up', head: 'cap', face: null, body: 'heart' })
    const b = look('tb', { ears: 'v', head: 'beret', face: null, body: 'scarf' })
    const convinced = t > 5.2
    bianka(a, 'favor', 8, H - 29 * P - 4, t, { talking: t > 0.6 && t < 2.2 || t > 4 && t < 5.2, gaze: [1, 0], phase: 0.3 })
    bianka(b, convinced ? 'favor' : 'undecided', W - 8 - 26 * P, H - 29 * P - 4, t, { mirror: true, talking: t > 2.4 && t < 3.8, gaze: [-1, 0], happy: t > 5.2 && t < 6.4, lift: t > 5.2 && t < 5.5 ? P * 3 : 0 })
    if (t > 0.5 && t < 2.3) { bubble(10, 12, 60, 34, 22, 1); if (t < 1.4) typing(24, 32, t); else { lines(20, 22, 3, 40, 6, GREY, ease((t - 1.4) / 0.4)); } }
    if (t > 2.3 && t < 4) { bubble(W - 82, 12, 64, 34, W - 40, 1); if (t < 3) typing(W - 70, 32, t); else quest(W - 56, 20) }
    if (t > 3.9 && t < 5.4) { bubble(10, 12, 74, 34, 22, 1); lines(20, 22, 3, 54, 6, GREY); heart(60, 24) }
    if (t > 5.3 && t < 7) { heart(W - 8 - 26 * P + 34, 22 - (t - 5.3) * 6, LIME); rect(W - 8 - 26 * P + 34, 22 - (t - 5.3) * 6 + 12, 12, 2, INK) }
  } },

  // 4 · Lee el informe: las barras de la opinión crecen y la analista lo repasa
  report: { period: 7, poster: 2.4, draw(t) {
    const analyst = look('an', { ears: 'classic', head: 'graduate', face: 'glasses', body: 'pencil' })
    bianka(analyst, 'undecided', 8, H - 29 * P - 4, t, { gaze: [1, 0], talking: t > 3 && t < 4.6 })
    const bx = 112, by = 14, bw = W - bx - 12, bh = H - 30
    box(bx, by, bw, bh, CREAM)
    const bars = [[LIME, 0.62], [WHITE, 0.26], [INK, 0.12]]
    bars.forEach(([col, hgt], i) => {
      const u = ease((t - 0.6 - i * 0.45) / 1.2)
      const w = (bw - 30) / 3 - 6, x = bx + 12 + i * (w + 10), full = bh - 26
      const h = Math.round(full * hgt * u)
      rect(x, by + bh - 10 - h, w, h, INK); rect(x + 2, by + bh - 10 - h + 2, Math.max(0, w - 4), Math.max(0, h - 4), col)
      if (u > 0.98) rect(x + w / 2 - 4, by + bh - 22 - h, 8, 3, INK)
    })
    rect(bx + 6, by + bh - 8, bw - 12, 2, INK)
    // sello de «hecho»
    if (t > 3.4) { const s = Math.round(10 * ease((t - 3.4) / 0.3)); rect(bx + bw - 18, by + 8, s, s, LIME); rect(bx + bw - 18, by + 8, s, 2, INK); rect(bx + bw - 18, by + 8 + s - 2, s, 2, INK) }
  } },

  // 5 · Conversa y profundiza: preguntas a una persona simulada y respuestas
  chat: { period: 8, draw(t) {
    const asker = look('as', { ears: 'flop', head: null, face: null, body: 'tie' })
    const talker = look('tk', { ears: 'up', head: 'headphones', face: null, body: null })
    bianka(asker, 'undecided', 8, H - 29 * P - 4, t, { gaze: [1, 0], talking: t > 0.6 && t < 1.8, phase: 0.2 })
    bianka(talker, 'favor', W - 8 - 26 * P, H - 29 * P - 4, t, { mirror: true, gaze: [-1, 0], talking: t > 2.6 && t < 5.4 })
    if (t > 0.5 && t < 4.4) { bubble(8, 8, 56, 28, 22, 1); if (t < 1.6) typing(20, 24, t); else { lines(16, 16, 2, 34, 6); } }
    if (t > 2.4) {
      const grow = ease((t - 2.4) / 1.2)
      bubble(W - 110, 24, 100, 46, W - 34 - 4, 1)
      if (t < 3.4) typing(W - 96, 50, t)
      else lines(W - 100, 34, 4, 80, 7, GREY, grow)
    }
    if (t > 5.6 && t < 7.4) { bubble(8, 8, 56, 28, 22, 1); quest(24, 12) }
    if (t > 6.2 && t < 7.8) { bubble(W - 110, 24, 100, 46, W - 34 - 4, 1); lines(W - 100, 34, 3, 80, 7, GREY); heart(W - 34, 30) }
  } },
}

const size = () => {
  const el = canvas.value
  if (!el) return
  // Tamaño lógico fijo: el píxel se ve siempre nítido y las escenas no dependen del ancho de la columna.
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  el.width = LW * dpr; el.height = LH * dpr
  ctx = el.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
  W = LW; H = LH
  paint(currentT())
}
const currentT = () => {
  const sc = SCENES[props.scene]
  if (reduced) return sc.period * 0.82           // fotograma «final», quieto
  if (!props.active) return sc.poster || 0       // antes de que llegue la Bianka: un fotograma de cartel (nunca una viñeta vacía)
  return ((performance.now() / 1000 - activeSince) % sc.period + sc.period) % sc.period
}
const paint = (t) => {
  if (!ctx || !W) return
  ctx.clearRect(0, 0, W, H)
  ctx.imageSmoothingEnabled = false
  SCENES[props.scene].draw(t)
}
const tick = (ts) => {
  raf = null
  if (!running) return
  paint(currentT())
  raf = requestAnimationFrame(tick)
}
const start = () => { if (running || reduced || !visible || document.hidden) return; running = true; raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null }
const onVis = () => (document.hidden ? stop() : start())

watch(() => props.active, (v) => { if (v) { activeSince = performance.now() / 1000 } paint(currentT()) })

onMounted(() => {
  activeSince = performance.now() / 1000
  size()
  interObs = new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop() }, { threshold: 0.05 })
  interObs.observe(canvas.value)
  document.addEventListener('visibilitychange', onVis)
  if (reduced) paint(currentT())
})
onUnmounted(() => { stop(); interObs?.disconnect(); document.removeEventListener('visibilitychange', onVis) })
</script>

<style scoped>
.scene {
  display: block;
  width: 208px;
  height: 160px;
  margin: 0 auto;
  image-rendering: pixelated;
  transition: opacity 0.5s ease, filter 0.5s ease;
}
.scene.dim { opacity: 0.72; filter: grayscale(0.2); }
</style>
