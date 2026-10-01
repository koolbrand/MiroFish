<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <router-link to="/" class="brand-link" aria-label="Simuloo"><BrandLogo class="brand" /></router-link>
        <ProjectNameChip
          v-if="currentProjectId && currentProjectId !== 'new'"
          :projectId="currentProjectId"
          :name="projectData?.name"
          @updated="onProjectRenamed"
        />
      </div>

      <!-- Centro: las etapas y su estado (la navegación principal del proceso) -->
      <div class="header-center">
        <div data-tour="main-stepper">
          <WizardStepper
            :currentStep="currentStep"
            :projectId="currentProjectId && currentProjectId !== 'new' ? currentProjectId : null"
          />
        </div>
        <span class="step-divider"></span>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>

      <div class="header-right">
        <div class="view-switcher" data-tour="main-view-switcher">
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
        <HelpButton compact tourId="mainStep1" :resolve="resolveMainTour" />
        <AppVersion class="tech-only" />
      </div>
    </header>

    <AutoPipelineBanner :projectId="currentProjectId && currentProjectId !== 'new' ? currentProjectId : null" :step="1" />

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :class="{ 'has-failure': failed }" :inert="failed || undefined" :style="leftPanelStyle" data-tour="main-graph-panel">
        <GraphPanel
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="currentPhase"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step Components -->
      <div class="panel-wrapper right" :class="{ 'has-failure': failed }" :style="rightPanelStyle" data-tour="main-step-panel">
        <!-- Si algo falla (el análisis del documento o la construcción del mapa), se dice claro y con salida -->
        <div v-if="failed" class="failure" role="alert">
          <BiankaAvatar class="failure-face" :look="failureLook" bucket="undecided" :pixel="3" />
          <div class="failure-body">
            <h2 class="failure-title">{{ $t('main.failTitle') }}</h2>
            <p class="failure-text">{{ failureText }}</p>
            <div class="failure-actions">
              <button v-if="canRetry" type="button" class="failure-retry" :disabled="loading" @click="retryFromError">{{ $t('main.failRetry') }}</button>
              <router-link to="/" class="failure-back">{{ $t('main.failBack') }}</router-link>
            </div>
            <details class="failure-details">
              <summary>{{ $t('main.failDetails') }}</summary>
              <code>{{ error }}</code>
            </details>
          </div>
        </div>
        <!-- Step 1: 图谱构建 -->
        <Step1GraphBuild 
          v-if="currentStep === 1"
          :currentPhase="currentPhase"
          :projectData="projectData"
          :ontologyProgress="ontologyProgress"
          :buildProgress="buildProgress"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @next-step="handleNextStep"
        />
        <!-- Step 2: 环境搭建 -->
        <Step2EnvSetup
          v-else-if="currentStep === 2"
          :projectData="projectData"
          :graphData="graphData"
          :systemLogs="systemLogs"
          @go-back="handleGoBack"
          @next-step="handleNextStep"
          @add-log="addLog"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import GraphPanel from '../components/GraphPanel.vue'
import Step1GraphBuild from '../components/Step1GraphBuild.vue'
import Step2EnvSetup from '../components/Step2EnvSetup.vue'
import WizardStepper from '../components/WizardStepper.vue'
import AutoPipelineBanner from '../components/AutoPipelineBanner.vue'
import { generateOntology, getProject, buildGraph, getTaskStatus, getGraphData } from '../api/graph'
import { startAutoPipeline } from '../api/pipeline'
import { usePipeline } from '../composables/usePipeline'
import { getPendingUpload, clearPendingUpload, setLaunching } from '../store/pendingUpload'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import AppVersion from '../components/AppVersion.vue'
import BrandLogo from '../components/BrandLogo.vue'
import ProjectNameChip from '../components/ProjectNameChip.vue'
import HelpButton from '../components/HelpButton.vue'
import BiankaAvatar from '../components/BiankaAvatar.vue'
import { useTutorial } from '../composables/useTutorial'
import { getTour } from '../tours/tours'

const route = useRoute()
const router = useRouter()
const { t, tm } = useI18n()
const { maybeAutoStart } = useTutorial()

// Pick the right tour based on the current wizard step so the "?" button and
// auto-launch both stay in sync with what the user is looking at.
const resolveMainTour = () => {
  if (currentStep.value === 2) return 'mainStep2'
  return 'mainStep1'
}

