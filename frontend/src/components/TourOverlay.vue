<template>
  <Teleport to="body">
    <Transition name="tour-fade">
      <div v-if="isActive && currentStep" class="tour-root" @keydown.esc="stop">
        <!-- Capa oscura: UN solo elemento con una sombra enorme y un hueco. Se mueve de un paso a otro sin cortes -->
        <div class="tour-dim" :class="{ animate }" :style="holeStyle"></div>

        <!-- Bloqueo del clic fuera del hueco (invisible): deja pasar el clic solo al elemento destacado -->
        <div class="tour-block" :style="blockTopStyle"    @click="onBackdropClick"></div>
        <div class="tour-block" :style="blockBottomStyle" @click="onBackdropClick"></div>
        <div class="tour-block" :style="blockLeftStyle"   @click="onBackdropClick"></div>
        <div class="tour-block" :style="blockRightStyle"  @click="onBackdropClick"></div>

        <!-- Anillo de luz alrededor del elemento -->
        <div class="tour-ring" :class="{ animate, on: ringOn }" :style="holeStyle"></div>

        <!-- Tarjeta -->
        <div
          ref="cardEl"
          class="tour-card"
          :class="[`placement-${resolvedPlacement}`, { floating: !hasAnchor, hidden: !cardVisible }]"
          :style="cardStyle"
          role="dialog"
          aria-modal="true"
        >
          <div class="tour-header">
            <span class="tour-badge">{{ $t('tutorial.badge') }}</span>
            <span class="tour-count">{{ shownIndex + 1 }} / {{ total }}</span>
          </div>
          <h3 class="tour-title">{{ resolvedTitle }}</h3>
          <p class="tour-body">{{ resolvedBody }}</p>
          <div class="tour-footer">
            <button class="tour-skip" @click="stop">{{ $t('tutorial.skip') }}</button>
            <div class="tour-nav">
              <button
                class="tour-btn ghost"
                :disabled="shownIndex === 0"
                @click="prev"
              >{{ $t('tutorial.back') }}</button>
              <button class="tour-btn primary" @click="next">
                {{ shownIndex === total - 1 ? $t('tutorial.finish') : $t('tutorial.next') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch, ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTutorial } from '../composables/useTutorial'

const { t } = useI18n()
const {
  state, isActive, currentStep, index, total, tourId,
  next, prev, stop,
} = useTutorial()

// ── Qué se ve ───────────────────────────────────────────────────────────────
// El paso al que se va (`index`) y el que se está mostrando (`shownIndex`) no son el mismo mientras dura
// la transición: la tarjeta cambia de texto y de sitio solo cuando la página ya está colocada. Antes
// cambiaba en el acto y saltaba mientras la página aún se desplazaba (el «flash»).
const shownIndex = ref(0)
const shownStep = computed(() => state.steps[shownIndex.value] || null)
const rect = ref(null)          // { x, y, w, h } del elemento destacado, en coordenadas de pantalla
const cardVisible = ref(false)
const ringOn = ref(false)
const animate = ref(false)      // los movimientos del hueco se animan solo al cambiar de paso, no al seguir un scroll
const moving = ref(false)       // mientras la página se coloca no se sigue el scroll

// Ancho útil sin la barra de scroll: con innerWidth la tarjeta quedaba debajo de ella.
const viewportSize = () => ({
  w: document.documentElement.clientWidth || window.innerWidth,
  h: document.documentElement.clientHeight || window.innerHeight,
})
const viewport = ref(viewportSize())

// El hueco de la capa oscura. Cerrado = un punto: la pantalla entera queda oscura.
const hole = ref({ x: viewport.value.w / 2, y: viewport.value.h / 2, w: 0, h: 0 })
const closeHole = () => {
  const h = hole.value
  hole.value = { x: h.x + h.w / 2, y: h.y + h.h / 2, w: 0, h: 0 }
}

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const nextFrame = () => new Promise(r => requestAnimationFrame(() => r()))

const resolveFor = (step) => {
  const sel = step?.selector
  if (!sel) return null
  if (typeof sel === 'function') {
    try { return sel() } catch (_) { return null }
  }
  try { return document.querySelector(sel) } catch (_) { return null }
}

const measureEl = (el, step) => {
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) return null
  const pad = step?.padding ?? 8
  return {
    x: Math.max(0, r.left - pad),
    y: Math.max(0, r.top  - pad),
    w: r.width  + pad * 2,
    h: r.height + pad * 2,
  }
}

