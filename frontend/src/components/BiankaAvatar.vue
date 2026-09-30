<template>
  <!-- Una Bianka pequeña con vida propia (respira y parpadea). La misma `seed` da siempre la misma Bianka:
       cada proyecto del historial tiene «su cara». Decorativa (aria-hidden). -->
  <canvas ref="canvas" class="bianka-avatar" :style="{ width: `${w}px`, height: `${h}px` }" aria-hidden="true"></canvas>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { drawBianka, makeLook, fixedLook, seededRng } from '../lib/biankaSprite'

const props = defineProps({
  seed: { type: String, default: '' },
  // aspecto fijo (si se pasa, ignora seed): { ears, head, face, body }
  look: { type: Object, default: null },
  bucket: { type: String, default: 'undecided' },
  pixel: { type: Number, default: 2 },
  mirror: { type: Boolean, default: false },
  // opinión → lima (favor) / blanca (undecided) / tinta (against)
  talking: { type: Boolean, default: false },
})

const canvas = ref(null)
const w = computed(() => 26 * props.pixel + 8)
const h = computed(() => 29 * props.pixel + 6)
let raf = null, visible = false, io = null, running = false
const phase = Math.random() * 3
const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const lk = props.look ? fixedLook(props.look) : makeLook(props.seed ? seededRng(props.seed) : Math.random)

const paint = (t) => {
  const el = canvas.value
  if (!el) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  if (el.width !== w.value * dpr) { el.width = w.value * dpr; el.height = h.value * dpr }
  const ctx = el.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, w.value, h.value)
  const P = props.pixel
  const breath = (((t + phase) / 1.6) % 1) < 0.5 ? 0 : P
  drawBianka(ctx, { x: 4, y: 2 + breath, P, look: lk, bucket: props.bucket, mirror: props.mirror, now: t, blink: ((t + phase) % 3.8) > 3.65, talking: props.talking, gaze: [0, 0] })
}
const tick = () => { raf = null; if (!running) return; paint(performance.now() / 1000); raf = requestAnimationFrame(tick) }
const start = () => { if (running || reduced || !visible || document.hidden) return; running = true; raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null }

onMounted(() => {
  paint(0)
  io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop() })
  io.observe(canvas.value)
})
onUnmounted(() => { stop(); io?.disconnect() })
</script>

<style scoped>
.bianka-avatar { display: block; flex: none; image-rendering: pixelated; }
</style>
