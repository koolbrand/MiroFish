<template>
  <nav class="wizard-stepper" :aria-label="t('stepper.ariaLabel')">
    <template v-for="(name, i) in stepNames" :key="i">
      <!-- Conector entre pasos -->
      <span
        v-if="i > 0"
        class="stepper-bar"
        :class="{ done: i < currentStep }"
      />

      <!-- Chip del paso -->
      <button
        type="button"
        class="stepper-chip"
        :class="{
          current: i + 1 === currentStep,
          done: i + 1 < currentStep,
          locked: isLocked(i + 1),
        }"
        :disabled="isLocked(i + 1) || i + 1 === currentStep"
        :aria-current="i + 1 === currentStep ? 'step' : null"
        :title="chipTitle(i + 1, name)"
        @click="goTo(i + 1)"
      >
        <span class="chip-num">
          <span v-if="i + 1 < currentStep" class="chip-check" aria-hidden="true">✓</span>
          <span v-else>{{ i + 1 }}</span>
        </span>
        <span v-if="i + 1 === currentStep" class="chip-name">{{ name }}</span>
      </button>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  currentStep: {
    type: Number,
    required: true,
    validator: (v) => v >= 1 && v <= 5,
  },
  projectId: { type: String, default: null },
  simulationId: { type: String, default: null },
  reportId: { type: String, default: null },
})

const emit = defineEmits(['before-navigate'])

const router = useRouter()
const { t, tm } = useI18n()

const stepNames = computed(() => tm('main.stepNames'))

function idForStep(step) {
  if (step === 1) return props.projectId
  if (step === 2 || step === 3) return props.simulationId
  if (step === 4 || step === 5) return props.reportId
  return null
}

function isLocked(step) {
  // Pasos futuros siempre están bloqueados
  if (step > props.currentStep) return true
  // Para pasos ≤ currentStep necesitamos el ID correspondiente
  return !idForStep(step)
}

function chipTitle(step, name) {
  if (step === props.currentStep) return name
  if (isLocked(step)) {
    return step > props.currentStep
      ? t('stepper.lockedFuture', { name })
      : t('stepper.lockedMissing', { name })
  }
  return t('stepper.goTo', { name })
}

function goTo(step) {
  if (isLocked(step) || step === props.currentStep) return
  emit('before-navigate', step)

  if (step === 1) {
    router.push({ name: 'Process', params: { projectId: props.projectId } })
  } else if (step === 2) {
    router.push({ name: 'Simulation', params: { simulationId: props.simulationId } })
  } else if (step === 3) {
    router.push({ name: 'SimulationRun', params: { simulationId: props.simulationId } })
  } else if (step === 4) {
    router.push({ name: 'Report', params: { reportId: props.reportId } })
  } else if (step === 5) {
    router.push({ name: 'Interaction', params: { reportId: props.reportId } })
  }
}
</script>

<style scoped>
.wizard-stepper {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stepper-bar {
  width: 18px;
  height: 2px;
  background: #E0E0E0;
  border-radius: 1px;
  transition: background-color 0.2s ease;
}

.stepper-bar.done {
  background: #000;
}

.stepper-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #999;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, opacity 0.15s ease;
}

.stepper-chip:hover:not(:disabled) {
  background: #F3F3F3;
  color: #000;
}

.stepper-chip:focus-visible {
  outline: 2px solid #2196F3;
  outline-offset: 2px;
}

.stepper-chip.done {
  color: #000;
}

.stepper-chip.current {
  color: #000;
  cursor: default;
}

.stepper-chip.locked {
  color: #CCC;
  cursor: not-allowed;
  opacity: 0.6;
}

.chip-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  border: 1.5px solid currentColor;
  background: #FFF;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.stepper-chip.done .chip-num {
  background: #000;
  color: #FFF;
  border-color: #000;
}

.stepper-chip.current .chip-num {
  background: #FF5722;
  color: #FFF;
  border-color: #FF5722;
}

.stepper-chip.locked .chip-num {
  border-color: #E0E0E0;
  color: #CCC;
}

.chip-check {
  font-size: 12px;
  line-height: 1;
}

.chip-name {
  white-space: nowrap;
  font-weight: 700;
  font-size: 13px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Responsive: oculta el nombre del paso actual en pantallas muy estrechas */
@media (max-width: 1100px) {
  .chip-name {
    display: none;
  }
  .stepper-bar {
    width: 12px;
  }
}
</style>