// Parte del elemento que se ve de verdad: dentro de la pantalla y dentro de los contenedores con scroll que lo recortan.
const visibleFraction = (el) => {
  const r = el.getBoundingClientRect()
  const area = r.width * r.height
  if (!area) return 0
  const { w: vw, h: vh } = viewportSize()
  let box = { l: 0, t: 0, r: vw, b: vh }
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const cs = getComputedStyle(p)
    if (cs.overflowX === 'visible' && cs.overflowY === 'visible') continue
    const pr = p.getBoundingClientRect()
    box = { l: Math.max(box.l, pr.left), t: Math.max(box.t, pr.top), r: Math.min(box.r, pr.right), b: Math.min(box.b, pr.bottom) }
  }
  const iw = Math.max(0, Math.min(r.right, box.r) - Math.max(r.left, box.l))
  const ih = Math.max(0, Math.min(r.bottom, box.b) - Math.max(r.top, box.t))
  return (iw * ih) / area
}

// ¿Hay que mover la página? Solo si el elemento no se ve entero y centrarlo lo cambia de verdad
// (un bloque más alto que la pantalla ya centrado no se vuelve a mover).
const needsScroll = (el) => {
  if (visibleFraction(el) > 0.98) return false
  const r = el.getBoundingClientRect()
  const { h: vh } = viewportSize()
  return Math.abs((r.top + r.height / 2) - vh / 2) > 40
}

// Espera a que el elemento deje de moverse (fin del scroll suave), con tope.
const waitUntilSettled = async (el, maxMs = 1200) => {
  const t0 = performance.now()
  let still = 0, last = null
  while (performance.now() - t0 < maxMs) {
    await nextFrame()
    const r = el.getBoundingClientRect()
    const now = `${Math.round(r.top)}|${Math.round(r.left)}`
    still = now === last ? still + 1 : 0
    last = now
    if (still >= 4 && performance.now() - t0 > 80) return
  }
}

let runId = 0
const goToStep = async (idx, my) => {
  const step = state.steps[idx]
  if (!step) return
  const stale = () => my !== runId

  // 1) la tarjeta se retira antes de cambiar nada
  cardVisible.value = false
  ringOn.value = false
  await nextTick()
  if (step.waitMs) await sleep(step.waitMs)
  if (stale()) return

  // 2) la página se coloca con la pantalla oscura entera (el hueco se cierra mientras se desplaza)
  const el = resolveFor(step)
  if (el && needsScroll(el)) {
    moving.value = true
    animate.value = true
    closeHole()
    await sleep(reducedMotion() ? 0 : 170)
    if (stale()) return
    // Un desplazamiento largo (un bloque de miles de píxeles) se hace de golpe bajo la pantalla oscura:
    // el scroll suave tardaría más de un segundo y la tarjeta no aparecería hasta el final.
    const r0 = el.getBoundingClientRect()
    const far = Math.abs((r0.top + r0.height / 2) - viewportSize().h / 2) > viewportSize().h * 1.5
    el.scrollIntoView({ behavior: reducedMotion() || far ? 'auto' : 'smooth', block: 'center', inline: 'center' })
    await waitUntilSettled(el)
    if (stale()) return
  }
  const target = measureEl(el, step)

  // 3) todo a la vez: texto, posición de la tarjeta y hueco
  viewport.value = viewportSize()
  rect.value = target
  shownIndex.value = idx
  if (target) {
    if (hole.value.w === 0 && hole.value.h === 0) {
      // el hueco nace en el centro del elemento y se abre
      animate.value = false
      hole.value = { x: target.x + target.w / 2, y: target.y + target.h / 2, w: 0, h: 0 }
      await nextFrame()
      if (stale()) return
    }
    animate.value = true
    hole.value = target
  } else {
    animate.value = true
    closeHole()
  }
  await nextTick()
  await nextFrame()          // da tiempo a medir la altura real de la tarjeta antes de enseñarla
  if (stale()) return
  moving.value = false
  cardVisible.value = true
  ringOn.value = !!target
}

watch(
  () => [isActive.value, index.value, tourId.value],
  async ([active]) => {
    const my = ++runId
    if (!active) {
      cardVisible.value = false
      ringOn.value = false
      moving.value = false
      rect.value = null
      shownIndex.value = 0
      animate.value = false
      const v = viewportSize()
      hole.value = { x: v.w / 2, y: v.h / 2, w: 0, h: 0 }
      return
    }
    await nextTick()
    await goToStep(index.value, my)
  },
  { immediate: true }
)

