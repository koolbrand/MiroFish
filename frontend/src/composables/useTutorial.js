import { ref, computed, reactive } from 'vue'

/**
 * Minimal, dependency-free tutorial engine.
 *
 * Shared state lives at module scope so `useTutorial()` returns the same
 * controller from any component, and the single `<TourOverlay />` mounted
 * in App.vue reacts to it.
 *
 * A "tour" is a list of steps with:
 *   - selector: CSS selector OR () => Element  (optional — absent ⇒ centered)
 *   - titleKey / bodyKey: i18n keys (resolved by the overlay via vue-i18n)
 *   - placement: 'auto' | 'top' | 'bottom' | 'left' | 'right'
 *   - padding: px of breathing room around the highlighted element
 *   - waitMs: ms to wait after advancing before the step is "ready"
 *             (useful when the previous step's click animates in a DOM node)
 */

const state = reactive({
  active: false,
  tourId: null,
  steps: [],
  index: 0,
})

const SEEN_KEY_PREFIX = 'mirofish_tutorial_seen_v1_'

function markSeen(tourId) {
  try { localStorage.setItem(SEEN_KEY_PREFIX + tourId, '1') } catch (_) {}
}

function hasSeen(tourId) {
  try { return localStorage.getItem(SEEN_KEY_PREFIX + tourId) === '1' }
  catch (_) { return false }
}

function clearSeen(tourId) {
  try { localStorage.removeItem(SEEN_KEY_PREFIX + tourId) } catch (_) {}
}

function start(tourId, steps, { markOnStart = true } = {}) {
  if (!Array.isArray(steps) || steps.length === 0) return
  state.tourId = tourId
  state.steps = steps
  state.index = 0
  state.active = true
  if (markOnStart) markSeen(tourId)
}

function stop() {
  state.active = false
  state.tourId = null
  state.steps = []
  state.index = 0
}

function next() {
  if (state.index < state.steps.length - 1) {
    state.index++
  } else {
    stop()
  }
}

function prev() {
  if (state.index > 0) state.index--
}

function goTo(i) {
  if (i >= 0 && i < state.steps.length) state.index = i
}

/**
 * Auto-start a tour only if the user has not seen it before.
 * Returns true if the tour was started.
 */
function maybeAutoStart(tourId, steps) {
  if (hasSeen(tourId)) return false
  // Defer one frame so freshly-mounted anchors exist in the DOM.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => start(tourId, steps))
  })
  return true
}

export function useTutorial() {
  const currentStep = computed(() =>
    state.active ? state.steps[state.index] : null
  )
  const isActive = computed(() => state.active)
  const isFirst = computed(() => state.index === 0)
  const isLast = computed(() => state.index === state.steps.length - 1)
  const total = computed(() => state.steps.length)
  const index = computed(() => state.index)
  const tourId = computed(() => state.tourId)

  return {
    // read-only reactive
    state,
    currentStep,
    isActive,
    isFirst,
    isLast,
    total,
    index,
    tourId,
    // commands
    start,
    stop,
    next,
    prev,
    goTo,
    // helpers
    hasSeen,
    markSeen,
    clearSeen,
    maybeAutoStart,
  }
}
