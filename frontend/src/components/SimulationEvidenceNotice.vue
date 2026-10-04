<template>
  <aside class="evidence-notice" data-testid="simulation-evidence" :aria-label="$t('evidence.title')">
    <strong>{{ $t('evidence.title') }}</strong>
    <p>{{ $t('evidence.conversation') }}</p>
    <details v-if="facts" class="evidence-details" :open="!collapsible">
      <summary>{{ $t('evidence.recordTitle') }}</summary>
      <section class="evidence-record" :aria-label="$t('evidence.recordTitle')" data-testid="evidence-record">
      <dl>
        <div><dt>{{ $t('evidence.agents') }}</dt><dd>{{ show(facts.agents) }}</dd></div>
        <div><dt>{{ $t('evidence.anchored') }}</dt><dd>{{ show(facts.anchored) }}</dd></div>
        <div><dt>{{ $t('evidence.active') }}</dt><dd>{{ show(facts.active) }}</dd></div>
        <div><dt>{{ $t('evidence.events') }}</dt><dd>{{ show(facts.events) }}<template v-if="facts.platforms.length"> ({{ facts.platforms.map(p => `${p.name}: ${show(p.count)}`).join(', ') }})</template></dd></div>
        <div><dt>{{ $t('evidence.roundsRecorded') }}</dt><dd>{{ show(facts.executedRounds) }} / {{ show(facts.configuredRounds) }}</dd></div>
        <div><dt>{{ $t('evidence.hoursRecorded') }}</dt><dd>{{ show(facts.executedHours) }} / {{ show(facts.configuredHours) }}</dd></div>
        <div><dt>{{ $t('evidence.originalMaterial') }}</dt><dd>{{ show(facts.sourceCharacters) }} {{ $t('evidence.characters') }}</dd></div>
        <div><dt>{{ $t('evidence.boundedExcerpt') }}</dt><dd>{{ yesNo(facts.truncated) }}</dd></div>
      </dl>
      <p v-if="facts.sourceAvailable === false">{{ $t('evidence.sourceMissing') }}</p>
      <p>{{ $t('evidence.method') }}</p>
      </section>
    </details>
    <p v-if="facts?.populationCitation">{{ $t('evidence.profileSource') }}: {{ facts.populationCitation }}</p>
    <p v-if="legacy">{{ $t('evidence.legacy') }}</p>
    <template v-if="coverage">
      <p>{{ $t(preview ? 'evidence.durationPreview' : 'evidence.durationResult', {
        rounds: coverage.effectiveRounds, hours: format(coverage.effectiveHours),
        plannedRounds: coverage.plannedRounds, plannedHours: format(coverage.plannedHours)
      }) }}</p>
      <p v-if="coverage.limited && (preview || terminal) && coverage.missingPeakHours.length">{{ $t('evidence.missingPeaks', { hours: coverage.missingPeakHours.map(h => `${h}:00`).join(', ') }) }}</p>
    </template>
  </aside>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getSimulationConfig, getRunStatus } from '../api/simulation'
import { simulationCoverage } from '../lib/simulationCoverage'
import { evidenceFacts } from '../lib/evidenceFacts'

const props = defineProps({
  simulationId: String,
  config: Object,
  runStatus: Object,
  rounds: Number,
  preview: Boolean,
  preparationReady: { type: Boolean, default: true },
  legacyReport: Boolean,
  evidence: Object,
  report: Boolean,
  reportReady: Boolean,
  collapsible: Boolean
})
const { locale, t } = useI18n()
const loadedConfig = ref(null)
const loadedRun = ref(null)
let generation = 0
let unmounted = false
watch(() => [props.simulationId, props.evidence?.version, props.reportReady, props.preparationReady], async ([id]) => {
  const request = ++generation
  loadedConfig.value = null
  loadedRun.value = null
  if (!id || props.evidence?.version || (props.report && !props.reportReady) || (props.preview && props.preparationReady === false)) return
  // Estas lecturas no generan contenido ni cambian las simulaciones guardadas.
  const [config, run] = await Promise.allSettled([
    props.config ? Promise.resolve(null) : getSimulationConfig(id),
    props.runStatus || props.preview ? Promise.resolve(null) : getRunStatus(id)
  ])
  if (unmounted || request !== generation) return
  if (config.status === 'fulfilled' && config.value?.success) loadedConfig.value = config.value.data
  if (run.status === 'fulfilled' && run.value?.success) loadedRun.value = run.value.data
}, { immediate: true })
onUnmounted(() => { unmounted = true; generation++ })
const config = computed(() => props.preview && props.preparationReady === false ? null : (props.config || loadedConfig.value))
const run = computed(() => props.runStatus || loadedRun.value)
const legacy = computed(() => props.legacyReport || !props.evidence?.version && !!config.value && !(config.value.generation_version >= 2))
const facts = computed(() => evidenceFacts(props.evidence))
const terminal = computed(() => ['completed', 'stopped', 'failed'].includes(props.evidence?.execution?.status || run.value?.runner_status))
const coverage = computed(() => {
  if (props.preview && props.preparationReady === false) return null
  // Un informe nuevo conserva la ficha de SU ejecución aunque más adelante
  // cambie el estado de la simulación. No sustituirla por una lectura posterior.
  const e = props.evidence?.execution
  if (!props.preview && e && [e.configured_rounds, e.executed_rounds, e.configured_hours, e.executed_hours].every(n => Number.isFinite(n))) {
    return {
      plannedRounds: e.configured_rounds, plannedHours: e.configured_hours,
      effectiveRounds: e.executed_rounds, effectiveHours: e.executed_hours,
      limited: e.duration_limited === true, missingPeakHours: []
    }
  }
  if (props.evidence?.version) return null
  const count = props.preview ? props.rounds : Math.max(run.value?.current_round || 0, run.value?.twitter_current_round || 0, run.value?.reddit_current_round || 0)
  if (!props.preview && (!run.value || run.value.runner_status === 'idle')) return null
  return simulationCoverage(config.value, count)
})
const format = value => new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(value)
const show = value => value === null ? '—' : format(value)
const yesNo = value => value === null ? '—' : t(value ? 'evidence.yes' : 'evidence.no')
</script>

<style scoped>
.evidence-notice {
  flex-shrink: 0;
  padding: 12px 16px;
  border: 1px solid var(--kb-line);
  border-left: 3px solid var(--kb-accent-solid);
  border-radius: 8px;
  background: var(--kb-surface);
  color: var(--kb-text-2);
  font: 400 13px/1.5 var(--kb-font-sans);
  overflow-wrap: anywhere;
}
.evidence-notice strong { color: var(--kb-text); font-weight: 700; }
.evidence-notice p { margin: 6px 0 0; }
.evidence-record { margin-top: 12px; }
.evidence-details > summary { cursor: pointer; min-height: 24px; padding: 5px 0; margin-top: 6px; color: var(--kb-accent-text); }
.evidence-details > summary:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 2px; }
.evidence-record h3 { margin: 0; font-size: 13px; color: var(--kb-text); }
.evidence-record dl { margin: 8px 0 0; }
.evidence-record dl > div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 2px 16px; padding: 3px 0; }
.evidence-record dt { font-weight: 500; }
.evidence-record dd { margin: 0; font-family: var(--kb-font-mono); }
</style>
