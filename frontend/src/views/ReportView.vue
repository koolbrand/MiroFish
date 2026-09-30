<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <BrandLogo class="brand" @click="router.push('/')" />
        <ProjectNameChip
          v-if="projectData?.project_id"
          :projectId="projectData.project_id"
          :name="projectData.name"
          @updated="onProjectRenamed"
        />
      </div>

      <!-- Centro: las etapas y su estado (la navegación principal del proceso) -->
      <div class="header-center">
        <div data-tour="report-stepper">
          <WizardStepper
            :currentStep="4"
            :projectId="projectData?.project_id || null"
            :simulationId="simulationId"
            :reportId="currentReportId"
          />
        </div>
        <span class="step-divider"></span>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>

      <div class="header-right">
        <div class="view-switcher">
          <button 
            v-for="mode in ['graph', 'split', 'workbench']" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: $t('main.layoutGraph'), split: $t('main.layoutSplit'), workbench: $t('main.layoutWorkbench') }[mode] }}
          </button>
        </div>
        <div class="step-divider"></div>
        <LanguageSwitcher compact />
        <HelpButton compact tourId="report" />
        <AppVersion class="tech-only" />
      </div>
    </header>

    <AutoPipelineBanner :projectId="projectData?.project_id || null" :step="4" />

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle" data-tour="report-graph-panel">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="4"
          :isSimulating="false"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step4 报告生成 -->
      <div class="panel-wrapper right" :style="rightPanelStyle" data-tour="report-panel">
        <Step4Report
          :reportId="currentReportId"
          :simulationId="simulationId"
          :systemLogs="systemLogs"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '../components/GraphPanel.vue'
import Step4Report from '../components/Step4Report.vue'
import WizardStepper from '../components/WizardStepper.vue'
import AutoPipelineBanner from '../components/AutoPipelineBanner.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getReport } from '../api/report'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import AppVersion from '../components/AppVersion.vue'
import HelpButton from '../components/HelpButton.vue'
import { useTutorial } from '../composables/useTutorial'
import { getTour } from '../tours/tours'
import BrandLogo from '../components/BrandLogo.vue'
import ProjectNameChip from '../components/ProjectNameChip.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { maybeAutoStart } = useTutorial()

// Props
const props = defineProps({
  reportId: String
})

// Layout State - 默认切换到工作台视角
const viewMode = ref('workbench')

