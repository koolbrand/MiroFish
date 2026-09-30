<template>
  <div v-if="visible" class="auto-banner" :class="`is-${status}`" role="status" aria-live="polite">
    <span class="auto-tag"><span class="auto-dot" aria-hidden="true"></span>{{ $t('auto.tag') }}</span>
    <p class="auto-text">{{ message }}</p>
    <div class="auto-actions">
      <button v-if="status === 'running'" type="button" class="auto-btn" :disabled="busy" @click="onCancel">
        {{ $t('auto.cancel') }}
      </button>
      <button v-else type="button" class="auto-btn is-primary" :disabled="busy" @click="onResume">
        {{ $t('auto.resume') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { usePipeline } from '../composables/usePipeline'

// Aviso del modo automático en las pantallas del proceso: en qué etapa va el servidor, detenerlo o reanudarlo.
// Si estás mirando la etapa en la que va, te lleva a la siguiente cuando el servidor avanza
// (si has vuelto atrás a mirar otra, no te mueve).
const props = defineProps({
  projectId: { type: String, default: null },
  step: { type: Number, required: true },
})

const router = useRouter()
const { t } = useI18n()
const { state, cancel, resume } = usePipeline(() => props.projectId)
const busy = ref(false)

const status = computed(() => state.value?.status || null)
const visible = computed(() => state.value?.mode === 'auto' && ['running', 'failed', 'interrupted', 'cancelled'].includes(status.value))
const stageName = computed(() => t(`auto.stage.${state.value?.stage || 'ontology'}`))

const message = computed(() => {
  const s = state.value || {}
  const n = Math.min(Math.max(s.stage_index || 1, 1), 5)
  if (s.status === 'running') return t('auto.running', { n, stage: stageName.value })
  if (s.status === 'failed') return t('auto.failed', { stage: stageName.value, error: s.error || t('common.unknownError') })
  if (s.status === 'interrupted') return t('auto.interrupted', { stage: stageName.value })
  return t('auto.cancelled', { stage: stageName.value })
})

watch(() => state.value?.stage_index || 0, (next, prev) => {
  const s = state.value
  if (!s || s.mode !== 'auto' || !prev) return
  if (!(prev <= props.step && next > props.step)) return
  if (next === 2 && s.simulation_id) router.push({ name: 'Simulation', params: { simulationId: s.simulation_id } })
  else if (next === 3 && s.simulation_id) router.push({ name: 'SimulationRun', params: { simulationId: s.simulation_id } })
  else if (next >= 4 && s.report_id && props.step < 4) router.push({ name: 'Report', params: { reportId: s.report_id } })
})

const onCancel = async () => {
  if (!window.confirm(t('auto.cancelConfirm'))) return
  busy.value = true
  try { await cancel() } catch (e) { window.alert(t('auto.actionFailed', { error: e.message })) } finally { busy.value = false }
}

const onResume = async () => {
  busy.value = true
  try { await resume() } catch (e) { window.alert(t('auto.actionFailed', { error: e.message })) } finally { busy.value = false }
}
</script>

<style scoped>
.auto-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 24px;
  background: var(--kb-text);
  color: #fff;
  font-family: var(--kb-font-sans);
  flex-shrink: 0;
}
.auto-banner.is-failed,
.auto-banner.is-interrupted,
.auto-banner.is-cancelled { background: var(--kb-text-2); }
.auto-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font: 600 11px var(--kb-font-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  white-space: nowrap;
  color: var(--kb-accent-solid);
}
.auto-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--kb-accent-solid);
}
.is-running .auto-dot { animation: auto-pulse 1.6s ease-in-out infinite; }
.is-failed .auto-tag, .is-interrupted .auto-tag, .is-cancelled .auto-tag { color: #fff; }
.is-failed .auto-dot, .is-interrupted .auto-dot, .is-cancelled .auto-dot { background: #fff; }
.auto-text {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.4;
  text-wrap: pretty;
}
.auto-actions { flex-shrink: 0; }
.auto-btn {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: transparent;
  color: #fff;
  font: 600 12px var(--kb-font-sans);
  cursor: pointer;
  white-space: nowrap;
}
.auto-btn:hover:not(:disabled) { border-color: #fff; }
.auto-btn.is-primary { background: var(--kb-accent-solid); border-color: var(--kb-accent-solid); color: var(--kb-accent-on); }
.auto-btn:disabled { opacity: 0.6; cursor: default; }
@keyframes auto-pulse { 50% { opacity: 0.35; } }
@media (prefers-reduced-motion: reduce) { .is-running .auto-dot { animation: none; } }
@media (max-width: 640px) {
  .auto-banner { flex-wrap: wrap; gap: 8px 12px; padding: 10px 16px; }
  .auto-text { flex-basis: 100%; order: 3; }
  .auto-actions { margin-inline-start: auto; }
}
</style>
