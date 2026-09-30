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
          ahead: i + 1 > currentStep && !isLocked(i + 1),
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
import { computed, reactive, ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulation, listSimulations } from '../api/simulation'
import { checkReportForSimulation } from '../api/report'

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

// Cada vista solo conoce los identificadores de «su» paso (la del paso 2 no sabe si ya hay informe), así que el
// indicador completa lo que falta preguntando al servidor hasta dónde ha llegado este proyecto. Así se puede ir
// a cualquier paso que ya exista —también hacia delante—, no solo volver atrás.
const ids = reactive({ project: props.projectId, simulation: props.simulationId, report: props.reportId })
const simStatus = ref(null)          // estado de la simulación (created · preparing · ready · running · …)
const reportStatus = ref(null)       // estado del informe (generating · completed · …) o null si no hay
let resolveSeq = 0

const PREPARED = ['ready', 'running', 'paused', 'stopped', 'completed', 'failed']

async function resolveProgress() {
  const seq = ++resolveSeq
  ids.project = props.projectId || ids.project
  ids.simulation = props.simulationId || null
  ids.report = props.reportId || null
  try {
    // desde el paso 1 solo se conoce el proyecto: la simulación más reciente de ese proyecto
    if (!ids.simulation && ids.project) {
      const r = await listSimulations(ids.project)
      const list = (r?.data || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
      if (seq !== resolveSeq) return
      ids.simulation = list[0]?.simulation_id || null
    }
    if (ids.simulation) {
      const [sim, rep] = await Promise.all([
        getSimulation(ids.simulation).catch(() => null),
        checkReportForSimulation(ids.simulation).catch(() => null),
      ])
      if (seq !== resolveSeq) return
      simStatus.value = sim?.data?.status || null
      ids.project = ids.project || sim?.data?.project_id || null
      ids.report = props.reportId || rep?.data?.report_id || null
      reportStatus.value = rep?.data?.has_report ? (rep.data.report_status || null) : null
    }
  } catch (e) {
    // sin red o sin permisos: el indicador se queda con lo que le pasó la vista (volver atrás sigue funcionando)
  }
}

onMounted(resolveProgress)
watch(() => [props.projectId, props.simulationId, props.reportId, props.currentStep], resolveProgress)

function idForStep(step) {
  if (step === 1) return ids.project
  if (step === 2 || step === 3) return ids.simulation
  if (step === 4 || step === 5) return ids.report
  return null
}

// ¿Existe ya ese paso? (el actual siempre; los demás, si hay con qué abrirlos)
// Hacia delante solo con el proyecto terminado (informe completo): en curso se avanza paso a paso,
// porque abrir el paso 3 de una simulación preparada y sin ejecutar la lanza.
function isAvailable(step) {
  if (step === props.currentStep) return true
  if (step > props.currentStep && reportStatus.value !== 'completed') return false
  if (!idForStep(step)) return false
  if (step === 3) return PREPARED.includes(simStatus.value)            // entorno preparado
  if (step === 5) return reportStatus.value === 'completed'            // informe terminado (la conversación lo necesita)
  return true
}

function isLocked(step) {
  return !isAvailable(step)
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
    router.push({ name: 'Process', params: { projectId: ids.project } })
  } else if (step === 2) {
    router.push({ name: 'Simulation', params: { simulationId: ids.simulation } })
  } else if (step === 3) {
    router.push({ name: 'SimulationRun', params: { simulationId: ids.simulation } })
  } else if (step === 4) {
    router.push({ name: 'Report', params: { reportId: ids.report } })
  } else if (step === 5) {
    router.push({ name: 'Interaction', params: { reportId: ids.report } })
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
  background: var(--kb-line);
  border-radius: 1px;
  transition: background-color 0.2s ease;
}

.stepper-bar.done {
  background: var(--kb-text);
}

.stepper-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--kb-subtle);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, opacity 0.15s ease;
}

.stepper-chip:hover:not(:disabled) {
  background: #F3F3F3;
  color: var(--kb-text);
}

.stepper-chip:focus-visible {
  outline: 2px solid #2196F3;
  outline-offset: 2px;
}

.stepper-chip.done {
  color: var(--kb-text);
}

.stepper-chip.current {
  color: var(--kb-text);
  cursor: default;
}

.stepper-chip.locked {
  color: var(--kb-line-strong);
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
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 700;
  border: 1.5px solid currentColor;
  background: #FFF;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.stepper-chip.done .chip-num {
  background: var(--kb-text);
  color: #FFF;
  border-color: var(--kb-text);
}

.stepper-chip.current .chip-num {
  background: var(--kb-accent-solid);
  color: var(--kb-accent-on);
  border-color: var(--kb-accent-line);
}

.stepper-chip.ahead { color: var(--kb-text); }
.stepper-chip.ahead .chip-num { border-color: var(--kb-text); }
.stepper-chip.locked .chip-num {
  border-color: var(--kb-line);
  color: var(--kb-line-strong);
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