// Data State
const currentReportId = ref(route.params.reportId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return t('ui.status.error')
  if (currentStatus.value === 'completed') return t('ui.status.completed')
  return t('ui.status.generating')
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

// --- Data Logic ---
const loadReportData = async () => {
  try {
    addLog(t('log.loadReportData', { id: currentReportId.value }))

    // 获取 report 信息以获取 simulation_id
    const reportRes = await getReport(currentReportId.value)
    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id

      if (simulationId.value) {
        // 获取 simulation 信息
        const simRes = await getSimulation(simulationId.value)
        if (simRes.success && simRes.data) {
          const simData = simRes.data

          // 获取 project 信息
          if (simData.project_id) {
            const projRes = await getProject(simData.project_id)
            if (projRes.success && projRes.data) {
              projectData.value = projRes.data
              addLog(t('log.projectLoadSuccess', { id: projRes.data.project_id }))

              // 获取 graph 数据
              if (projRes.data.graph_id) {
                await loadGraph(projRes.data.graph_id)
              }
            }
          }
        }
      }
    } else {
      addLog(t('log.getReportInfoFailed', { error: reportRes.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.loadException', { error: err.message }))
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog(t('log.graphDataLoadSuccess'))
    }
  } catch (err) {
    addLog(t('log.graphLoadFailed', { error: err.message }))
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

const onProjectRenamed = (updated) => {
  if (!updated) return
  if (projectData.value) {
    projectData.value = { ...projectData.value, name: updated.name }
  } else {
    projectData.value = updated
  }
}

// Watch route params
watch(() => route.params.reportId, (newId) => {
  if (newId && newId !== currentReportId.value) {
    currentReportId.value = newId
    loadReportData()
  }
}, { immediate: true })

onMounted(() => {
  addLog(t('log.reportViewInit'))
  loadReportData()

  // First visit → walk through the report view.
  maybeAutoStart('report', getTour('report'))
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--kb-bg);
  overflow: hidden;
  font-family: var(--kb-font-sans);
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 1px solid var(--kb-line);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  background: #FFF;
  z-index: 100;
  position: relative;
}

.header-left {
  justify-self: start;
  display: flex;
  align-items: center;
  min-width: 0;
}

.header-center {
  justify-self: center;
}

.brand {
  font-size: 22px;
  cursor: pointer;
  color: inherit;
  transition: opacity 0.15s ease;
}

.brand:hover {
  opacity: 0.7;
}

.view-switcher {
  display: flex;
  background: var(--kb-soft);
  padding: 4px;
  border-radius: 6px;
  gap: 4px;
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: var(--kb-text);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.header-right {
  justify-self: end;
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 6px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: var(--kb-font-mono);
  font-weight: 700;
  color: var(--kb-subtle);
}

.step-name {
  font-weight: 700;
  color: var(--kb-text);
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: var(--kb-line);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--kb-muted);
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--kb-line-strong);
}

.status-indicator.processing .dot { background: #FF9800; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse { 50% { opacity: 0.5; } }

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 1px solid var(--kb-line);
}

/* Pantallas estrechas: el encabezado se reparte en filas (el mapa y la mesa de trabajo no caben juntos) */
@media (max-width: 900px) {
  .main-view { height: 100dvh; }
  .app-header {
    display: flex;
    flex-wrap: wrap;
    height: auto;
    gap: 8px 12px;
    padding: 10px 16px;
  }
  .header-left { flex: 1 1 auto; }
  .header-center { order: 3; flex: 1 1 100%; }
  .view-switcher { width: 100%; }
  .switch-btn { flex: 1; padding-inline: 8px; }
  .header-right { flex: 1 1 100%; justify-content: space-between; gap: 10px; }
  .header-right :deep(.app-version-badge), .step-divider { display: none; }
}

/* ── Cabecera común de las pantallas del proceso ─────────────────────────────
   Izquierda (marca y proyecto) y derecha (vista, idioma, tutorial) a su tamaño; el centro,
   con las etapas y su estado, se queda el resto. Antes el reparto era simétrico y la derecha
   no cabía por debajo de ~2100 px: saltaba a otra fila dentro de 60 px y tocaba el borde. */
.app-header {
  height: auto;
  min-height: 60px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas: "left center right";
  column-gap: 24px;
  row-gap: 8px;
  padding-block: 8px;
}
.header-left { grid-area: left; }
.header-center {
  grid-area: center;
  justify-self: center;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.header-right { grid-area: right; flex-wrap: nowrap; gap: 12px; }
@media (max-width: 1320px) and (min-width: 901px) {
  /* portátiles: dos filas pensadas (marca y herramientas arriba, etapas centradas debajo) */
  .app-header {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-areas: "left right" "center center";
    padding-block: 10px;
  }
}
@media (max-width: 900px) {
  /* móvil: idioma y tutorial junto a la marca; el selector de vista y las etapas, cada uno en su fila */
  .header-right { display: contents; }
  .header-right .view-switcher { order: 2; flex: 1 1 100%; width: 100%; }
  .header-right .step-divider { display: none; }
  .header-center { order: 3; flex: 1 1 100%; justify-content: space-between; }
  .switch-btn { white-space: nowrap; }
  /* el nombre del proyecto se recorta antes de empujar el idioma y el tutorial a otra fila */
  .header-left { flex: 1 1 0; min-width: 0; }
  .header-left :deep(.project-chip) { min-width: 0; margin-left: 10px; }
  .header-left :deep(.chip-text) { min-width: 0; }
  .header-left :deep(.chip-label) { min-width: 0; max-width: none; }
}
</style>
