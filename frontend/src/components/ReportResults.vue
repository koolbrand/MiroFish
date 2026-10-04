<template>
  <section class="report-results" :aria-label="$t('reportResults.title')" data-testid="report-results">
    <template v-if="data">
      <div class="results-hero">
        <p class="results-eyebrow"><span class="eyebrow-mark" aria-hidden="true"></span>{{ $t('reportResults.title') }}</p>
        <h2 :class="{ 'is-long': data.headline.text.length > 220 }"><MiniMarkdown :text="data.headline.text" inline /></h2>
        <p class="results-scope">{{ $t('reportResults.scope') }}</p>
        <ReportResultReferences :refs="data.headline.refs" />
      </div>
      <div class="finding-grid">
        <article v-for="(row, index) in data.findings" :key="index" class="finding-card">
          <p class="finding-label">{{ $t('reportResults.finding') }}</p>
          <p class="finding-text"><MiniMarkdown :text="row.text" inline /></p>
          <ReportResultReferences :refs="row.refs" />
        </article>
      </div>
      <section v-if="data.contrasts.length" class="result-map" :aria-label="$t('reportResults.positions')">
        <h3 class="results-section-title">{{ $t('reportResults.positions') }}</h3>
        <p class="map-caption">{{ $t('reportResults.qualitative') }}</p>
        <article v-for="(row, index) in data.contrasts" :key="index" class="position-card">
          <div class="position-poles"><p><MiniMarkdown :text="row.left" inline /></p><svg viewBox="0 0 32 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 12h26M9 6l-6 6 6 6m14-12 6 6-6 6" /></svg><p><MiniMarkdown :text="row.right" inline /></p></div>
          <ReportResultReferences :refs="row.refs" />
        </article>
      </section>
      <aside class="results-limitations" :aria-label="$t('reportResults.limitations')">
        <h3>{{ $t('reportResults.limitations') }}</h3>
        <div v-for="(row, index) in data.limitations" :key="index"><p><MiniMarkdown :text="row.text" inline /></p><ReportResultReferences :refs="row.refs" /></div>
      </aside>
    </template>
    <template v-else>
      <p v-if="summary" class="results-fallback">{{ summary }}</p>
      <div v-if="reportReady" class="results-placeholder">
        <h2>{{ $t('reportResults.title') }}</h2>
        <template v-if="snapshot?.status === 'generating' && !problem">
          <p class="results-progress" role="status"><span class="progress-mark" aria-hidden="true"></span>{{ $t('reportResults.generating') }}</p>
          <p>{{ $t('reportResults.generatingHelp') }}</p>
        </template>
        <template v-else-if="problem">
          <p role="status">{{ $t(problem === 'poll_timeout' ? 'reportResults.pollTimeout' : 'reportResults.connection') }}</p>
          <button type="button" class="results-button secondary" :disabled="busy" @click="controller.resume()">{{ $t('reportResults.checkAgain') }}</button>
        </template>
        <template v-else>
          <p v-if="snapshot?.status === 'stale'">{{ $t('reportResults.stale') }}</p>
          <p v-else-if="snapshot?.status === 'failed'" role="status">{{ $t(errorKey) }}</p>
          <p>{{ $t('reportResults.createHelp') }}</p>
          <button v-if="canCreate" type="button" class="results-button" :disabled="busy" @click="controller.start()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M5 4h14v16H5zM8 8h8m-8 4h8m-8 4h5" /></svg>{{ $t(snapshot?.status === 'not_generated' ? 'reportResults.create' : 'reportResults.retry') }}</button>
        </template>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { generateReportResults, getReportResults } from '../api/report'
import { createResultsController } from '../lib/reportResults'
import ReportResultReferences from './ReportResultReferences.vue'
import MiniMarkdown from '../lib/miniMarkdown'
const props = defineProps({ reportId: String, results: Object, reportReady: Boolean, summary: String })
const emit = defineEmits(['results-updated'])
const snapshot = ref(null)
const busy = ref(false)
const problem = ref(null)
const controller = createResultsController({
  read: async (id, signal) => { const res = await getReportResults(id, { signal }); if (!res?.success) throw new Error('Read failed'); return res.data?.results },
  generate: async (id, signal) => { const res = await generateReportResults(id, { signal }); if (!res?.success) throw new Error('Start failed'); return res.data },
  onSnapshot: (value, local) => { snapshot.value = value; if (local) emit('results-updated', value) },
  onProblem: value => { problem.value = value },
  onBusy: value => { busy.value = value }
})
watch(() => props.reportId, id => controller.reset(id), { immediate: true })
watch(() => [props.results, props.reportReady, props.reportId], () => controller.observe(props.results, props.reportReady), { immediate: true })
onUnmounted(() => controller.dispose())
const data = computed(() => snapshot.value?.status === 'ready' ? snapshot.value.data : null)
const canCreate = computed(() => !!props.reportId && props.reportReady && ['not_generated', 'failed', 'stale'].includes(snapshot.value?.status))
const errorKey = computed(() => snapshot.value?.error_code ? `reportResults.errors.${snapshot.value.error_code}` : 'reportResults.failed')
</script>

