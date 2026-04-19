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
const viewport = ref({ w: window.innerWidth, h: window.innerHeight })

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
  viewport.value = { w: window.innerWidth, h: window.innerHeight }
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

const resolvedPlacement = computed(() => {
  const want = currentStep.value?.placement || 'auto'
  if (!rect.value) return 'center'
  if (want !== 'auto') return want
  const { x, y, w, h } = rect.value
  const { w: vw, h: vh } = viewport.value
  const space = {
    top:    y,
    bottom: vh - (y + h),
    left:   x,
    right:  vw - (x + w),
  }
  // Prefer bottom when there is room, otherwise the side with most space.
  if (space.bottom >= CARD_H_ESTIMATE + MARGIN) return 'bottom'
  if (space.top    >= CARD_H_ESTIMATE + MARGIN) return 'top'
  if (space.right  >= CARD_W + MARGIN) return 'right'
  if (space.left   >= CARD_W + MARGIN) return 'left'
  return 'bottom'
})

const cardStyle = computed(() => {
  const r = rect.value
  const { w: vw, h: vh } = viewport.value
  if (!r || resolvedPlacement.value === 'center') {
    return {
      left:  `calc(50% - ${CARD_W / 2}px)`,
      top:   `calc(50% - 100px)`,
      width: `${CARD_W}px`,
    }
  }
  let left = 0, top = 0
  const { x, y, w, h } = r
  switch (resolvedPlacement.value) {
    case 'bottom':
      left = Math.min(Math.max(MARGIN, x + w / 2 - CARD_W / 2), vw - CARD_W - MARGIN)
      top  = y + h + 14
      break
    case 'top':
      left = Math.min(Math.max(MARGIN, x + w / 2 - CARD_W / 2), vw - CARD_W - MARGIN)
      top  = y - CARD_H_ESTIMATE - 14
      break
    case 'right':
      left = x + w + 14
      top  = Math.min(Math.max(MARGIN, y + h / 2 - CARD_H_ESTIMATE / 2), vh - CARD_H_ESTIMATE - MARGIN)
      break
    case 'left':
      left = x - CARD_W - 14
      top  = Math.min(Math.max(MARGIN, y + h / 2 - CARD_H_ESTIMATE / 2), vh - CARD_H_ESTIMATE - MARGIN)
      break
  }
  return {
    left:  `${Math.round(left)}px`,
    top:   `${Math.round(Math.max(MARGIN, top))}px`,
    width: `${CARD_W}px`,
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
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
  border: 2px solid #FF4500;
  box-shadow:
    0 0 0 2px rgba(255, 69, 0, 0.25),
    0 0 28px 4px rgba(255, 69, 0, 0.45);
  border-radius: 4px;
  animation: tour-pulse 1.8s ease-in-out infinite;
  transition: all 150ms ease-out;
}

@keyframes tour-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(255, 69, 0, 0.25), 0 0 28px 4px rgba(255, 69, 0, 0.45); }
  50%      { box-shadow: 0 0 0 4px rgba(255, 69, 0, 0.18), 0 0 40px 8px rgba(255, 69, 0, 0.55); }
}

.tour-card {
  position: fixed;
  background: #FFFFFF;
  color: #000;
  border: 1px solid #000;
  box-shadow: 8px 8px 0 rgba(0, 0, 0, 0.12);
  pointer-events: auto;
  padding: 18px 20px 16px;
  transition: all 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.tour-card.floating {
  border: 1px solid #000;
}

.tour-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.tour-badge {
  background: #FF4500;
  color: #fff;
  padding: 3px 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.62rem;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  font-weight: 700;
}

.tour-count {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  color: #999;
  letter-spacing: 1px;
}

.tour-title {
  font-size: 1.08rem;
  font-weight: 600;
  margin: 0 0 8px 0;
  line-height: 1.3;
  color: #000;
}

.tour-body {
  font-size: 0.88rem;
  line-height: 1.55;
  color: #333;
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
  color: #999;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 1px;
  cursor: pointer;
  padding: 6px 2px;
  text-transform: uppercase;
}

.tour-skip:hover { color: #333; }

.tour-nav {
  display: flex;
  gap: 8px;
}

.tour-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.8px;
  padding: 8px 14px;
  cursor: pointer;
  border: 1px solid #000;
  text-transform: uppercase;
  transition: transform 120ms ease, background 120ms ease;
}

.tour-btn.ghost {
  background: #fff;
  color: #000;
}

.tour-btn.ghost:hover:not(:disabled) {
  background: #F5F5F5;
}

.tour-btn.ghost:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.tour-btn.primary {
  background: #000;
  color: #fff;
  border-color: #000;
}

.tour-btn.primary:hover {
  background: #FF4500;
  border-color: #FF4500;
  transform: translateY(-1px);
}

/* Placement arrows */
.tour-card::before {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  background: #fff;
  border: 1px solid #000;
  transform: rotate(45deg);
}

.tour-card.placement-bottom::before {
  top: -7px; left: 50%; margin-left: -6px;
  border-right: none; border-bottom: none;
}
.tour-card.placement-top::before {
  bottom: -7px; left: 50%; margin-left: -6px;
  border-left: none; border-top: none;
}
.tour-card.placement-right::before {
  left: -7px; top: 50%; margin-top: -6px;
  border-top: none; border-right: none;
}
.tour-card.placement-left::before {
  right: -7px; top: 50%; margin-top: -6px;
  border-bottom: none; border-left: none;
}
.tour-card.floating::before,
.tour-card.placement-center::before {
  display: none;
}

@media (max-width: 640px) {
  .tour-card {
    width: calc(100vw - 32px) !important;
    left: 16px !important;
    right: 16px !important;
  }
}
</style>