// Seguir al elemento si cambia el tamaño de la ventana o la persona mueve la página (sin animar: el hueco pegado al elemento)
const measureNow = () => {
  viewport.value = viewportSize()
  if (moving.value || !cardVisible.value) return
  const step = shownStep.value
  const target = measureEl(resolveFor(step), step)
  if (!target) return
  animate.value = false
  rect.value = target
  hole.value = target
}

let rafId = null
const scheduleMeasure = () => {
  if (rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = null
    measureNow()
  })
}

// Keyboard, resize and scroll listeners
const onKeydown = (e) => {
  if (!isActive.value) return
  if (e.key === 'Escape') stop()
  else if (e.key === 'ArrowRight' || e.key === 'Enter') next()
  else if (e.key === 'ArrowLeft')  prev()
}

onMounted(() => {
  window.addEventListener('resize', scheduleMeasure, { passive: true })
  window.addEventListener('scroll', scheduleMeasure, { passive: true, capture: true })
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('resize', scheduleMeasure)
  window.removeEventListener('scroll', scheduleMeasure, { capture: true })
  window.removeEventListener('keydown', onKeydown)
  if (rafId) cancelAnimationFrame(rafId)
  runId++
  cardObserver?.disconnect()
})

// ── Derived styles ──────────────────────────────────────────────────────────
const hasAnchor = computed(() => rect.value !== null)

const holeStyle = computed(() => {
  const { x, y, w, h } = hole.value
  return {
    left:   `${x}px`,
    top:    `${y}px`,
    width:  `${w}px`,
    height: `${h}px`,
  }
})

// Cuatro paneles invisibles rodean el hueco para que el clic fuera del elemento no llegue a la página.
const blockTopStyle = computed(() => {
  if (!rect.value) return { inset: '0 0 0 0' } // sin elemento, todo bloqueado
  const { y } = rect.value
  return { left: 0, top: 0, right: 0, height: `${Math.max(0, y)}px` }
})
const blockBottomStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { y, h } = rect.value
  return { left: 0, right: 0, top: `${y + h}px`, bottom: 0 }
})
const blockLeftStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { x, y, h } = rect.value
  return { left: 0, top: `${y}px`, height: `${h}px`, width: `${Math.max(0, x)}px` }
})
const blockRightStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { x, y, w, h } = rect.value
  return { left: `${x + w}px`, top: `${y}px`, height: `${h}px`, right: 0 }
})

// Placement resolution
const CARD_W = 360
const CARD_H_ESTIMATE = 200
const MARGIN = 16
const GAP = 14
const ARROW_INSET = 18
const SIDES = ['bottom', 'top', 'right', 'left']
const OPPOSITE = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' }

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi))

// Tamaño real de la tarjeta (el texto cambia de un paso a otro): colocarla con
// una altura estimada la sacaba de la pantalla cuando el texto era largo.
const cardEl = ref(null)
const cardH = ref(CARD_H_ESTIMATE)
let cardObserver = null
watch(cardEl, (el) => {
  cardObserver?.disconnect()
  if (!el || typeof ResizeObserver === 'undefined') return
  cardObserver = new ResizeObserver(() => { cardH.value = el.offsetHeight || CARD_H_ESTIMATE })
  cardObserver.observe(el)
})

// En móvil la tarjeta ocupa el ancho entero menos los márgenes.
const cardW = computed(() => {
  const vw = viewport.value.w
  return vw <= 640 ? vw - MARGIN * 2 : Math.min(CARD_W, vw - MARGIN * 2)
})

const fits = (side, r) => {
  const { w: vw, h: vh } = viewport.value
  const need = (side === 'top' || side === 'bottom') ? cardH.value : cardW.value
  const space = {
    top:    r.y,
    bottom: vh - (r.y + r.h),
    left:   r.x,
    right:  vw - (r.x + r.w),
  }[side]
  return space >= need + GAP + MARGIN
}