// Layout State
const viewMode = ref(typeof window !== 'undefined' && window.innerWidth <= 900 ? 'workbench' : 'split') // graph | split | workbench (en móvil, solo uno a la vez)

// Step State
const currentStep = ref(1) // 1: 图谱构建, 2: 环境搭建, 3: 开始模拟, 4: 报告生成, 5: 深度互动
const stepNames = computed(() => tm('main.stepNames'))

// Data State
const currentProjectId = ref(route.params.projectId)
const { isRunning: autoRunning, refresh: refreshPipeline } = usePipeline(() => (currentProjectId.value && currentProjectId.value !== 'new' ? currentProjectId.value : null))
const loading = ref(false)
const graphLoading = ref(false)
const error = ref('')
const projectData = ref(null)
const graphData = ref(null)
const currentPhase = ref(-1) // -1: Upload, 0: Ontology, 1: Build, 2: Complete
const ontologyProgress = ref(null)
const buildProgress = ref(null)
const systemLogs = ref([])

// Polling timers
let pollTimer = null
let graphPollTimer = null
// Se pone al salir de la pantalla: tras cada `await` largo se mira para no seguir actuando (navegar, abrir sondeos) en una pantalla ya cerrada
let unmounted = false

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
// El aviso de fallo: qué ha pasado, en cristiano, y qué se puede hacer (el detalle técnico queda plegado)
const failureLook = { ears: 'flop', body: 'bowtie' }
const failed = computed(() => !!error.value && currentStep.value === 1)
const noPending = computed(() => error.value === t('log.noPendingFilesError'))
const failureText = computed(() => (noPending.value ? t('main.failBodyNoFiles') : currentProjectId.value === 'new' ? t('main.failBodyNew') : t('main.failBodyBuild')))
const canRetry = computed(() => !noPending.value && (currentProjectId.value !== 'new' || getPendingUpload().isPending))
const retryFromError = async () => {
  if (loading.value) return
  const isNew = currentProjectId.value === 'new'
  error.value = ''
  if (isNew) await handleNewProject()
  else await startBuildGraph()
}

const statusClass = computed(() => {
  if (error.value) return 'error'
  if (currentPhase.value >= 2) return 'completed'
  return 'processing'
})

