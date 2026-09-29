<template>
  <Teleport to="body">
    <div v-if="isActive && currentStep" class="tour-root" @keydown.esc="stop">
      <!-- Backdrop with 4 panels forming a cutout around the target (if any) -->
      <div class="tour-backdrop" :style="backdropTopStyle"  @click="onBackdropClick"></div>
      <div class="tour-backdrop" :style="backdropBottomStyle" @click="onBackdropClick"></div>
      <div class="tour-backdrop" :style="backdropLeftStyle" @click="onBackdropClick"></div>
      <div class="tour-backdrop" :style="backdropRightStyle" @click="onBackdropClick"></div>

      <!-- Highlight ring around the target -->
      <div
        v-if="hasAnchor"
        class="tour-ring"
        :style="ringStyle"
      ></div>

      <!-- Tooltip card -->
      <div
        ref="cardEl"
        class="tour-card"
        :class="[`placement-${resolvedPlacement}`, { floating: !hasAnchor }]"
        :style="cardStyle"
        role="dialog"
        aria-modal="true"
      >
        <div class="tour-header">
          <span class="tour-badge">{{ $t('tutorial.badge') }}</span>
          <span class="tour-count">{{ index + 1 }} / {{ total }}</span>
        </div>
        <h3 class="tour-title">{{ resolvedTitle }}</h3>
        <p class="tour-body">{{ resolvedBody }}</p>
        <div class="tour-footer">
          <button class="tour-skip" @click="stop">{{ $t('tutorial.skip') }}</button>
          <div class="tour-nav">
            <button
              class="tour-btn ghost"
              :disabled="isFirst"
              @click="prev"
            >{{ $t('tutorial.back') }}</button>
            <button class="tour-btn primary" @click="next">
              {{ isLast ? $t('tutorial.finish') : $t('tutorial.next') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch, ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTutorial } from '../composables/useTutorial'

const { t } = useI18n()
const {
  isActive, currentStep, index, total, isFirst, isLast,
  next, prev, stop,
} = useTutorial()

// ── Rect tracking ───────────────────────────────────────────────────────────
const rect = ref(null) // { x, y, w, h } in viewport coords
// Ancho útil sin la barra de scroll: con innerWidth la tarjeta quedaba debajo de ella.
const viewportSize = () => ({
  w: document.documentElement.clientWidth || window.innerWidth,
  h: document.documentElement.clientHeight || window.innerHeight,
})
const viewport = ref(viewportSize())

const resolveSelector = () => {
  const step = currentStep.value
  if (!step) return null
  const sel = step.selector
  if (!sel) return null
  if (typeof sel === 'function') {
    try { return sel() } catch (_) { return null }
  }
  try { return document.querySelector(sel) } catch (_) { return null }
}

const measure = () => {
  viewport.value = viewportSize()
  const el = resolveSelector()
  if (!el) { rect.value = null; return }
  const r = el.getBoundingClientRect()
  if (r.width === 0 && r.height === 0) { rect.value = null; return }
  const pad = currentStep.value?.padding ?? 8
  rect.value = {
    x: Math.max(0, r.left - pad),
    y: Math.max(0, r.top  - pad),
    w: r.width  + pad * 2,
    h: r.height + pad * 2,
  }
}

let rafId = null
const scheduleMeasure = () => {
  if (rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = null
    measure()
  })
}

// Scroll target into view before measuring
const scrollIntoView = async () => {
  const el = resolveSelector()
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
  // Wait for the smooth-scroll animation to settle a bit.
  await new Promise(r => setTimeout(r, 350))
}

watch(
  () => [isActive.value, index.value, currentStep.value?.selector],
  async () => {
    if (!isActive.value) return
    await nextTick()
    const waitMs = currentStep.value?.waitMs ?? 0
    if (waitMs) await new Promise(r => setTimeout(r, waitMs))
    await scrollIntoView()
    measure()
  },
  { immediate: true }
)

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
  cardObserver?.disconnect()
})

// ── Derived styles ──────────────────────────────────────────────────────────
const hasAnchor = computed(() => rect.value !== null)

const ringStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { x, y, w, h } = rect.value
  return {
    left:   `${x}px`,
    top:    `${y}px`,
    width:  `${w}px`,
    height: `${h}px`,
  }
})

// Four backdrops form a "hole" around the target rect.
const backdropTopStyle = computed(() => {
  if (!rect.value) return { inset: '0 0 0 0' } // full cover when no anchor
  const { y } = rect.value
  return {
    left: 0, top: 0, right: 0, height: `${Math.max(0, y)}px`
  }
})
const backdropBottomStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { y, h } = rect.value
  return {
    left: 0, right: 0, top: `${y + h}px`, bottom: 0
  }
})
const backdropLeftStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { x, y, h } = rect.value
  return {
    left: 0, top: `${y}px`, height: `${h}px`, width: `${Math.max(0, x)}px`
  }
})
const backdropRightStyle = computed(() => {
  if (!rect.value) return { display: 'none' }
  const { x, y, w, h } = rect.value
  return {
    left: `${x + w}px`, top: `${y}px`, height: `${h}px`, right: 0
  }
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
  const want = currentStep.value?.placement || 'auto'
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
  const step = currentStep.value
  if (!step) return ''
  if (step.title) return step.title
  if (step.titleKey) return t(step.titleKey, step.titleParams || {})
  return ''
})

const resolvedBody = computed(() => {
  const step = currentStep.value
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
  position: fixed;
  inset: 0;
  z-index: 99999;
  pointer-events: none;
  font-family: var(--kb-font-sans);
}

.tour-backdrop {
  position: fixed;
  background: rgba(0, 0, 0, 0.62);
  pointer-events: auto;
  transition: all 120ms ease-out;
}

.tour-ring {
  position: fixed;
  pointer-events: none;
  border: 2px solid var(--kb-accent-line);
  box-shadow:
    0 0 0 2px rgba(204, 230, 115, 0.25),
    0 0 28px 4px rgba(204, 230, 115, 0.45);
  border-radius: 4px;
  animation: tour-pulse 1.8s ease-in-out infinite;
  transition: all 150ms ease-out;
}

@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(204, 230, 115, 0.25), 0 0 28px 4px rgba(204, 230, 115, 0.45); }
  50%      { box-shadow: 0 0 0 4px rgba(204, 230, 115, 0.18), 0 0 40px 8px rgba(204, 230, 115, 0.55); }
}

.tour-card {
  position: fixed;
  background: #FFFFFF;
  color: var(--kb-text);
  border: 1px solid var(--kb-text);
  box-shadow: 8px 8px 0 rgba(0, 0, 0, 0.12);
  pointer-events: auto;
  padding: 18px 20px 16px;
  transition: all 180ms cubic-bezier(0.22, 1, 0.36, 1);
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
</style>
