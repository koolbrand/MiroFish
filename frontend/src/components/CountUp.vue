<template>
  <!-- Cuenta hacia arriba los números de una cifra («10–120», «20–30 min»)
       al entrar en pantalla. El lector de pantalla lee siempre el valor final. -->
  <span ref="el" class="count-up">
    <span class="sr-only">{{ value }}</span>
    <!-- la raya de un rango («20–120») va aparte, con aire a cada lado: con el interletrado apretado de la cifra grande se pegaba a los dígitos -->
    <span aria-hidden="true"><template v-for="(p, i) in shown" :key="i"><span v-if="p.sep" class="count-sep">{{ p.t }}</span><template v-else>{{ p.t }}</template></template></span>
  </span>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { onceInView } from '../composables/useReveal'

const props = defineProps({
  value: { type: String, required: true },
  duration: { type: Number, default: 1400 },
})

const el = ref(null)
const progress = ref(0)
let raf = null
let stopObs = null

// Trozos de texto y números: solo se animan los números.
const parts = computed(() =>
  props.value.split(/(\d+(?:[.,]\d+)?)/).map(p => (/^\d/.test(p) ? { n: parseFloat(p.replace(',', '.')), raw: p } : { s: p }))
)

const shown = computed(() =>
  parts.value.map(p => {
    if (p.s !== undefined) return { t: p.s.trim() === '–' || p.s.trim() === '-' ? '–' : p.s, sep: p.s.trim() === '–' || p.s.trim() === '-' }
    if (progress.value >= 1) return { t: p.raw }
    return { t: String(Math.round(p.n * progress.value)) }
  })
)

const run = () => {
  const t0 = performance.now()
  const frame = (now) => {
    const k = Math.min(1, (now - t0) / props.duration)
    progress.value = 1 - Math.pow(1 - k, 3)
    if (k < 1) raf = requestAnimationFrame(frame)
  }
  raf = requestAnimationFrame(frame)
}

onMounted(() => {
  stopObs = onceInView(el.value, () => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) progress.value = 1
    else run()
  }, 0.5)
})

onUnmounted(() => {
  stopObs?.()
  if (raf) cancelAnimationFrame(raf)
})
</script>

<style scoped>
.count-up { font-variant-numeric: tabular-nums; }
/* la raya del rango respira: aire a cada lado y sin el interletrado apretado de la cifra */
.count-sep { display: inline-block; margin-inline: 0.09em; letter-spacing: 0; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
