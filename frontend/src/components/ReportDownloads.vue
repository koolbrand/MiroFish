<template>
  <!-- Descargas del informe: PDF con la identidad de Simuloo (se maqueta en el servidor, 1–3 s) y Markdown -->
  <div class="report-downloads">
    <button
      type="button"
      class="dl dl-pdf"
      :disabled="busy || disabled"
      :aria-busy="busy"
      :title="$t('step5.downloadPdfTitle')"
      @click="download('pdf')"
    >
      <span v-if="busy" class="dl-spin" aria-hidden="true"></span>
      <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      {{ busy ? $t('step5.generatingPdf') : 'PDF' }}
    </button>
    <button
      type="button"
      class="dl"
      :disabled="disabled"
      :title="$t('step5.downloadReport')"
      :aria-label="$t('step5.downloadReport')"
      @click="download('md')"
    >.md</button>
    <p v-if="error" class="dl-error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { downloadReport, downloadReportPdf } from '../api/report'

const props = defineProps({
  reportId: { type: String, default: '' },
  disabled: { type: Boolean, default: false },   // mientras el informe aún se escribe
})

const { t } = useI18n()
const busy = ref(false)
const error = ref('')

// Un error de descarga llega como Blob (la respuesta se pidió como archivo): se lee el mensaje del servidor
const messageOf = async (err) => {
  try {
    const blob = err?.response?.data
    if (blob && typeof blob.text === 'function') {
      const body = JSON.parse(await blob.text())
      if (body?.error) return body.error
    }
  } catch (e) { /* sin cuerpo legible: mensaje genérico */ }
  return t('step5.pdfFailed')
}

const download = async (kind) => {
  if (!props.reportId || busy.value) return
  error.value = ''
  if (kind === 'pdf') busy.value = true
  try {
    await (kind === 'pdf' ? downloadReportPdf(props.reportId) : downloadReport(props.reportId))
  } catch (err) {
    error.value = await messageOf(err)
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.report-downloads { margin-left: auto; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 6px; }
.dl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  padding: 3px 11px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-control-line);
  border-radius: 3px;
  color: var(--kb-text-on-soft);
  font: 600 12px var(--kb-font-mono);
  letter-spacing: 0.03em;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.dl:hover:not(:disabled) { border-color: var(--kb-text); color: var(--kb-text); background: var(--kb-surface-2); }
.dl:focus-visible { outline: 2px solid var(--kb-text); outline-offset: 2px; }
.dl:disabled { opacity: 0.55; cursor: default; }
/* el PDF es lo que casi todo el mundo busca: lima con filete de tinta, como el resto de acciones principales */
.dl-pdf { background: var(--kb-accent-solid); border-color: var(--kb-text); color: var(--kb-accent-on); }
.dl-pdf:hover:not(:disabled) { background: var(--kb-accent-hover); border-color: var(--kb-text); color: var(--kb-accent-on); }
.dl-spin { width: 12px; height: 12px; border: 2px solid var(--kb-text); border-top-color: transparent; border-radius: 50%; animation: dl-turn 0.8s linear infinite; }
.dl-error { flex-basis: 100%; margin: 4px 0 0; text-align: end; font: 400 12px/1.4 var(--kb-font-sans); color: var(--kb-danger-text); }
@keyframes dl-turn { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .dl-spin { animation-duration: 2.4s; } }
</style>