// El lado pedido por el paso es una preferencia: si no cabe se prueba el
// opuesto y después los demás. Antes se respetaba a ciegas y la tarjeta se
// salía de la pantalla (p. ej. «right» de un bloque que ya está a la derecha).
const resolvedPlacement = computed(() => {
  const r = rect.value
  if (!r) return 'center'
  const want = shownStep.value?.placement || 'auto'
  const order = want === 'auto' || !OPPOSITE[want]
    ? SIDES
    : [want, OPPOSITE[want], ...SIDES.filter(s => s !== want && s !== OPPOSITE[want])]
  // El elemento es tan grande que no queda sitio a ningún lado: la tarjeta va
  // encima, dentro de la pantalla y sin flecha.
  return order.find(side => fits(side, r)) || 'overlay'
})

const cardStyle = computed(() => {
  const r = rect.value
  const { w: vw, h: vh } = viewport.value
  const cw = cardW.value
  const ch = cardH.value
  const maxLeft = vw - cw - MARGIN
  const maxTop = vh - ch - MARGIN
  if (!r || resolvedPlacement.value === 'center') {
    return {
      left:  `${Math.round(clamp((vw - cw) / 2, MARGIN, maxLeft))}px`,
      top:   `${Math.round(clamp((vh - ch) / 2, MARGIN, maxTop))}px`,
      width: `${cw}px`,
    }
  }
  const { x, y, w, h } = r
  const cx = x + w / 2
  const cy = y + h / 2
  let left = 0, top = 0
  switch (resolvedPlacement.value) {
    case 'bottom':
      left = cx - cw / 2
      top  = y + h + GAP
      break
    case 'top':
      left = cx - cw / 2
      top  = y - ch - GAP
      break
    case 'right':
      left = x + w + GAP
      top  = cy - ch / 2
      break
    case 'left':
      left = x - cw - GAP
      top  = cy - ch / 2
      break
    case 'overlay':
      left = cx - cw / 2
      top  = Math.min(y + h, vh) - ch - MARGIN
      break
  }
  left = clamp(left, MARGIN, maxLeft)
  top = clamp(top, MARGIN, maxTop)
  // La flecha sigue apuntando al centro del elemento aunque la tarjeta se
  // haya desplazado para caber.
  return {
    left:  `${Math.round(left)}px`,
    top:   `${Math.round(top)}px`,
    width: `${cw}px`,
    '--arrow-x': `${Math.round(clamp(cx - left, ARROW_INSET, cw - ARROW_INSET))}px`,
    '--arrow-y': `${Math.round(clamp(cy - top, ARROW_INSET, ch - ARROW_INSET))}px`,
  }
})

const resolvedTitle = computed(() => {
  const step = shownStep.value
  if (!step) return ''
  if (step.title) return step.title
  if (step.titleKey) return t(step.titleKey, step.titleParams || {})
  return ''
})

const resolvedBody = computed(() => {
  const step = shownStep.value
  if (!step) return ''
  if (step.body) return step.body
  if (step.bodyKey) return t(step.bodyKey, step.bodyParams || {})
  return ''
})

const onBackdropClick = () => {
  // Click outside target does nothing by default — prevents accidental
  // dismissal. Users dismiss via the Skip/Esc/Finish controls.
}
</script>

<style scoped>
.tour-root {
  /* Oscurecimiento de la web detrás del tutorial: lo justo para destacar el elemento sin taparla */
  --tour-dim: rgba(17, 17, 17, 0.38);
  --tour-move: 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  position: fixed;
  inset: 0;
  z-index: 99999;
  pointer-events: none;
  font-family: var(--kb-font-sans);
}

/* La capa oscura es la sombra de un hueco: un solo elemento, sin costuras ni solapes al moverse */
.tour-dim {
  position: fixed;
  border-radius: 6px;
  box-shadow: 0 0 0 100vmax var(--tour-dim);
  pointer-events: none;
}
.tour-dim.animate,
.tour-ring.animate {
  transition: left var(--tour-move), top var(--tour-move), width var(--tour-move), height var(--tour-move);
}

.tour-block {
  position: fixed;
  pointer-events: auto;
}

.tour-ring {
  position: fixed;
  pointer-events: none;
  border: 2px solid var(--kb-accent-line);
  box-shadow:
    0 0 0 2px rgba(204, 230, 115, 0.25),
    0 0 28px 4px rgba(204, 230, 115, 0.45);
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.18s ease;
}
.tour-ring.animate {
  transition: opacity 0.18s ease, left var(--tour-move), top var(--tour-move), width var(--tour-move), height var(--tour-move);
}
.tour-ring.on {
  opacity: 1;
  animation: tour-pulse 1.8s ease-in-out infinite;
}

