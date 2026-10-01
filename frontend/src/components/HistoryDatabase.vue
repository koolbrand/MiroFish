<template>
  <div class="history-database" :class="{ 'no-projects': projects.length === 0 && !loading }">
    <header class="history-head">
      <div>
        <span class="history-kicker">{{ $t('history.kicker') }}</span>
        <h2 class="history-title">{{ $t('history.heading') }}</h2>
      </div>
      <router-link v-if="projects.length" to="/projects" class="history-all">
        {{ $t('history.seeAll') }} <span aria-hidden="true">→</span>
      </router-link>
    </header>

    <!-- Cargando: esqueletos con brillo -->
    <div v-if="loading" class="sim-grid" aria-busy="true" :aria-label="$t('history.loadingText')">
      <div v-for="n in 3" :key="n" class="sim-card skeleton">
        <span class="sk sk-pill"></span>
        <span class="sk sk-title"></span>
        <span class="sk sk-line"></span>
        <span class="sk sk-line short"></span>
        <span class="sk sk-bar"></span>
      </div>
    </div>

    <!-- Tarjetas: la barra de etapas se rellena al entrar en pantalla -->
    <div v-else-if="projects.length" v-reveal class="sim-grid">
      <article
        v-for="(project, index) in projects"
        :key="project.simulation_id"
        class="sim-card"
        :style="{ '--i': Math.min(index, 8) }"
      >
        <div class="sim-card-top">
          <!-- cada proyecto tiene su propia Bianka (la misma siempre) y su color dice cómo acabó -->
          <BiankaAvatar class="sim-face" :seed="project.simulation_id" :bucket="faceBucket(project)" :pixel="2" />
          <span class="sim-status" :class="getProgressClass(project)">
            <i class="dot" aria-hidden="true"></i>{{ formatRounds(project) }}
          </span>
          <button
            type="button"
            class="sim-delete"
            :aria-label="$t('history.deleteNamed', { name: cardTitle(project) })"
            :title="$t('history.deleteSim')"
            :disabled="deletingIds.has(project.simulation_id)"
            @click="askDeleteSimulation(project)"
          >×</button>
        </div>

        <p v-if="project.pipeline_mode === 'auto'" class="sim-auto" :class="`is-${project.pipeline_status || 'running'}`">
          {{ $t('history.autoBadge', { status: $t(`history.autoStatus.${project.pipeline_status || 'running'}`) }) }}
        </p>

        <h3 class="sim-title">
          <!-- el botón cubre toda la tarjeta (patrón «enlace estirado») -->
          <button type="button" class="sim-open" @click="navigateToProject(project)">
            {{ cardTitle(project) }}
          </button>
        </h3>
        <p v-if="project.simulation_requirement" class="sim-desc">{{ plainText(project.simulation_requirement) }}</p>
        <p v-else class="sim-desc is-empty">{{ $t('history.noDescription') }}</p>

        <ol class="pipeline">
          <li v-for="stage in stagesOf(project)" :key="stage.key" :class="{ done: stage.value >= 1 }">
            <span class="track"><span class="fill" :style="{ '--v': stage.value }"></span></span>
            <span class="stage-label">
              {{ stage.label }}
              <span class="sr-only">— {{ stage.value >= 1 ? $t('history.ready') : $t('history.pending') }}</span>
            </span>
          </li>
        </ol>

        <div class="sim-card-foot">
          <span class="sim-meta">
            <time :datetime="project.created_at">{{ formatDate(project.created_at) }} · {{ formatTime(project.created_at) }}</time>
            <template v-if="project.files?.length"> · {{ filesLabel(project) }}</template>
          </span>
          <span class="sim-go" aria-hidden="true">{{ $t('history.open') }} →</span>
        </div>
      </article>
    </div>

    <!-- Sin simulaciones todavía -->
    <div v-else class="history-empty">
      <BiankaAvatar class="history-empty-face" :look="emptyLook" bucket="undecided" :pixel="4" />
      <p class="history-empty-title">{{ $t('history.emptyTitle') }}</p>
      <p class="history-empty-body">{{ $t('history.emptyBody') }}</p>
      <a href="#ensayo" class="history-empty-cta">{{ $t('history.emptyCta') }} <span aria-hidden="true">↑</span></a>
    </div>

    <!-- Confirmar borrado -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="deleteTarget" class="kb-modal-overlay" @click.self="cancelDelete">
          <div class="kb-modal small" role="dialog" aria-modal="true" :aria-label="$t('history.deleteConfirmTitle')">
            <div class="kb-modal-head">
              <h3>{{ $t('history.deleteConfirmTitle') }}</h3>
              <button type="button" class="kb-modal-close" :aria-label="$t('history.cancel')" @click="cancelDelete">×</button>
            </div>
            <p class="kb-modal-text">{{ $t('history.deleteConfirmMsg', { id: cardTitle(deleteTarget) }) }}</p>
            <p class="kb-modal-warning">{{ $t('history.deleteWarning') }}</p>
            <div class="kb-modal-actions">
              <button type="button" class="kb-btn ghost" :disabled="confirming" @click="cancelDelete">
                {{ $t('history.cancel') }}
              </button>
              <button type="button" class="kb-btn danger" :disabled="confirming" @click="confirmDelete">
                {{ confirming ? $t('history.deleting') : $t('history.deleteSim') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Detalle: volver a cualquier paso ya hecho -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="selectedProject" class="kb-modal-overlay" @click.self="closeModal">
          <div class="kb-modal" role="dialog" aria-modal="true" :aria-label="cardTitle(selectedProject)">
            <div class="kb-modal-head">
              <div class="kb-modal-meta">
                <span class="sim-status" :class="getProgressClass(selectedProject)">
                  <i class="dot" aria-hidden="true"></i>{{ formatRounds(selectedProject) }}
                </span>
                <span class="kb-modal-date">{{ formatDate(selectedProject.created_at) }} · {{ formatTime(selectedProject.created_at) }}</span>
                <span class="kb-modal-id tech-only">{{ formatSimulationId(selectedProject.simulation_id) }}</span>
              </div>
              <button type="button" class="kb-modal-close" :aria-label="$t('common.close')" @click="closeModal">×</button>
            </div>

            <h3 class="kb-modal-title">{{ cardTitle(selectedProject) }}</h3>

            <div class="kb-modal-section">
              <div class="kb-modal-label">{{ $t('history.simRequirement') }}</div>
              <p class="kb-modal-requirement">{{ plainText(selectedProject.simulation_requirement) || $t('common.none') }}</p>
            </div>

            <div class="kb-modal-section">
              <div class="kb-modal-label">{{ $t('history.relatedFiles') }}</div>
              <ul v-if="selectedProject.files?.length" class="kb-modal-files">
                <li v-for="(file, index) in selectedProject.files" :key="index">
                  <span class="file-ext">{{ getFileTypeLabel(file.filename) }}</span>
                  <span class="file-name">{{ file.filename }}</span>
                </li>
              </ul>
              <p v-else class="kb-modal-muted">{{ $t('history.noRelatedFiles') }}</p>
            </div>

            <div class="kb-modal-label replay">{{ $t('history.replayTitle') }}</div>
            <div class="replay-grid">
              <button type="button" class="replay-btn" :disabled="!selectedProject.project_id" @click="goToProject">
                <span class="replay-step">{{ $t('history.stepLabel', { n: 1 }) }}</span>
                <span class="replay-name">{{ $t('history.step1Button') }}</span>
              </button>
              <button type="button" class="replay-btn" @click="goToSimulation">
                <span class="replay-step">{{ $t('history.stepLabel', { n: 2 }) }}</span>
                <span class="replay-name">{{ $t('history.step2Button') }}</span>
              </button>
              <button type="button" class="replay-btn" :disabled="!selectedProject.report_id" @click="goToReport">
                <span class="replay-step">{{ $t('history.stepLabel', { n: 4 }) }}</span>
                <span class="replay-name">{{ $t('history.step4Button') }}</span>
              </button>
            </div>
            <p class="kb-modal-muted hint">{{ $t('history.replayHint') }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getSimulationHistory, deleteSimulation } from '../api/simulation'
import { vReveal } from '../composables/useReveal'
import BiankaAvatar from './BiankaAvatar.vue'

// la Bianka que espera en el historial vacío: dudosa (blanca), con gafas, mirando al frente
const emptyLook = { ears: 'up', face: 'glasses', body: 'bowtie' }

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const projects = ref([])
const loading = ref(true)
const selectedProject = ref(null)
const deleteTarget = ref(null)
const confirming = ref(false)
const deletingIds = ref(new Set())

// Estado real del proceso (runner_status), no solo las rondas: una simulación
// parada a medias no debe parecer «en curso».
const statusKind = (simulation) => {
  const rs = simulation.runner_status
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  if (rs === 'running' || rs === 'starting' || rs === 'stopping') return 'running'
  if (rs === 'failed') return 'failed'
  if (rs === 'completed' || (total && current >= total)) return 'completed'
  if (!current) return 'not-started'
  return 'stopped'
}

const getProgressClass = (simulation) => ({ running: 'in-progress' }[statusKind(simulation)] || statusKind(simulation))

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toISOString().slice(0, 10)
  } catch {
    return dateStr?.slice(0, 10) || ''
  }
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return ''
  }
}

