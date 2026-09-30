<template>
  <!-- Una fila de Biankas: asoman por un borde (`visiblePx`) o se ven enteras. Miran al cursor, saltan
       al entrar en pantalla y al pulsarlas. Decorativa (aria-hidden). -->
  <!-- La caja mide lo que mide su contenedor; el lienzo sobresale por arriba (`lift`) para que quepan el salto, el
       júbilo y los gorros altos sin que el borde del lienzo los corte «como una máscara demasiado justa». -->
  <div class="bianka-row-box" aria-hidden="true" @click="onClick">
    <canvas ref="canvas" class="bianka-row" :style="{ top: `-${lift}px`, height: `calc(100% + ${lift}px)` }"></canvas>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { drawBianka, makeLook, rand } from '../lib/biankaSprite'

const props = defineProps({
  // Tamaño de cada celda de píxel.
  pixel: { type: Number, default: 3 },
  // Alto de sprite que se ve desde arriba (asomando por un borde). null = enteras.
  visiblePx: { type: Number, default: null },
  // 'favor' = todas convencidas (lima) · 'mix' = reparto de opiniones
  mood: { type: String, default: 'mix' },
  // Ancho de cada hueco, en celdas de la retícula de la Bianka.
  slotCells: { type: Number, default: 24 },
})

const canvas = ref(null)
// aire por encima: gorro de mago (6 celdas) + salto (4) + júbilo (2) + 2 de margen
const lift = computed(() => 14 * props.pixel)
let ctx = null
let W = 0, H = 0, dpr = 1
let agents = []
let raf = null, running = false, visible = false, last = 0, now = 0, entered = false, enteredAt = 0
let pointer = null
let io = null, ro = null
const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const bucketFor = (i) => (props.mood === 'favor' ? 'favor' : ['favor', 'undecided', 'favor', 'against', 'undecided'][i % 5])

const size = () => {
  const el = canvas.value
  if (!el) return
  const w = el.clientWidth, h = el.clientHeight
  if (!w || !h) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  el.width = Math.round(w * dpr); el.height = Math.round(h * dpr)
  ctx = el.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
  const changed = Math.abs(w - W) > 40 || !agents.length
  W = w; H = h
  if (changed) seed()
  paint()
}

const seed = () => {
  const P = props.pixel
  const slot = props.slotCells * P
  const n = Math.max(3, Math.ceil(W / slot) + 1)
  agents = Array.from({ length: n }, (_, i) => ({
    x: i * slot - slot * 0.35 + rand(-P * 2, P * 2),
    look: { ...makeLook(), pose: null },   // la fila asoma por un borde: sin paletas
    mirror: i % 2 === 1,
    bucket: bucketFor(i),
    phase: Math.random() * 3,
    hopAt: -10,
    delay: (i / n) * 0.9,
    blink: rand(0, 4),
  }))
}

// y de la esquina superior de la retícula de cada Bianka. Si solo asoman (`visiblePx`), el borde
// inferior del lienzo las corta: se ve únicamente la parte de arriba (orejas y cara).
const spriteTop = () => (props.visiblePx == null ? H - 29 * props.pixel - 2 : H - props.visiblePx)

const paint = () => {
  if (!ctx) return
  const P = props.pixel
  ctx.clearRect(0, 0, W, H)
  ctx.imageSmoothingEnabled = false
  const y0 = spriteTop()
  for (const a of agents) {
    const since = entered ? now - enteredAt - a.delay : -1
    // hasta que entra en pantalla, escondidas bajo el borde; luego suben de un salto
    const rise = since < 0 ? 34 * P : since < 0.3 ? Math.ceil((1 - since / 0.3) * 4) * P * 2 : 0
    const hopT = now - a.hopAt
    const hop = hopT >= 0 && hopT < 0.34 ? Math.round(Math.sin((Math.PI * hopT) / 0.34) * 4) * P : 0
    const cheer = props.mood === 'favor' && since > 0.5 ? (((now + a.phase) % 2.4) < 0.24 ? P * 2 : 0) : 0
    const breath = (((now + a.phase) / 1.6) % 1) < 0.5 ? 0 : P
    const cx = a.x + 13 * P, cy = y0 + 16 * P
    let gaze = [0, 0]
    if (pointer) {
      const dx = pointer.x - cx, dy = pointer.y - cy
      if (Math.hypot(dx, dy) < 420) gaze = [Math.abs(dx) > 16 ? Math.sign(dx) : 0, Math.abs(dy) > 16 ? Math.sign(dy) : 0]
    }
    drawBianka(ctx, {
      x: a.x, y: y0 + rise + breath - hop - cheer, P, look: a.look, bucket: a.bucket, mirror: a.mirror, now,
      gaze, blink: ((now + a.blink) % 3.6) > 3.45, happy: props.mood === 'favor' && since > 0.5, talking: false,
    })
  }
}

const tick = (ts) => {
  raf = null
  if (!running) return
  now += Math.min(0.05, (ts - last) / 1000 || 0.016); last = ts
  paint()
  raf = requestAnimationFrame(tick)
}
const start = () => { if (running || reduced || !visible || document.hidden) return; running = true; last = performance.now(); raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null }
const onVis = () => (document.hidden ? stop() : start())

const onPointer = (e) => {
  const el = canvas.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const x = e.clientX - r.left, y = e.clientY - r.top
  pointer = { x, y }
}
const onClick = (e) => {
  const r = canvas.value.getBoundingClientRect()
  const x = e.clientX - r.left
  const P = props.pixel
  for (const a of agents) if (x > a.x + 4 * P && x < a.x + 22 * P) a.hopAt = now
}

onMounted(() => {
  size()
  ro = new ResizeObserver(size); ro.observe(canvas.value)
  io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting
    if (visible && !entered) { entered = true; enteredAt = now }
    visible ? start() : stop()
  }, { threshold: 0.15 })
  io.observe(canvas.value)
  window.addEventListener('pointermove', onPointer, { passive: true })
  document.addEventListener('visibilitychange', onVis)
  if (reduced) { entered = true; enteredAt = -100; now = 10; paint() }
})
onUnmounted(() => {
  stop(); ro?.disconnect(); io?.disconnect()
  window.removeEventListener('pointermove', onPointer)
  document.removeEventListener('visibilitychange', onVis)
})
</script>

<style scoped>
.bianka-row-box { position: relative; width: 100%; height: 100%; cursor: pointer; }
.bianka-row { position: absolute; left: 0; display: block; width: 100%; image-rendering: pixelated; pointer-events: none; }
</style>