<style scoped>
.report-results { container-type: inline-size; margin: 24px 0; min-width: 0; font-family: var(--kb-font-sans); color: var(--kb-text); overflow-wrap: anywhere; }
.results-hero { padding: 24px; background: var(--kb-accent-subtle); border: 1px solid var(--kb-accent-line); border-radius: 16px; }
.results-eyebrow { display: flex; align-items: center; gap: 8px; margin: 0 0 14px; font: 600 12px/1.4 var(--kb-font-mono); text-transform: uppercase; letter-spacing: .035em; color: var(--kb-accent-text); }
.eyebrow-mark { flex-shrink: 0; width: 12px; height: 12px; border-radius: 3px; background: var(--kb-text); transform: rotate(-12deg); }
.results-hero h2 { font-size: 22px; line-height: 1.4; font-weight: 600; letter-spacing: -.015em; margin: 0; }
.results-hero h2.is-long { font-size: 20px; }
.results-scope { font-size: 12px; line-height: 1.6; color: var(--kb-text-2); margin: 14px 0 0; }
.finding-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 20px; }
.finding-card, .position-card { padding: 20px; border: 1px solid var(--kb-line); border-radius: 12px; background: var(--kb-surface); min-width: 0; }
.finding-card { border-top: 3px solid var(--kb-accent-solid); }
.finding-label { margin: 0 0 12px; font: 600 12px/1.4 var(--kb-font-mono); color: var(--kb-accent-text); text-transform: uppercase; letter-spacing: .035em; }
.finding-text { margin: 0; font-size: 16px; line-height: 1.55; font-weight: 400; }
.result-map { margin-top: 24px; }
.results-section-title { margin: 0 0 8px; font-size: 20px; line-height: 1.3; }
.map-caption { color: var(--kb-muted); font-size: 12px; line-height: 1.5; margin: 0 0 14px; }
.position-card { margin-top: 12px; }
.position-poles { display: grid; grid-template-columns: minmax(0, 1fr) 32px minmax(0, 1fr); align-items: center; gap: 8px; }
.position-poles p { margin: 0; padding: 14px; align-self: stretch; display: flex; align-items: center; font-size: 16px; line-height: 1.55; font-weight: 400; border: 1px solid var(--kb-control-line); border-radius: 10px; background: var(--kb-surface-2); }
.position-poles svg { width: 32px; height: 24px; color: var(--kb-accent-text); }
.results-limitations { margin-top: 24px; padding: 20px; border-radius: 12px; background: var(--kb-soft); border-left: 3px solid var(--kb-text); color: var(--kb-text-on-soft); }
.results-limitations h3 { font-size: 18px; margin: 0 0 12px; }
.results-limitations p { font-size: 14px; line-height: 1.6; margin: 12px 0 0; }
.results-limitations :deep(summary) { color: var(--kb-text-on-soft); }
.results-limitations :deep(.reference-context), .results-limitations :deep(figcaption) { color: var(--kb-text-on-soft); }
.results-fallback { padding-left: 16px; border-left: 3px solid var(--kb-accent-solid); font-size: 17px; line-height: 1.65; color: var(--kb-text-2); margin: 0 0 20px; }
.results-placeholder { padding: 20px; border: 1px solid var(--kb-line); border-radius: 12px; background: var(--kb-surface); }
.results-placeholder h2 { font-size: 19px; line-height: 1.3; margin: 0 0 12px; }
.results-placeholder p { margin: 10px 0; font-size: 13px; line-height: 1.6; color: var(--kb-text-2); }
.results-button { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 10px 14px; border: 1px solid var(--kb-text); border-radius: 8px; color: var(--kb-accent-on); background: var(--kb-accent-solid); font: 600 13px/1.4 var(--kb-font-sans); cursor: pointer; margin-top: 8px; text-align: left; }
.results-button svg { width: 18px; height: 18px; flex-shrink: 0; }
.results-button.secondary { background: var(--kb-surface); border-color: var(--kb-control-line); }
.results-button:hover:not(:disabled) { background: var(--kb-accent-subtle); }
.results-button:disabled { opacity: .6; cursor: wait; }
.results-button:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 3px; }
.results-progress { display: flex; align-items: center; gap: 10px; }
.progress-mark { width: 12px; height: 12px; flex-shrink: 0; border: 2px solid var(--kb-control-line); border-top-color: var(--kb-text); border-radius: 50%; animation: result-spin .7s linear infinite; }
@keyframes result-spin { to { transform: rotate(360deg); } }
@container (max-width: 480px) { .finding-grid { grid-template-columns: minmax(0, 1fr); } .results-hero, .finding-card, .position-card, .results-limitations { padding: 16px; } }
@container (max-width: 340px) { .position-poles { grid-template-columns: minmax(0, 1fr); } .position-poles svg { justify-self: center; transform: rotate(90deg); } .position-poles p { padding: 12px; } }
@media (prefers-reduced-motion: reduce) { .progress-mark { animation: none; } }
</style>