const getSimulationTitle = (requirement) => {
  requirement = plainText(requirement)
  if (!requirement) return t('history.untitledSimulation')
  return requirement.length > 60 ? requirement.slice(0, 60) + '…' : requirement
}

// Lima si terminó bien, tinta si falló, blanca en cualquier otro caso
const faceBucket = (project) => ({ completed: 'favor', failed: 'against' }[statusKind(project)] || 'undecided')

const cardTitle = (project) => project?.project_name || getSimulationTitle(project?.simulation_requirement)

const formatSimulationId = (simulationId) => {
  if (!simulationId) return 'SIM_UNKNOWN'
  return `SIM_${simulationId.replace('sim_', '').slice(0, 6).toUpperCase()}`
}

const formatRounds = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  const kind = statusKind(simulation)
  if (kind === 'not-started' || total === 0) return t('history.notStarted')
  if (kind === 'running') return t('history.statusRunning', { current, total })
  if (kind === 'stopped') return t('history.statusStopped', { current, total })
  if (kind === 'failed') return t('history.statusFailed', { current, total })
  return t('history.roundsProgress', { current, total })
}

// La pregunta a veces llega en Markdown («**Simulación:** …»): se enseña limpia.
const plainText = (text) => (text || '').replace(/\*\*|__|`/g, '').replace(/^#{1,6}\s+/gm, '').trim()

const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  return filename.split('.').pop()?.toUpperCase() || 'FILE'
}

const truncateFilename = (filename, maxLength) => {
  if (!filename) return t('history.unknownFile')
  if (filename.length <= maxLength) return filename
  const ext = filename.includes('.') ? '.' + filename.split('.').pop() : ''
  return filename.slice(0, maxLength - ext.length - 1) + '…' + ext
}

const filesLabel = (project) => {
  const files = project.files || []
  const first = truncateFilename(files[0]?.filename, 22)
  return files.length > 1 ? `${first} ${t('history.moreFiles', { count: files.length - 1 })}` : first
}

// Tres etapas visibles del proyecto: 0 = pendiente, 1 = hecha (la simulación admite parcial).
const stagesOf = (project) => {
  const total = project.total_rounds || 0
  const current = project.current_round || 0
  return [
    { key: 'graph', label: t('history.stageGraph'), value: project.project_id ? 1 : 0 },
    { key: 'sim', label: t('history.stageSim'), value: total ? Math.min(1, current / total) : 0 },
    { key: 'report', label: t('history.stageReport'), value: project.report_id ? 1 : 0 },
  ]
}

const navigateToProject = (simulation) => {
  selectedProject.value = simulation
}

const closeModal = () => {
  selectedProject.value = null
}

const goToProject = () => {
  if (selectedProject.value?.project_id) {
    router.push({ name: 'Process', params: { projectId: selectedProject.value.project_id } })
    closeModal()
  }
}

const goToSimulation = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({ name: 'Simulation', params: { simulationId: selectedProject.value.simulation_id } })
    closeModal()
  }
}

const goToReport = () => {
  if (selectedProject.value?.report_id) {
    router.push({ name: 'Report', params: { reportId: selectedProject.value.report_id } })
    closeModal()
  }
}

const askDeleteSimulation = (sim) => {
  deleteTarget.value = sim
}

const cancelDelete = () => {
  if (confirming.value) return
  deleteTarget.value = null
}

const confirmDelete = async () => {
  if (!deleteTarget.value || confirming.value) return
  const sid = deleteTarget.value.simulation_id
  confirming.value = true
  const next = new Set(deletingIds.value)
  next.add(sid)
  deletingIds.value = next
  try {
    const res = await deleteSimulation(sid)
    if (res.success) {
      // La tarjeta desaparece sin esperar a recargar la lista
      projects.value = projects.value.filter(p => p.simulation_id !== sid)
    } else {
      console.warn('deleteSimulation failed:', res.error)
    }
  } catch (err) {
    console.error('deleteSimulation error:', err)
  } finally {
    const after = new Set(deletingIds.value)
    after.delete(sid)
    deletingIds.value = after
    confirming.value = false
    deleteTarget.value = null
  }
}

// Diálogos (ficha y confirmación de borrado): el foco entra, Tab se queda dentro, Escape cierra y el foco vuelve a la tarjeta
const dialogEl = () => document.querySelector('.kb-modal-overlay .kb-modal')
const onKeydown = (e) => {
  if (e.key === 'Escape') {
    if (deleteTarget.value) cancelDelete()
    else if (selectedProject.value) closeModal()
    return
  }
  if (e.key !== 'Tab') return
  const dlg = dialogEl()
  if (!dlg) return
  const items = [...dlg.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')].filter(el => el.offsetParent !== null)
  if (!items.length) return
  const first = items[0], last = items[items.length - 1]
  if (!dlg.contains(document.activeElement)) { e.preventDefault(); first.focus() }
  else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}
let lastFocus = null

const loadHistory = async () => {
  try {
    loading.value = true
    const response = await getSimulationHistory(20)
    if (response.success) {
      projects.value = response.data || []
    }
  } catch (error) {
    console.error('Error al cargar proyectos históricos:', error)
    projects.value = []
  } finally {
    loading.value = false
  }
}

// Al volver a la portada se recarga la lista
watch(() => route.path, (newPath) => {
  if (newPath === '/') loadHistory()
})

watch([selectedProject, deleteTarget], ([sel, del], [wasSel, wasDel]) => {
  const open = !!(sel || del)
  if (open) {
    if (!(wasSel || wasDel)) { lastFocus = document.activeElement; window.addEventListener('keydown', onKeydown) }
    // en el borrado el foco va a «Cancelar» (lo más seguro); en la ficha, al cierre
    nextTick(() => (document.querySelector('.kb-modal-actions .kb-btn.ghost') || document.querySelector('.kb-modal-close'))?.focus())
  } else {
    window.removeEventListener('keydown', onKeydown)
    lastFocus?.focus?.(); lastFocus = null
  }
})

onMounted(async () => {
  await nextTick()
  await loadHistory()
})

onActivated(() => {
  loadHistory()
})
</script>

<style scoped>
.sim-auto {
  margin: 10px 0 -4px;
  font: 600 11px var(--kb-font-mono);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--kb-text-2);
}
.sim-auto.is-running { color: var(--kb-accent-text); }
.sim-auto.is-failed, .sim-auto.is-interrupted { color: var(--kb-text); }
.history-database { font-family: var(--kb-font-sans); color: var(--kb-text); }

.history-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px 32px;
  margin-bottom: 40px;
}
.history-kicker {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--kb-accent-text);
}
.history-title {
  margin: 12px 0 0;
  font-size: clamp(2rem, 3.8vw, 3.2rem);
  font-weight: 800;
  line-height: 1.02;
  letter-spacing: -0.04em;
  text-wrap: balance;
}
.history-all {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  font-weight: 600;
  color: var(--kb-text);
  text-decoration: none;
  white-space: nowrap;
}
.history-all span { transition: transform 0.2s ease; }
.history-all:hover span { transform: translateX(3px); }

/* ── Rejilla de tarjetas ─────────────────────────────────────────────────── */
.sim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 20px;
}
.sim-grid.reveal { opacity: 1; transform: none; }

.sim-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px 22px 18px;
  background: var(--kb-surface);
  /* contorno de tinta y sombra dura, como el resto de las tarjetas de la portada */
  border: 2px solid var(--ink-950);
  border-radius: 14px;
  box-shadow: 4px 4px 0 var(--ink-950);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}
.sim-grid.reveal .sim-card {
  opacity: 0;
  transform: translateY(16px);
  transition: opacity 0.6s ease, transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1), border-color 0.2s ease, box-shadow 0.2s ease;
  transition-delay: calc(var(--i) * 0.08s), calc(var(--i) * 0.08s), 0s, 0s;
}
.sim-grid.is-in .sim-card { opacity: 1; transform: none; }
.sim-grid.is-in .sim-card:hover,
.sim-card:focus-within {
  box-shadow: 7px 7px 0 var(--ink-950);
}
.sim-grid.is-in .sim-card:hover { transform: translate(-2px, -2px); transition-delay: 0s; }

.sim-card-top { display: flex; align-items: center; gap: 12px; }
.sim-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--kb-soft);
  color: var(--kb-text-2);
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.sim-status .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--gray-500); }
.sim-status.completed { background: var(--lime-50); color: var(--lime-800); }
.sim-status.completed .dot { background: var(--lime-700); }
.sim-status.in-progress { background: var(--ink-950); color: var(--lime-500); }
.sim-status.in-progress .dot { background: var(--lime-500); animation: pulse 1.6s ease-in-out infinite; }
.sim-status.stopped { background: var(--kb-soft); color: var(--kb-text-2); }
.sim-status.stopped .dot { background: var(--gray-600); }
.sim-status.failed { background: #FDECEC; color: #991B1B; }
.sim-status.failed .dot { background: var(--kb-danger); }

.sim-delete {
  margin-inline-start: auto;
  position: relative;
  z-index: 2;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--kb-muted);
  font-size: 1.15rem;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.sim-delete:hover:not(:disabled) { background: #FDECEC; color: var(--kb-danger); }
.sim-delete:disabled { opacity: 0.4; cursor: not-allowed; }

.sim-title { margin: 4px 0 0; font-size: 1.15rem; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; }
.sim-open {
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  text-align: start;
  cursor: pointer;
  text-wrap: balance;
}
.sim-open::after { content: ''; position: absolute; inset: 0; border-radius: inherit; }
.sim-open:focus-visible { outline: none; }
.sim-card:has(.sim-open:focus-visible) { outline: 2px solid var(--kb-accent-text); outline-offset: 2px; }

.sim-desc.is-empty { color: var(--kb-muted); font-style: italic; }
.sim-desc {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  font-size: 0.92rem;
  line-height: 1.5;
  color: var(--kb-text-2);
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.pipeline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
.pipeline li { display: grid; gap: 6px; }
.track { display: block; height: 6px; overflow: hidden; border-radius: 3px; background: var(--kb-soft); }
.fill {
  display: block;
  height: 100%;
  background: var(--lime-500);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 0.9s cubic-bezier(0.65, 0, 0.35, 1);
  transition-delay: calc(var(--i) * 0.08s + 0.35s);
}
.pipeline li:nth-child(2) .fill { transition-delay: calc(var(--i) * 0.08s + 0.6s); }
.pipeline li:nth-child(3) .fill { transition-delay: calc(var(--i) * 0.08s + 0.85s); }
.sim-grid.is-in .fill { transform: scaleX(var(--v)); }
.stage-label { font-family: var(--kb-font-mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--kb-subtle); }
.pipeline li.done .stage-label { color: var(--kb-text-2); }

.sim-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--kb-line);
  font-size: 0.8rem;
}
.sim-meta {
  overflow: hidden;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.sim-go { flex: none; font-weight: 600; color: var(--kb-text); transition: transform 0.2s ease; }
.sim-card:hover .sim-go { transform: translateX(3px); }

/* Esqueletos */
.skeleton { gap: 14px; }
.sk {
  display: block;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--kb-soft) 0%, #F7F7F7 50%, var(--kb-soft) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.3s linear infinite;
}
.sk-pill { width: 96px; height: 22px; border-radius: 999px; }
.sk-title { width: 70%; height: 20px; }
.sk-line { width: 100%; height: 12px; }
.sk-line.short { width: 55%; }
.sk-bar { width: 100%; height: 6px; margin-top: 10px; }

/* Vacío */
.history-empty {
  display: grid;
  justify-items: start;
  gap: 8px;
  padding: clamp(28px, 4vw, 40px);
  border: 1.5px dashed var(--kb-control-line);
  border-radius: 16px;
  background: var(--kb-surface-2);
}
.history-empty-face { margin-bottom: 4px; }
/* con sitio, la Bianka va al lado del texto (no arriba, dejando media tarjeta vacía) */
@media (min-width: 720px) {
  .history-empty { grid-template-columns: auto minmax(0, 1fr); column-gap: 32px; align-items: center; }
  .history-empty-face { grid-row: 1 / span 3; margin: 0; }
  .history-empty > :not(.history-empty-face) { grid-column: 2; }
  .history-empty-cta { justify-self: start; }
}
.history-empty-title { margin: 0; font-size: 1.15rem; font-weight: 700; }
.history-empty-body { max-width: 60ch; margin: 0; color: var(--kb-text-2); line-height: 1.5; text-wrap: pretty; }
.history-empty-cta {
  margin-top: 10px;
  padding: 10px 16px;
  border-radius: 10px;
  background: var(--lime-500);   /* el mismo relleno lima de la acción principal en portada, formulario y cierre */
  color: var(--ink-950);
  font-weight: 600;
  text-decoration: none;
}
.history-empty-cta:hover { filter: brightness(0.96); }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@keyframes shimmer { to { background-position: -200% 0; } }
@keyframes pulse { 50% { opacity: 0.35; } }

@media (prefers-reduced-motion: reduce) {
  .sim-grid.reveal .sim-card, .fill { transition: none; }
  .sk, .sim-status .dot { animation: none; }
}
</style>

<!-- Ventanas (teleport a body): sin scoped para que los estilos lleguen -->
<style>
.kb-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(17, 17, 17, 0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.kb-modal {
  box-sizing: border-box;
  width: min(640px, 100%);
  max-height: calc(100vh - 32px);
  overflow: auto;
  padding: clamp(22px, 4vw, 32px);
  border-radius: 20px;
  background: var(--kb-surface);
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
  box-shadow: 0 40px 100px -40px rgba(0, 0, 0, 0.55);
}
.kb-modal.small { width: min(460px, 100%); }
.kb-modal-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.kb-modal-head h3 { margin: 0; font-size: 1.2rem; font-weight: 700; }
.kb-modal-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.kb-modal-meta .sim-status {
  display: inline-flex; align-items: center; gap: 7px; padding: 5px 10px; border-radius: 999px;
  background: var(--kb-soft); color: var(--kb-text-2); font-family: var(--kb-font-mono); font-size: 11px; font-weight: 600;
}
.kb-modal-meta .sim-status .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--gray-500); }
.kb-modal-meta .sim-status.completed { background: var(--lime-50); color: var(--lime-800); }
.kb-modal-meta .sim-status.completed .dot { background: var(--lime-700); }
.kb-modal-meta .sim-status.in-progress { background: var(--ink-950); color: var(--lime-500); }
.kb-modal-meta .sim-status.in-progress .dot { background: var(--lime-500); }
.kb-modal-meta .sim-status.failed { background: #FDECEC; color: #991B1B; }
.kb-modal-meta .sim-status.failed .dot { background: var(--kb-danger); }
.kb-modal-date, .kb-modal-id { font-family: var(--kb-font-mono); font-size: 11px; color: var(--kb-subtle); }
.kb-modal-close {
  flex: none; width: 36px; height: 36px; margin: -6px -6px 0 0; border: none; border-radius: 50%;
  background: transparent; color: var(--kb-text-2); font-size: 1.4rem; line-height: 1; cursor: pointer;
}
.kb-modal-close:hover { background: var(--kb-soft); }
.kb-modal-title { margin: 16px 0 20px; font-size: clamp(1.4rem, 3vw, 1.8rem); font-weight: 800; line-height: 1.15; letter-spacing: -0.03em; text-wrap: balance; }
.kb-modal-section { margin-bottom: 18px; }
.kb-modal-label {
  margin-bottom: 8px; font-family: var(--kb-font-mono); font-size: 11px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--kb-muted);
}
.kb-modal-label.replay { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--kb-line); }
.kb-modal-requirement {
  margin: 0; padding: 14px 16px; border-radius: 12px; background: var(--kb-surface-2);
  font-size: 0.95rem; line-height: 1.55; color: var(--kb-text-2); white-space: pre-wrap;
}
.kb-modal-files { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.kb-modal-files li { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 0.9rem; }
.kb-modal-files .file-ext {
  flex: none; padding: 2px 6px; border-radius: 5px; background: var(--ink-950); color: var(--lime-500);
  font-family: var(--kb-font-mono); font-size: 10px; font-weight: 600;
}
.kb-modal-files .file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-modal-muted { margin: 0; font-size: 0.88rem; line-height: 1.5; color: var(--kb-muted); }
.kb-modal-muted.hint { margin-top: 14px; }
.kb-modal-text { margin: 14px 0 6px; line-height: 1.5; color: var(--kb-text-2); }
.kb-modal-warning { margin: 0 0 22px; font-size: 0.9rem; color: var(--kb-danger); }
.kb-modal-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }

.replay-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.replay-btn {
  display: grid; gap: 4px; padding: 14px; border: 1px solid var(--kb-line-strong); border-radius: 12px;
  background: var(--kb-surface); color: var(--kb-text); font-family: var(--kb-font-sans); text-align: start; cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.replay-btn:hover:not(:disabled) { border-color: var(--ink-950); background: var(--lime-50); }
.replay-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.replay-step { font-family: var(--kb-font-mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--kb-accent-text); }
.replay-name { font-size: 0.92rem; font-weight: 600; line-height: 1.3; }

.kb-btn {
  padding: 11px 18px; border-radius: 10px; font: 600 0.95rem/1 var(--kb-font-sans); cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.kb-btn.ghost { border: 1px solid var(--kb-control-line); background: var(--kb-surface); color: var(--kb-text); }
.kb-btn.ghost:hover:not(:disabled) { border-color: var(--ink-950); }
.kb-btn.danger { border: 1px solid var(--kb-danger); background: var(--kb-danger); color: #fff; }
.kb-btn.danger:hover:not(:disabled) { background: #B91C1C; border-color: #B91C1C; }
.kb-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-active .kb-modal, .modal-leave-active .kb-modal { transition: transform 0.25s cubic-bezier(0.2, 0.8, 0.2, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .kb-modal, .modal-leave-to .kb-modal { transform: translateY(12px) scale(0.98); }

@media (max-width: 560px) {
  .replay-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
