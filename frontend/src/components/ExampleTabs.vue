<template>
  <!-- Pestañas de los ejemplos: cada una es una situación distinta (consumo, B2B, precio, crisis, decisión pública).
       Con nombre visible —no puntos—: quien mira ve de un vistazo que hay más y de qué tipo. En móvil se desliza
       hacia los lados y el siguiente asoma por el borde. El caso elegido es de toda la página (ver `exampleCases.js`). -->
  <div class="ex-tabs" :class="{ 'on-ink': onInk }">
    <span class="ex-label" aria-hidden="true">{{ $t('home.casesLabel') }}</span>
    <div class="ex-scroller" ref="scroller" @scroll.passive="updateEdges" :class="{ 'has-left': edgeLeft, 'has-right': edgeRight }">
      <div class="ex-list" role="tablist" :aria-label="$t('home.casesAria')" @keydown="onKey">
        <button
          v-for="c in CASES"
          :id="`${uid}-tab-${c.id}`"
          :key="c.id"
          ref="tabEls"
          type="button"
          role="tab"
          class="ex-tab"
          :class="{ on: c.id === currentId }"
          :aria-selected="c.id === currentId"
          :tabindex="c.id === currentId ? 0 : -1"
          @click="choose(c.id)"
        >{{ $t(`home.cases.${c.id}.tab`) }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { CASES, useExampleCase } from '../lib/exampleCases'

// onInk: sobre la banda de tinta del informe (texto claro)
defineProps({ onInk: { type: Boolean, default: false } })

const { currentId, select } = useExampleCase()
const uid = `ex${Math.random().toString(36).slice(2, 7)}`
const scroller = ref(null)
const tabEls = ref([])
const edgeLeft = ref(false)
const edgeRight = ref(false)

const updateEdges = () => {
  const el = scroller.value
  if (!el) return
  edgeLeft.value = el.scrollLeft > 4
  edgeRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}

const choose = (id) => select(id)

// Flechas, Inicio y Fin cambian de pestaña (patrón de pestañas del WAI-ARIA)
const onKey = (e) => {
  const i = CASES.findIndex(c => c.id === currentId.value)
  let n = -1
  if (e.key === 'ArrowRight') n = (i + 1) % CASES.length
  else if (e.key === 'ArrowLeft') n = (i - 1 + CASES.length) % CASES.length
  else if (e.key === 'Home') n = 0
  else if (e.key === 'End') n = CASES.length - 1
  if (n < 0) return
  e.preventDefault()
  select(CASES[n].id)
  nextTick(() => document.getElementById(`${uid}-tab-${CASES[n].id}`)?.focus())
}

// la pestaña elegida se mantiene a la vista (en móvil, dentro de la tira que se desliza)
const reveal = () => {
  const el = scroller.value
  const tab = document.getElementById(`${uid}-tab-${currentId.value}`)
  if (!el || !tab) return
  const l = tab.offsetLeft - 16, r = tab.offsetLeft + tab.offsetWidth + 16
  if (l < el.scrollLeft) el.scrollTo({ left: l, behavior: 'smooth' })
  else if (r > el.scrollLeft + el.clientWidth) el.scrollTo({ left: r - el.clientWidth, behavior: 'smooth' })
}
watch(currentId, () => nextTick(reveal))

let ro = null
onMounted(() => {
  updateEdges()
  ro = new ResizeObserver(updateEdges)
  ro.observe(scroller.value)
})
onUnmounted(() => ro?.disconnect())
</script>

<style scoped>
.ex-tabs { display: flex; align-items: center; gap: 14px 18px; min-width: 0; }
.ex-label {
  flex: none;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--kb-muted);
}
.ex-scroller {
  position: relative;
  min-width: 0;
  flex: 1 1 auto;
  overflow-x: auto;
  scrollbar-width: none;
  scroll-snap-type: x proximity;
  overscroll-behavior-x: contain;
  padding: 4px 4px 7px;              /* aire para la sombra dura y el foco */
  margin: -4px -4px -7px;
}
.ex-scroller::-webkit-scrollbar { display: none; }
/* el borde que oculta más pestañas se funde: hay más a ese lado */
.ex-scroller.has-right { -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 36px), transparent); }
.ex-scroller.has-left { -webkit-mask-image: linear-gradient(to left, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to left, #000 calc(100% - 36px), transparent); }
.ex-scroller.has-left.has-right { -webkit-mask-image: linear-gradient(to right, transparent, #000 36px, #000 calc(100% - 36px), transparent); mask-image: linear-gradient(to right, transparent, #000 36px, #000 calc(100% - 36px), transparent); }
.ex-list { display: flex; gap: 8px; width: max-content; }
.ex-tab {
  flex: none;
  scroll-snap-align: start;
  padding: 10px 16px;
  border: 2px solid var(--ink-950);
  border-radius: 999px;
  background: var(--kb-surface);
  color: var(--kb-text);
  font: 700 0.9rem/1 var(--kb-font-sans);
  letter-spacing: -0.01em;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.ex-tab:hover:not(.on) { background: var(--lime-50); transform: translateY(-1px); }
.ex-tab.on { background: var(--lime-500); box-shadow: 3px 3px 0 var(--ink-950); transform: translate(-1px, -1px); }
.ex-tab:focus-visible { outline: 2px solid var(--ink-950); outline-offset: 3px; }

/* sobre tinta: contorno y rótulo claros; la elegida sigue en lima */
.on-ink .ex-label { color: rgba(255, 255, 255, 0.72); }
.on-ink .ex-tab { border-color: #fff; background: transparent; color: #fff; }
.on-ink .ex-tab:hover:not(.on) { background: rgba(255, 255, 255, 0.12); }
.on-ink .ex-tab.on { background: var(--lime-500); border-color: var(--lime-500); color: var(--ink-950); box-shadow: 3px 3px 0 rgba(255, 255, 255, 0.85); }
.on-ink .ex-tab:focus-visible { outline-color: #fff; }

@media (max-width: 640px) {
  .ex-tabs { flex-direction: column; align-items: stretch; gap: 10px; }
  .ex-tab { padding: 11px 16px; }
}
@media (prefers-reduced-motion: reduce) { .ex-tab { transition: none; } }
</style>