const statusText = computed(() => {
  if (error.value) return t('log.statusError')
  if (currentPhase.value >= 2) return t('log.statusReady')
  if (currentPhase.value === 1) return t('log.statusBuilding')
  if (currentPhase.value === 0) return t('log.statusOntology')
  return t('log.statusInitializing')
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  // Keep last 100 logs
  if (systemLogs.value.length > 100) {
    systemLogs.value.shift()
  }
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

const handleNextStep = (params = {}) => {
  if (currentStep.value < 5) {
    currentStep.value++
    addLog(t('log.enterStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
    
    // 如果是从 Step 2 进入 Step 3，记录模拟轮数配置
    if (currentStep.value === 3 && params.maxRounds) {
      addLog(t('log.customSimRounds', { rounds: params.maxRounds }))
    }
  }
}

const handleGoBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    addLog(t('log.returnToStep', { step: currentStep.value, name: stepNames.value[currentStep.value - 1] }))
  }
}

// --- Data Logic ---

const initProject = async () => {
  addLog(t('log.projectViewInit'))
  if (currentProjectId.value === 'new') {
    await handleNewProject()
  } else {
    await loadProject()
  }
}

const handleNewProject = async () => {
  const pending = getPendingUpload()
  if (!pending.isPending || pending.files.length === 0) {
    error.value = t('log.noPendingFilesError')
    addLog(t('log.noPendingFilesLog'))
    return
  }
  setLaunching(true)
  
  try {
    loading.value = true
    currentPhase.value = 0
    ontologyProgress.value = { message: t('log.ontologyStart') }
    addLog(t('log.ontologyStart'))
    
    const formData = new FormData()
    pending.files.forEach(f => formData.append('files', f))
    formData.append('simulation_requirement', pending.simulationRequirement)
    if (pending.projectName && pending.projectName.trim()) {
      formData.append('project_name', pending.projectName.trim())
    }

    if (pending.webResearch) formData.append('web_research', 'true')
    // Rondas de la simulación: solo el automático las fija desde la portada (el manual las elige en el paso 2)
    if (pending.mode === 'auto') formData.append('max_rounds', String(pending.rounds))

    // Automático: el servidor lee el material y sigue solo hasta el informe; esta pantalla solo observa
    if (pending.mode === 'auto') {
      const autoRes = await startAutoPipeline(formData)
      clearPendingUpload()
      // La persona se fue mientras se enviaba: el proyecto ya existe (está en Proyectos); no se la "teletransporta"
      if (unmounted) return
      currentProjectId.value = autoRes.data.project_id
      router.replace({ name: 'Process', params: { projectId: autoRes.data.project_id } })
      addLog(t('log.autoStarted', { id: autoRes.data.project_id }))
      await refreshPipeline()
      await loadProject()
      return
    }

    const res = await generateOntology(formData, pending.webResearch ? { timeout: 600000 } : {})
    if (res.success) {
      clearPendingUpload()
      if (unmounted) return           // el proyecto queda creado; al abrirlo se retoma (ontología hecha → grafo)
      currentProjectId.value = res.data.project_id
      projectData.value = res.data
      
      router.replace({ name: 'Process', params: { projectId: res.data.project_id } })
      ontologyProgress.value = null
      addLog(t('log.ontologyDone', { id: res.data.project_id }))
      await startBuildGraph()
    } else {
      error.value = res.error || 'Ontology generation failed'
      addLog(t('log.ontologyError', { error: error.value }))
      ontologyProgress.value = null
      currentPhase.value = -1
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in handleNewProject: ${err.message}`)
    ontologyProgress.value = null
    currentPhase.value = -1
  } finally {
    setLaunching(false)
    loading.value = false
  }
}

const loadProject = async () => {
  try {
    loading.value = true
    addLog(t('log.loadingProject', { id: currentProjectId.value }))
    const res = await getProject(currentProjectId.value)
    if (res.success) {
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      addLog(t('log.projectLoadedStatus', { status: res.data.status }))
      
      // En automático el grafo lo lanza el servidor: aquí solo se espera a que empiece
      if (['created', 'ontology_generated'].includes(res.data.status) && !res.data.graph_id && await autoInCharge()) {
        watchAutoProject()
      } else if (res.data.status === 'ontology_generated' && !res.data.graph_id) {
        await startBuildGraph()
      } else if (res.data.status === 'graph_building') {
        // If graph already has data (e.g. server restart left status stale),
        // skip polling a dead task and treat the build as complete.
        if (res.data.graph_id) {
          try {
            const gRes = await getGraphData(res.data.graph_id)
            const hasData = gRes.success && (gRes.data?.node_count > 0 || (gRes.data?.nodes?.length || 0) > 0)
            if (hasData) {
              currentPhase.value = 2
              graphData.value = gRes.data
              addLog(t('log.graphRecovered', {
                nodes: gRes.data.node_count || gRes.data.nodes.length,
                edges: gRes.data.edge_count || gRes.data.edges?.length || 0
              }))
              return
            }
          } catch (gErr) {
            console.warn('Graph recovery probe failed:', gErr)
          }
        }
        // Real in-progress build: resume polling.
        currentPhase.value = 1
        if (res.data.graph_build_task_id) {
          startPollingTask(res.data.graph_build_task_id)
        } else {
          buildProgress.value = { progress: 0, message: t('log.graphBuildResuming') }
        }
        startGraphPolling()
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      }
    } else {
      error.value = res.error
      addLog(`Error loading project: ${res.error}`)
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in loadProject: ${err.message}`)
  } finally {
    loading.value = false
  }
}

// ¿Lleva este proyecto el automático del servidor? (entonces la pantalla no lanza etapas)
const autoInCharge = async () => {
  await refreshPipeline().catch(() => {})
  return autoRunning.value
}

// Mientras el servidor lee el material y arranca el grafo: consultar el proyecto hasta que haya grafo en marcha
let autoWatchTimer = null
const watchAutoProject = () => {
  if (unmounted) return
  clearTimeout(autoWatchTimer)
  if (!ontologyProgress.value) ontologyProgress.value = { message: t('log.ontologyStart') }
  autoWatchTimer = setTimeout(async () => {
    if (unmounted) return
    try {
      const res = await getProject(currentProjectId.value)
      if (unmounted) return
      if (!res.success) return watchAutoProject()
      projectData.value = res.data
      updatePhaseByStatus(res.data.status)
      if (res.data.status === 'graph_building') {
        ontologyProgress.value = null
        currentPhase.value = 1
        if (res.data.graph_build_task_id) startPollingTask(res.data.graph_build_task_id)
        startGraphPolling()
      } else if (res.data.status === 'graph_completed' && res.data.graph_id) {
        ontologyProgress.value = null
        currentPhase.value = 2
        await loadGraph(res.data.graph_id)
      } else if (res.data.status !== 'failed' && autoRunning.value) {
        watchAutoProject()
      } else {
        ontologyProgress.value = null
      }
    } catch (e) {
      watchAutoProject()
    }
  }, 3000)
}

const updatePhaseByStatus = (status) => {
  switch (status) {
    case 'created':
    case 'ontology_generated': currentPhase.value = 0; break;
    case 'graph_building': currentPhase.value = 1; break;
    case 'graph_completed': currentPhase.value = 2; break;
    case 'failed': error.value = t('log.projectFailedError'); break;
  }
}

const startBuildGraph = async () => {
  try {
    currentPhase.value = 1
    buildProgress.value = { progress: 0, message: t('log.graphBuildInitiated') }
    addLog(t('log.graphBuildInitiated'))

    const res = await buildGraph({ project_id: currentProjectId.value })
    if (res.success) {
      addLog(t('log.graphBuildTaskStartedId', { taskId: res.data.task_id }))
      startGraphPolling()
      startPollingTask(res.data.task_id)
    } else {
      error.value = res.error
      addLog(t('log.startBuildError', { error: res.error }))
    }
  } catch (err) {
    error.value = err.message
    addLog(`Exception in startBuildGraph: ${err.message}`)
  }
}

const startGraphPolling = () => {
  if (unmounted) return
  stopGraphPolling()              // «Reintentar» abría un segundo intervalo y dejaba el primero sin referencia
  addLog(t('log.pollingStarted'))
  fetchGraphData()
  graphPollTimer = setInterval(fetchGraphData, 10000)
}

const fetchGraphData = async () => {
  try {
    // Refresh project info to check for graph_id
    const projRes = await getProject(currentProjectId.value)
    if (projRes.success && projRes.data.graph_id) {
      const gRes = await getGraphData(projRes.data.graph_id)
      if (gRes.success) {
        graphData.value = gRes.data
        const nodeCount = gRes.data.node_count || gRes.data.nodes?.length || 0
        const edgeCount = gRes.data.edge_count || gRes.data.edges?.length || 0
        addLog(t('log.graphRefreshed', { nodes: nodeCount, edges: edgeCount }))
      }
    }
  } catch (err) {
    console.warn('Graph fetch error:', err)
  }
}

const startPollingTask = (taskId) => {
  if (unmounted) return
  stopPolling()
  pollTaskStatus(taskId)
  pollTimer = setInterval(() => pollTaskStatus(taskId), 2000)
}

const pollTaskStatus = async (taskId) => {
  try {
    const res = await getTaskStatus(taskId)
    if (res.success) {
      const task = res.data
      
      // Log progress message if it changed
      if (task.message && task.message !== buildProgress.value?.message) {
        addLog(task.message)
      }
      
      buildProgress.value = { progress: task.progress || 0, message: task.message }
      
      if (task.status === 'completed') {
        addLog(t('log.graphBuildTaskCompleted'))
        stopPolling()
        stopGraphPolling() // Stop polling, do final load
        currentPhase.value = 2
        
        // Final load
        const projRes = await getProject(currentProjectId.value)
        if (projRes.success && projRes.data.graph_id) {
            projectData.value = projRes.data
            await loadGraph(projRes.data.graph_id)
        }
      } else if (task.status === 'failed') {
        stopPolling()
        stopGraphPolling()           // el sondeo del grafo (10 s) seguía para siempre tras un fallo
        error.value = task.error
        addLog(t('log.graphBuildTaskFailed', { error: task.error }))
      }
    }
  } catch (e) {
    console.error(e)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  addLog(t('log.loadingFullGraph', { graphId }))
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog(t('log.graphLoadedOk'))
    } else {
      addLog(t('log.graphLoadFailed', { error: res.error }))
    }
  } catch (e) {
    addLog(t('log.graphLoadFailed', { error: e.message }))
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    addLog(t('log.manualRefresh'))
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
  addLog(t('log.projectRenamed', { name: updated.name }))
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const stopGraphPolling = () => {
  if (graphPollTimer) {
    clearInterval(graphPollTimer)
    graphPollTimer = null
    addLog(t('log.graphPollingStopped'))
  }
}

onMounted(() => {
  initProject()
  // First time landing on the wizard → explain Step 1 layout.
  nextTick(() => maybeAutoStart('mainStep1', getTour('mainStep1')))
})

onUnmounted(() => {
  unmounted = true
  clearTimeout(autoWatchTimer)
  stopPolling()
  stopGraphPolling()
})

// When the user advances to Step 2 for the first time, auto-launch that
// tour so they understand the environment-setup UI.
watch(currentStep, (step, prev) => {
  if (step === 2 && prev !== 2) {
    nextTick(() => maybeAutoStart('mainStep2', getTour('mainStep2')))
  }
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
  color: var(--kb-text-on-soft);   /* #6E6E6E sobre el fondo gris da 4,32:1; la tinta, 12:1 */
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #FFF;
  color: var(--kb-text);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--kb-muted);
  font-weight: 500;
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

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--kb-line-strong);
}

.status-indicator.processing .dot { background: var(--kb-accent-solid); animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: var(--kb-ok-text); }
.status-indicator.error .dot { background: var(--kb-danger); }

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

/* El aviso de fallo ocupa su alto natural arriba y el paso llena el resto (sin quedar recortado por abajo) */
.panel-wrapper.right { display: flex; flex-direction: column; }
.panel-wrapper.right :deep(.workbench-panel) { height: auto; flex: 1 1 0; min-height: 0; }
/* mientras dura el fallo, lo que hay alrededor del aviso queda apagado: no dice «esperando…» ni «completada» */
.panel-wrapper.left.has-failure > *, .panel-wrapper.right.has-failure :deep(.scroll-container) { opacity: 0.4; filter: grayscale(1); transition: opacity 0.2s ease; }
.panel-wrapper.right.has-failure :deep(.scroll-container) { pointer-events: none; user-select: none; }

/* Aviso de fallo (análisis o construcción del mapa) */
.failure {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin: 20px 24px 8px;
  padding: 18px 20px;
  background: var(--cream-100, #F2F1EF);
  border: 2px solid var(--ink-950, #111);
  border-radius: 14px;
  box-shadow: 4px 4px 0 var(--ink-950, #111);
}
.failure-face { flex: none; }
.failure-body { min-width: 0; }
.failure-title { margin: 0 0 6px; font-size: 1.1rem; font-weight: 800; letter-spacing: -0.01em; }
.failure-text { margin: 0 0 14px; font-size: 0.92rem; line-height: 1.5; color: var(--kb-text-2, #2A2A2A); text-wrap: pretty; }
.failure-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.failure-retry, .failure-back {
  display: inline-flex;
  align-items: center;
  padding: 10px 16px;
  border: 1px solid var(--ink-950, #111);
  border-radius: 8px;
  font: 600 0.9rem/1 var(--kb-font-sans);
  text-decoration: none;
  cursor: pointer;
}
.failure-retry { background: var(--lime-500, #CCE673); color: var(--ink-950, #111); }
.failure-retry:hover:not(:disabled) { background: var(--lime-600, #ACC451); }
.failure-retry:disabled { opacity: 0.5; cursor: not-allowed; }
.failure-back { background: #fff; color: var(--ink-950, #111); }
.failure-back:hover { background: var(--cream-100, #F2F1EF); }
.failure-details { margin-top: 12px; font-size: 0.8rem; color: var(--kb-muted, #6E6E6E); }
.failure-details summary { cursor: pointer; }
.failure-details code { display: block; margin-top: 6px; padding: 8px 10px; background: #fff; border: 1px solid var(--kb-line, #DDD); border-radius: 6px; font-family: var(--kb-font-mono); font-size: 0.75rem; overflow-wrap: anywhere; }

/* Pantallas estrechas: el encabezado se reparte en filas y el aviso de fallo cabe entero */
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
  .failure { margin: 14px 14px 8px; padding: 16px; gap: 12px; }
}
@media (max-width: 480px) {
  .failure { flex-direction: column; }
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