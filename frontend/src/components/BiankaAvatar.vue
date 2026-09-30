<template>
  <!-- Una Bianka pequeña con vida propia (respira y parpadea). La misma `seed` da siempre la misma Bianka:
       cada proyecto del historial tiene «su cara». Decorativa (aria-hidden). -->
  <!-- La caja mide lo de siempre (el diseño no se mueve); el lienzo sobresale por arriba para que quepan los gorros
       altos (el de mago llega 6 celdas por encima de la cabeza) y el salto sin que el borde los corte. -->
  <span class="bianka-avatar" :style="{ width: `${w}px`, height: `${h}px` }" aria-hidden="true">
    <canvas ref="canvas" :style="{ top: `-${lift}px`, width: `${w}px`, height: `${h + lift}px` }"></canvas>
  </span>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { drawBianka, makeLook, fixedLook, seededRng } from '../lib/biankaSprite'

const props = defineProps({
  seed: { type: String, default: '' },
  // aspecto fijo (si se pasa, ignora seed): { ears, head, face, body } por id, o un aspecto completo de makeLook()
  look: { type: Object, default: null },
  bucket: { type: String, default: 'undecided' },
  pixel: { type: Number, default: 2 },
  mirror: { type: Boolean, default: false },
  // opinión → lima (favor) / blanca (undecided) / tinta (against)
  talking: { type: Boolean, default: false },
  // contenta: ojos felices y un saltito al pasar a true (p. ej. cuando el formulario está listo)
  happy: { type: Boolean, default: false },
  // px extra de lienzo por encima, para que quepa el salto
  headroom: { type: Number, default: 0 },
  // hacia dónde mira, en celdas: [-1, 0] a la izquierda (las del titular miran su texto)
  gaze: { type: Array, default: () => [0, 0] },
})

const canvas = ref(null)
const w = computed(() => 26 * props.pixel + 8)
const h = computed(() => 29 * props.pixel + 6 + props.headroom)
const lift = computed(() => 8 * props.pixel)   // aire por encima de la caja: 6 celdas de gorro + 2 de salto
let raf = null, visible = false, io = null, running = false, hopAt = -10
const phase = Math.random() * 3
const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
// sin paleta de votación: el lienzo del avatar es justo y la paleta sobresale de la silueta
// `look` puede ser un aspecto ya construido (con `key`: el de una Bianka de la multitud) o las piezas por id
const lk = props.look ? (props.look.key ? { ...props.look, pose: null } : fixedLook(props.look)) : { ...makeLook(props.seed ? seededRng(props.seed) : Math.random), pose: null }

const paint = (t) => {
  const el = canvas.value
  if (!el) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const H = h.value + lift.value
  if (el.width !== w.value * dpr) { el.width = w.value * dpr; el.height = H * dpr }
  const ctx = el.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, w.value, H)
  const P = props.pixel
  const breath = (((t + phase) / 1.6) % 1) < 0.5 ? 0 : P
  const hopT = t - hopAt
  const hop = hopT >= 0 && hopT < 0.34 ? Math.round(Math.sin((Math.PI * hopT) / 0.34) * 2) * P : 0
  drawBianka(ctx, { x: 4, y: 2 + lift.value + props.headroom + breath - hop, P, look: lk, bucket: props.bucket, mirror: props.mirror, now: t, blink: ((t + phase) % 3.8) > 3.65, talking: props.talking, happy: props.happy, gaze: props.gaze })
}
const tick = () => { raf = null; if (!running) return; paint(performance.now() / 1000); raf = requestAnimationFrame(tick) }
const start = () => { if (running || reduced || !visible || document.hidden) return; running = true; raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null }

watch(() => props.happy, (v) => { if (v && !reduced) hopAt = performance.now() / 1000 })
watch(() => [props.happy, props.bucket], () => paint(performance.now() / 1000))

onMounted(() => {
  paint(0)
  io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop() })
  io.observe(canvas.value)
})
onUnmounted(() => { stop(); io?.disconnect() })
</script>

<style scoped>
.bianka-avatar { display: block; flex: none; position: relative; }
.bianka-avatar canvas { position: absolute; left: 0; display: block; image-rendering: pixelated; pointer-events: none; }
</style>
