<template>
  <div class="workbench-panel">
    <div class="scroll-container">
      <!-- Punto de partida: el objetivo de la simulación y el brief con el que se creó el proyecto (también al volver a uno ya hecho) -->
      <section v-if="projectData?.project_id" class="brief-card" aria-labelledby="brief-title" data-testid="brief-card">
        <header class="research-head">
          <span class="research-kicker">{{ $t('step1.briefKicker') }}</span>
          <h3 id="brief-title" class="brief-title">{{ $t('step1.briefObjective') }}</h3>
        </header>
        <p v-if="objective" class="brief-objective" data-testid="brief-objective">{{ objective }}</p>
        <p v-else-if="briefLoading" class="research-note" role="status">{{ $t('common.loading') }}</p>
        <p v-else-if="objectiveEmpty" class="research-note">{{ $t('step1.briefObjectiveEmpty') }}</p>

        <div class="brief-docs">
          <h4 class="brief-sub">{{ $t('step1.briefDocs') }}</h4>
          <ul v-if="brief?.files?.length" class="brief-files" :aria-label="$t('step1.briefFiles')">
            <li v-for="f in brief.files" :key="f.filename">
              <span class="brief-file-name" :title="f.filename">{{ f.filename }}</span>
              <span v-if="fileSize(f.size)" class="brief-file-size">{{ fileSize(f.size) }}</span>
            </li>
          </ul>
          <p v-if="briefError" class="research-note">{{ briefError }}</p>
          <template v-else-if="brief">
            <details v-if="brief.text" class="brief-text-box" data-testid="brief-text">
              <summary>{{ $t('step1.briefShowText', { n: number(brief.text_length) }) }}</summary>
              <pre class="brief-text">{{ brief.text }}</pre>
              <p v-if="brief.truncated" class="research-note">{{ $t('step1.briefTruncated', { shown: number(brief.text.length), total: number(brief.text_length) }) }}</p>
            </details>
            <p v-else class="research-note">{{ $t('step1.briefNoText') }}</p>
          </template>
        </div>
      </section>

      <!-- Contexto de internet (si se pidió): qué se encontró y de dónde, antes de crear a las personas -->
      <section v-if="research" class="research-card" :class="`is-${research.status}`" aria-labelledby="research-title">
        <header class="research-head">
          <span class="research-kicker">{{ $t('step1.researchKicker') }}</span>
          <h3 id="research-title" class="research-title">{{ researchTitle }}</h3>
        </header>
        <p v-if="researchNote" class="research-note">{{ researchNote }}</p>
        <template v-if="research.status === 'done' && research.sources?.length">
          <ul class="research-sources">
            <li v-for="(src, i) in research.sources.slice(0, 6)" :key="src.url">
              <span class="src-n">{{ i + 1 }}</span>
              <a :href="src.url" target="_blank" rel="noopener noreferrer" :title="src.title">{{ src.title || hostOf(src.url) }}</a>
              <span class="src-host">{{ hostOf(src.url) }}<template v-if="src.page_age"> · {{ src.page_age }}</template></span>
            </li>
          </ul>
          <p v-if="research.sources.length > 6" class="research-more">{{ $t('step1.researchMore', { n: research.sources.length - 6 }) }}</p>
          <div class="research-foot">
            <button type="button" class="research-dl" :disabled="downloading" @click="downloadResearchFile">
              ↓ {{ $t('step1.researchDownload') }}
            </button>
            <span class="research-warn">{{ $t('step1.researchWarn') }}</span>
          </div>
        </template>
      </section>

      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step1.ontologyGeneration') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 0" class="badge processing">{{ $t('step1.ontologyGenerating') }}</span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note tech-only">POST /api/graph/ontology/generate</p>
          <p class="description">
            {{ $t('step1.ontologyDesc') }}
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || $t('step1.analyzingDocs') }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? $t('step1.kindEntity') : $t('step1.kindRelation') }}</span>
                  <span class="detail-name" :title="selectedOntologyItem.name">{{ selectedOntologyItem.itemType === 'entity' ? entityLabel(selectedOntologyItem.name) : relationLabel(selectedOntologyItem.name) }}</span>
               </div>
               <button class="close-btn" @click="selectedOntologyItem = null">×</button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>
               
               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">{{ $t('step1.attributes') }}</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name" :title="attr.name">{{ attributeLabel(attr.name) }}</span>
                        <span class="attr-type tech-only">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">{{ $t('step1.examples') }}</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">{{ $t('step1.connections') }}</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node" :title="conn.source">{{ entityLabel(conn.source) }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node" :title="conn.target">{{ entityLabel(conn.target) }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">{{ $t('step1.generatedEntityTypes') }}</span>
            <div class="tags-list">
              <span 
                v-for="entity in projectData.ontology.entity_types" 
                :key="entity.name" 
                class="entity-tag clickable"
                :title="entity.name"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entityLabel(entity.name) }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">{{ $t('step1.generatedRelationTypes') }}</span>
            <div class="tags-list">
              <span 
                v-for="rel in projectData.ontology.edge_types" 
                :key="rel.name" 
                class="entity-tag clickable"
                :title="rel.name"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ relationLabel(rel.name) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step1.graphRagBuild') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">{{ $t('step1.ontologyCompleted') }}</span>
            <span v-else-if="currentPhase === 1" class="badge processing">
              {{ typeof buildProgress?.progress === 'number' ? `${buildProgress.progress}%` : $t('step1.buildInProgress') }}
            </span>
            <span v-else class="badge pending">{{ $t('step1.ontologyPending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note tech-only">POST /api/graph/build</p>
          <p class="description">
            {{ $t('step1.graphRagDesc') }}
          </p>
          
          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">{{ $t('step1.entityNodes') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">{{ $t('step1.relationEdges') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">{{ $t('step1.schemaTypes') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Complete -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step1.buildComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase >= 2" class="badge accent">{{ $t('step1.inProgress') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note tech-only">POST /api/simulation/create</p>
          <p class="description">{{ $t('step1.buildCompleteDesc') }}</p>
          <!-- En automático la simulación la crea el servidor; si ya existe, se abre (nunca se crea otra) -->
          <p v-if="autoRunning && !existingSimulationId" class="auto-note">{{ $t('auto.step1Note') }}</p>
          <button
            v-else-if="existingSimulationId"
            class="action-btn"
            @click="openExistingSimulation"
          >
            {{ $t('step1.viewEnvSetup') }} ➝
          </button>
          <button
            v-else
            class="action-btn"
            :disabled="currentPhase < 2 || creatingSimulation || checkingSimulations"
            @click="handleEnterEnvSetup"
          >
            <span v-if="creatingSimulation" class="spinner-sm"></span>
            {{ creatingSimulation ? $t('step1.creating') : $t('step1.enterEnvSetup') + ' ➝' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">{{ $t('ui.systemDashboard') }}</span>
        <span v-if="!showTech && lastLog" class="log-last">{{ lastLog }}</span>
        <button type="button" class="log-toggle" @click="toggleTech">{{ showTech ? $t('ui.hideLog') : $t('ui.showLog') }}</button>
        <span class="log-id tech-only">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
      </div>
      <div class="log-content" ref="logContent" v-show="showTech">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useTechDetails } from '../composables/useTechDetails'
import { computed, ref, watch, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { createSimulation, listSimulations } from '../api/simulation'
import { downloadResearch, getProjectBrief } from '../api/graph'
import { usePipeline } from '../composables/usePipeline'
import { entityLabel, relationLabel, attributeLabel } from '../lib/typeLabels'

const router = useRouter()
const { t, locale } = useI18n()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})
const { showTech, toggleTech } = useTechDetails()
const lastLog = computed(() => {
  const logs = props.systemLogs || []
  const last = logs[logs.length - 1]
  return last ? String(last.msg || '') : ''
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const creatingSimulation = ref(false)

// La respuesta de creación puede omitir el objetivo; /brief conserva el del proyecto.
const brief = ref(null)
const briefError = ref('')
const briefLoading = ref(false)
const objective = computed(() => String(props.projectData?.simulation_requirement || '').trim() || String(brief.value?.simulation_requirement || '').trim())
const objectiveEmpty = computed(() => !objective.value && !briefLoading.value && !!brief.value && !briefError.value)
let briefRequest = 0
let unmounted = false
onUnmounted(() => { unmounted = true; briefRequest++ })
const number = (n) => new Intl.NumberFormat(locale.value).format(n || 0)
const fileSize = (b) => {
  if (typeof b !== 'number' || !isFinite(b) || b <= 0) return ''
  return b < 1024 ? `${b} B` : b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1)} MB`
}
const loadBrief = async (projectId) => {
  if (unmounted) return
  const request = ++briefRequest
  briefLoading.value = !!projectId
  brief.value = null
  briefError.value = ''
  if (!projectId) return
  try {
    const res = await getProjectBrief(projectId)
    if (unmounted || request !== briefRequest || props.projectData?.project_id !== projectId) return
    if (res?.success && res.data) brief.value = res.data
    else briefError.value = t('step1.briefLoadFailed')
  } catch (e) {
    if (!unmounted && request === briefRequest && props.projectData?.project_id === projectId) briefError.value = t('step1.briefLoadFailed')
  } finally {
    if (!unmounted && request === briefRequest) briefLoading.value = false
  }
}
watch(() => props.projectData?.project_id, loadBrief, { immediate: true })

// Investigación en internet (opcional): lo que encontró el servidor antes de la ontología
const research = computed(() => {
  const r = props.projectData?.web_research
  return r && ['done', 'empty', 'failed'].includes(r.status) ? r : null
})
const researchTitle = computed(() => {
  const r = research.value
  if (!r) return ''
  if (r.status === 'done') return t('step1.researchFound', { n: r.sources?.length || 0 })
  if (r.status === 'empty') return t('step1.researchEmpty')
  return t('step1.researchFailed')
})
const researchNote = computed(() => {
  const r = research.value
  if (!r || r.status === 'done') return ''
  return r.status === 'empty' ? t('step1.researchEmptyNote') : t('step1.researchFailedNote')
})
const hostOf = (u) => { try { return new URL(u).hostname.replace(/^www\./, '') } catch (e) { return u } }
const downloading = ref(false)
const downloadResearchFile = async () => {
  if (downloading.value || !props.projectData?.project_id) return
  downloading.value = true
  try { await downloadResearch(props.projectData.project_id) } catch (e) { window.alert(t('step1.researchDownloadFailed')) } finally { downloading.value = false }
}

// Modo lectura: si el proyecto ya tiene simulación, este paso la abre en vez de crear otra
// (crear una segunda deja la primera huérfana y el proyecto a medias).
const existingSimulationId = ref(null)
const checkingSimulations = ref(false)
const { isRunning: autoRunning, state: pipelineState } = usePipeline(() => props.projectData?.project_id)

const loadExistingSimulation = async (projectId) => {
  existingSimulationId.value = null
  if (!projectId) return
  checkingSimulations.value = true
  try {
    const res = await listSimulations(projectId)
    const list = (res?.data || []).slice().sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
    if (props.projectData?.project_id === projectId) existingSimulationId.value = list[0]?.simulation_id || null
  } catch (e) {
    // sin lista: se deja crear (como antes)
  } finally {
    checkingSimulations.value = false
  }
}
watch(() => props.projectData?.project_id, loadExistingSimulation, { immediate: true })
// el automático crea la simulación: en cuanto aparece, el botón pasa a abrirla
watch(() => pipelineState.value?.simulation_id, sid => { if (sid) existingSimulationId.value = sid })

const openExistingSimulation = () => {
  router.push({ name: 'Simulation', params: { simulationId: existingSimulationId.value } })
}

// 进入环境搭建 - 创建 simulation 并跳转
const handleEnterEnvSetup = async () => {
  if (existingSimulationId.value) return openExistingSimulation()
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('Falta información del proyecto o del grafo')
    return
  }
  
  creatingSimulation.value = true
  
  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true
    })
    
    if (res.success && res.data?.simulation_id) {
      // 跳转到 simulation 页面
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('Error al crear la simulación:', res.error)
      alert(t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    console.error('Excepción al crear la simulación:', err)
    alert(t('step1.createSimulationException', { error: err.message }))
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.brief-card {
  margin-bottom: 16px;
  padding: 16px 18px;
  background: var(--kb-surface);
  border: 1.5px solid var(--ink-950);
  border-radius: 10px;
  box-shadow: 4px 4px 0 var(--ink-950);
}
.brief-title { margin: 0; font-size: 1rem; font-weight: 800; letter-spacing: -0.01em; }
.brief-objective { margin: 8px 0 0; font-size: 15px; line-height: 1.5; color: var(--kb-text); white-space: pre-wrap; overflow-wrap: anywhere; text-wrap: pretty; }
.brief-docs { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--kb-line); }
.brief-sub { margin: 0 0 8px; font: 600 11px var(--kb-font-mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--kb-muted); }
.brief-files { list-style: none; margin: 0 0 10px; padding: 0; display: flex; flex-wrap: wrap; gap: 6px 8px; }
.brief-files li { display: inline-flex; align-items: baseline; gap: 8px; max-width: 100%; padding: 4px 10px; background: var(--kb-soft); border-radius: 999px; font-size: 12.5px; }
.brief-file-name { min-width: 0; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brief-file-size { flex-shrink: 0; font: 11px var(--kb-font-mono); color: var(--kb-muted); }
.brief-text-box summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--kb-text); }
.brief-text { margin: 10px 0 0; max-height: 320px; overflow: auto; padding: 12px 14px; background: var(--kb-soft); border-radius: 8px; font: 12.5px/1.55 var(--kb-font-sans); white-space: pre-wrap; overflow-wrap: anywhere; }
.research-card {
  margin-bottom: 16px;
  padding: 16px 18px;
  background: var(--kb-surface);
  border: 1.5px solid var(--ink-950);
  border-radius: 10px;
  box-shadow: 4px 4px 0 var(--ink-950);
}
.research-card.is-empty, .research-card.is-failed { box-shadow: none; border-style: dashed; border-color: var(--kb-control-line); }
.research-head { display: grid; gap: 4px; }
.research-kicker { font: 600 11px var(--kb-font-mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--kb-accent-text); }
.research-title { margin: 0; font-size: 1rem; font-weight: 800; letter-spacing: -0.01em; }
.research-note { margin: 8px 0 0; font-size: 13px; line-height: 1.45; color: var(--kb-muted); text-wrap: pretty; }
.research-sources { list-style: none; margin: 12px 0 0; padding: 0; display: grid; gap: 8px; }
.research-sources li { display: grid; grid-template-columns: 20px minmax(0, 1fr); column-gap: 10px; row-gap: 1px; align-items: baseline; }
.src-n { grid-row: 1 / span 2; font: 700 11px var(--kb-font-mono); color: var(--kb-text-2); text-align: center; border: 1.5px solid var(--ink-950); border-radius: 4px; padding: 1px 0; }
.research-sources a { font-size: 13px; font-weight: 600; color: var(--kb-text); text-decoration-color: var(--kb-control-line); text-underline-offset: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.research-sources a:hover { text-decoration-color: var(--ink-950); }
.src-host { font: 400 11px var(--kb-font-mono); color: var(--kb-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.research-more { margin: 8px 0 0 30px; font-size: 12px; color: var(--kb-muted); }
.research-foot { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--kb-line); }
.research-dl { padding: 7px 12px; border: 1.5px solid var(--ink-950); border-radius: 8px; background: var(--kb-surface); font: 600 12px var(--kb-font-sans); cursor: pointer; }
.research-dl:hover:not(:disabled) { background: var(--kb-accent-subtle); }
.research-dl:disabled { opacity: 0.6; cursor: default; }
.research-warn { font-size: 12px; color: var(--kb-muted); line-height: 1.4; }
.auto-note {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--kb-surface-2);
  color: var(--kb-text-2);
  font-size: 13px;
  line-height: 1.45;
}
.workbench-panel {
  height: 100%;
  background-color: var(--kb-surface-2);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-card {
  background: #FFF;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid var(--kb-line);
  transition: all 0.3s ease;
  position: relative; /* For absolute overlay */
}

.step-card.active {
  border-color: var(--kb-accent-line);
  box-shadow: 0 4px 12px rgba(204, 230, 115, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-num {
  font-family: var(--kb-font-mono);
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-line);
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: var(--kb-text);
}

.step-title {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-size: 10px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge.success { background: #E8F5E9; color: #2E7D32; }
.badge.processing { background: var(--kb-accent-solid); color: var(--kb-accent-on); }
.badge.accent { background: var(--kb-accent-solid); color: var(--kb-accent-on); }
.badge.pending { background: var(--kb-soft); color: var(--kb-text-on-soft); }

.api-note {
  font-family: var(--kb-font-mono);
  font-size: 10px;
  color: var(--kb-subtle);
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: var(--kb-muted);
  line-height: 1.5;
  margin-bottom: 16px;
}

/* Step 01 Tags */
.tags-container {
  margin-top: 12px;
  transition: opacity 0.3s;
}

.tags-container.dimmed {
    opacity: 0.3;
    pointer-events: none;
}

.tag-label {
  display: block;
  font-size: 10px;
  color: var(--kb-subtle);
  margin-bottom: 8px;
  font-weight: 600;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  background: var(--kb-soft);
  border: 1px solid var(--kb-line);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--kb-text-2);
  font-family: var(--kb-font-sans);
  transition: all 0.2s;
}

.entity-tag.clickable {
    cursor: pointer;
}

.entity-tag.clickable:hover {
    background: var(--kb-line);
    border-color: var(--kb-line-strong);
}

/* Ontology Detail Overlay */
.ontology-detail-overlay {
    position: absolute;
    top: 60px; /* Below header roughly */
    left: 20px;
    right: 20px;
    bottom: 20px;
    background: rgba(255, 255, 255, 0.98);
    backdrop-filter: blur(4px);
    z-index: 10;
    border: 1px solid var(--kb-line);
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--kb-line);
    background: var(--kb-surface-2);
}

.detail-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-type-badge {
    font-size: 9px;
    font-weight: 700;
    color: #FFF;
    background: var(--kb-text);
    padding: 2px 6px;
    border-radius: 2px;
    text-transform: uppercase;
}

.detail-name {
    font-size: 14px;
    font-weight: 700;
    font-family: var(--kb-font-sans);
}

.close-btn {
    background: none;
    border: none;
    font-size: 18px;
    color: var(--kb-subtle);
    cursor: pointer;
    line-height: 1;
}

.close-btn:hover {
    color: var(--kb-text-2);
}

.detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

.detail-desc {
    font-size: 12px;
    color: var(--kb-text-2);
    line-height: 1.5;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px dashed var(--kb-line);
}

.detail-section {
    margin-bottom: 16px;
}

.section-label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    color: var(--kb-subtle);
    margin-bottom: 8px;
}

.attr-list, .conn-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.attr-item {
    font-size: 11px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
    padding: 4px;
    background: var(--kb-surface-2);
    border-radius: 4px;
}

.attr-name {
    font-family: var(--kb-font-sans);
    font-weight: 600;
    color: var(--kb-text);
}

.attr-type {
    color: var(--kb-subtle);
    font-size: 10px;
}

.attr-desc {
    color: var(--kb-text-2);
    flex: 1;
    min-width: 150px;
}

.example-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.example-tag {
    font-size: 11px;
    background: #FFF;
    border: 1px solid var(--kb-line);
    padding: 3px 8px;
    border-radius: 12px;
    color: var(--kb-text-2);
}

.conn-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 6px;
    background: var(--kb-soft);
    border-radius: 4px;
    font-family: var(--kb-font-mono);
}

.conn-node {
    font-weight: 600;
    color: var(--kb-text-2);
}

.conn-arrow {
    color: #BBB;
}

/* Step 02 Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  background: var(--kb-surface-2);
  padding: 16px;
  border-radius: 6px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
}

.stat-label {
  font-size: 9px;
  color: var(--kb-subtle);
  text-transform: uppercase;
  margin-top: 4px;
  display: block;
}

/* Step 03 Button */
.action-btn {
  width: 100%;
  background: var(--kb-text);
  color: #FFF;
  border: none;
  padding: 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn:disabled {
  background: var(--kb-line-strong);
  cursor: not-allowed;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--kb-accent-text);
  margin-bottom: 12px;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #FFCCBC;
  border-top-color: var(--kb-accent-line);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* System Logs */
.system-logs {
  background: var(--kb-text);
  color: var(--kb-line-strong);
  padding: 16px;
  font-family: var(--kb-font-mono);
  border-top: 1px solid var(--kb-text);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid var(--kb-text-2);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 11px;
  color: var(--kb-muted-on-dark);
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px; /* Approx 4 lines visible */
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--kb-text-2);
  border-radius: 2px;
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: var(--kb-muted);
  min-width: 75px;
}

.log-msg {
  color: var(--kb-line-strong);
  word-break: break-all;
}
</style>
