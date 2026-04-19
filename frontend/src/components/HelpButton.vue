<template>
  <button
    class="help-btn"
    :class="{ dark: dark }"
    @click="onClick"
    :title="$t('tutorial.openTooltip')"
    :aria-label="$t('tutorial.openTooltip')"
  >
    <span class="help-q">?</span>
    <span class="help-label">{{ $t('tutorial.openLabel') }}</span>
  </button>
</template>

<script setup>
import { useTutorial } from '../composables/useTutorial'
import { getTour } from '../tours/tours'

const props = defineProps({
  tourId: { type: String, required: true },
  // Resolve a different tour id dynamically (e.g. based on current wizard step)
  resolve: { type: Function, default: null },
  dark: { type: Boolean, default: false },
})

const { start, clearSeen } = useTutorial()

const onClick = () => {
  const id = props.resolve ? props.resolve() : props.tourId
  const steps = getTour(id)
  if (!steps) return
  // Manual re-open — also clear the "seen" flag so the user can re-replay later.
  clearSeen(id)
  start(id, steps)
}
</script>

<style scoped>
.help-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid #E5E5E5;
  color: #333;
  padding: 4px 10px 4px 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  cursor: pointer;
  transition: all 0.15s ease;
}

.help-btn:hover {
  border-color: #FF4500;
  color: #FF4500;
}

.help-btn.dark {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.25);
}

.help-btn.dark:hover {
  color: #FF4500;
  border-color: #FF4500;
}

.help-q {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  line-height: 1;
}

.help-label {
  font-size: 0.65rem;
}

@media (max-width: 768px) {
  .help-label { display: none; }
}
</style>