@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(204, 230, 115, 0.25), 0 0 28px 4px rgba(204, 230, 115, 0.45); }
  50%      { box-shadow: 0 0 0 4px rgba(204, 230, 115, 0.18), 0 0 40px 8px rgba(204, 230, 115, 0.55); }
}

/* Entrada y salida del tutorial entero */
.tour-fade-enter-active { transition: opacity 0.22s ease; }
.tour-fade-leave-active { transition: opacity 0.16s ease; }
.tour-fade-enter-from,
.tour-fade-leave-to { opacity: 0; }

.tour-card {
  position: fixed;
  background: #FFFFFF;
  color: var(--kb-text);
  border: 1px solid var(--kb-text);
  box-shadow: 8px 8px 0 rgba(0, 0, 0, 0.12);
  pointer-events: auto;
  padding: 18px 20px 16px;
  opacity: 1;
  transform: translateY(0);
  transition: opacity 0.2s ease, transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}
/* Oculta mientras la página se coloca; cambia de texto y de sitio sin que se vea y entra ya en su lugar */
.tour-card.hidden {
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  transition-duration: 0.09s;
}

.tour-card.floating {
  border: 1px solid var(--kb-text);
}

.tour-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.tour-badge {
  background: var(--kb-accent-solid);
  color: var(--kb-accent-on);
  padding: 3px 8px;
  font-family: var(--kb-font-mono);
  font-size: 0.62rem;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-weight: 700;
}

.tour-count {
  font-family: var(--kb-font-mono);
  font-size: 0.72rem;
  color: var(--kb-subtle);
  letter-spacing: 1px;
}

.tour-title {
  font-size: 1.08rem;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
  color: var(--kb-text);
}

.tour-body {
  font-size: 0.88rem;
  line-height: 1.55;
  color: var(--kb-text-2);
  margin: 0 0 16px 0;
}

.tour-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.tour-skip {
  background: transparent;
  border: none;
  color: var(--kb-subtle);
  font-family: var(--kb-font-mono);
  font-size: 0.72rem;
  letter-spacing: 1px;
  cursor: pointer;
  padding: 6px 2px;
  text-transform: uppercase;
}

.tour-skip:hover { color: var(--kb-text-2); }

.tour-nav {
  display: flex;
  gap: 8px;
}

.tour-btn {
  font-family: var(--kb-font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.8px;
  padding: 8px 14px;
  cursor: pointer;
  border: 1px solid var(--kb-text);
  text-transform: uppercase;
  transition: transform 120ms ease, background 120ms ease;
}

.tour-btn.ghost {
  background: #fff;
  color: var(--kb-text);
}

.tour-btn.ghost:hover:not(:disabled) {
  background: var(--kb-soft);
}

.tour-btn.ghost:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.tour-btn.primary {
  background: var(--kb-text);
  color: #fff;
  border-color: var(--kb-text);
}

.tour-btn.primary:hover {
  background: var(--kb-accent-solid);
  border-color: var(--kb-accent-line);
  transform: translateY(-1px);
}

/* Placement arrows */
.tour-card::before {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  background: #fff;
  border: 1px solid var(--kb-text);
  transform: rotate(45deg);
}

.tour-card.placement-bottom::before {
  top: -7px; left: var(--arrow-x, 50%); margin-left: -6px;
  border-right: none; border-bottom: none;
}
.tour-card.placement-top::before {
  bottom: -7px; left: var(--arrow-x, 50%); margin-left: -6px;
  border-left: none; border-top: none;
}
.tour-card.placement-right::before {
  left: -7px; top: var(--arrow-y, 50%); margin-top: -6px;
  border-top: none; border-right: none;
}
.tour-card.placement-left::before {
  right: -7px; top: var(--arrow-y, 50%); margin-top: -6px;
  border-bottom: none; border-left: none;
}
.tour-card.floating::before,
.tour-card.placement-center::before,
.tour-card.placement-overlay::before {
  display: none;
}

@media (prefers-reduced-motion: reduce) {
  .tour-dim.animate,
  .tour-ring.animate,
  .tour-ring,
  .tour-card,
  .tour-fade-enter-active,
  .tour-fade-leave-active { transition: none; }
  .tour-ring.on { animation: none; }
}
</style>
