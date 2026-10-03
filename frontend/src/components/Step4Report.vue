<template>
  <div class="report-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel" data-tour="rep-left-panel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block" data-tour="rep-header">
            <div class="report-meta">
              <span class="report-tag">{{ $t('ui.predictionReport') }}</span>
              <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
              <ReportDownloads v-if="reportId" :report-id="reportId" :disabled="!isComplete" />
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <p v-if="cisCita" class="cis-source-line" data-testid="cis-source">{{ cisCita }}</p>
            <SimulationEvidenceNotice :simulation-id="simulationId" :evidence="reportEvidence" report :report-ready="reportChecked" :legacy-report="reportChecked && !reportEvidence?.version" />
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list" data-tour="rep-sections">
            <div 
              v-for="(section, idx) in reportOutline.sections" 
              :key="idx"
              class="report-section-item"
              :class="{ 
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <!-- El plegado se maneja con teclado desde este botón; la fila entera sigue respondiendo al clic -->
                <button
                  v-if="isSectionCompleted(idx + 1)"
                  type="button"
                  class="r4-icon-btn collapse-btn"
                  :aria-expanded="String(!collapsedSections.has(idx))"
                  :aria-controls="`r4-section-${idx}`"
                  :aria-label="collapsedSections.has(idx) ? $t('step4.expandSection', { title: section.title }) : $t('step4.collapseSection', { title: section.title })"
                  @click.stop="toggleSectionCollapse(idx)"
                >
                  <svg
                    class="collapse-icon"
                    :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                    viewBox="0 0 24 24"
                    width="20"
                    height="20"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    aria-hidden="true"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
              </div>

              <div class="section-body" :id="`r4-section-${idx}`" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>

                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none">
                      <circle class="spin-track" cx="12" cy="12" r="10" stroke-width="4"></circle>
                      <path class="spin-head" d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation" aria-hidden="true">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">{{ $t('step4.waitingForReportAgent') }}</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Workflow Timeline -->
      <div class="right-panel" ref="rightPanel" data-tour="rep-workflow">
        <!-- El informe falló o no existe: se dice, con el motivo, y se puede volver a generar -->
        <div v-if="reportError" class="report-failed" role="alert">
          <strong class="report-failed-title">{{ $t('step4.failedTitle') }}</strong>
          <p class="report-failed-text">{{ reportError }}</p>
          <button
            v-if="simulationId"
            type="button"
            class="report-failed-btn"
            :disabled="regenerating"
            @click="regenerate"
          >{{ regenerating ? $t('step4.regenerating') : $t('step4.regenerate') }}</button>
          <p v-if="regenerateError" class="report-failed-text">{{ regenerateError }}</p>
        </div>
        <div class="panel-header" :class="`panel-header--${activeStep.status}`" v-if="!isComplete">
          <span class="header-dot" v-if="activeStep.status === 'active'"></span>
          <span class="header-index mono">{{ activeStep.noLabel }}</span>
          <span class="header-title">{{ activeStep.title }}</span>
          <span class="header-meta mono" v-if="activeStep.meta">{{ activeStep.meta }}</span>
        </div>

        <!-- Workflow Overview (flat, status-based palette) -->
        <div class="workflow-overview" v-if="agentLogs.length > 0 || reportOutline">
          <div class="workflow-metrics">
            <div class="metric">
              <span class="metric-label">{{ $t('ui.sections') }}</span>
              <span class="metric-value mono">{{ completedSections }}/{{ totalSections }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">{{ $t('ui.elapsed') }}</span>
              <span class="metric-value mono">{{ formatElapsedTime }}</span>
            </div>
            <div class="metric metric-right">
              <span class="metric-pill" :class="`pill--${statusClass}`">{{ statusText }}</span>
            </div>
          </div>

          <div class="workflow-steps" v-if="workflowSteps.length > 0">
            <div
              v-for="(step, sidx) in workflowSteps"
              :key="step.key"
              class="wf-step"
              :class="`wf-step--${step.status}`"
            >
              <!-- Estado por forma: aro vacío (pendiente), punto tinta (en curso), punto lima con marca (hecho) -->
              <div class="wf-step-connector" aria-hidden="true">
                <div class="wf-step-dot">
                  <svg v-if="step.status === 'done'" viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </div>
                <div class="wf-step-line" v-if="sidx < workflowSteps.length - 1"></div>
              </div>

              <div class="wf-step-content">
                <div class="wf-step-title-row">
                  <span class="wf-step-index mono">{{ step.noLabel }}</span>
                  <span class="wf-step-title">{{ step.title }}</span>
                  <span class="wf-step-meta mono" v-if="step.meta">{{ step.meta }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Next Step Button - 在完成后显示 -->
          <button v-if="isComplete" type="button" class="next-step-btn" @click="goToInteraction">
            <span>{{ $t('step4.goToInteraction') }}</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>

          <div class="workflow-divider"></div>
        </div>

        <!-- Qué hizo el agente paso a paso (iteraciones, herramientas, parámetros JSON): detalle técnico que a casi nadie
             le interesa. Sigue el mismo criterio que el resto de la app —«detalles técnicos» ocultos por defecto, con un
             solo conmutador global (el «Ver registro» de la barra inferior)—; el progreso en lenguaje llano está arriba. -->
        <section v-if="showTech && displayLogs.length" class="tech-timeline">
          <h3 class="tech-timeline-title">{{ $t('step4.techTimeline') }}</h3>
          <div class="workflow-timeline">
            <TransitionGroup name="timeline-item">
              <div 
                v-for="(log, idx) in displayLogs" 
                :key="log.timestamp + '-' + idx"
                class="timeline-item"
                :class="getTimelineItemClass(log, idx, displayLogs.length)"
              >
                <!-- Timeline Connector -->
                <div class="timeline-connector" aria-hidden="true">
                  <div class="connector-dot" :class="getConnectorClass(log, idx, displayLogs.length)"></div>
                  <div class="connector-line" v-if="idx < displayLogs.length - 1"></div>
                </div>
                
                <!-- Timeline Content -->
                <div class="timeline-content">
                  <div class="timeline-header">
                    <span class="action-label">{{ getActionLabel(log.action) }}</span>
                    <span class="action-time">{{ formatTime(log.timestamp) }}</span>
                  </div>
                  
                  <!-- Action Body - Different for each type -->
                  <div class="timeline-body" :class="{ 'collapsed': isLogCollapsed(log) }" @click="toggleLogExpand(log)">
                    
                    <!-- Report Start -->
                    <template v-if="log.action === 'report_start'">
                      <div class="info-row">
                        <span class="info-key">{{ $t('ui.simulation') }}</span>
                        <span class="info-val mono">{{ log.details?.simulation_id }}</span>
                      </div>
                      <div class="info-row" v-if="log.details?.simulation_requirement">
                        <span class="info-key">{{ $t('ui.requirement') }}</span>
                        <span class="info-val">{{ log.details.simulation_requirement }}</span>
                      </div>
                    </template>

                    <!-- Planning -->
                    <template v-if="log.action === 'planning_start'">
                      <div class="status-message planning">{{ log.details?.message }}</div>
                    </template>
                    <template v-if="log.action === 'planning_complete'">
                      <div class="status-message success">{{ log.details?.message }}</div>
                      <div class="outline-badge" v-if="log.details?.outline">
                        {{ $t('step4.sectionsPlanned', { count: log.details.outline.sections?.length || 0 }) }}
                      </div>
                    </template>

                    <!-- Section Start -->
                    <template v-if="log.action === 'section_start'">
                      <div class="section-tag">
                        <span class="tag-num">#{{ log.section_index }}</span>
                        <span class="tag-title">{{ log.section_title }}</span>
                      </div>
                    </template>
                    
                    <!-- Section Content Generated (内容生成完成，但整个章节可能还没完成) -->
                    <template v-if="log.action === 'section_content'">
                      <div class="section-tag content-ready">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                          <path d="M12 20h9"></path>
                          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                        </svg>
                        <span class="tag-title">{{ log.section_title }}</span>
                      </div>
                    </template>

                    <!-- Section Complete (章节生成完成) -->
                    <template v-if="log.action === 'section_complete'">
                      <div class="section-tag completed">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span class="tag-title">{{ log.section_title }}</span>
                      </div>
                    </template>

                    <!-- Tool Call -->
                    <template v-if="log.action === 'tool_call'">
                      <!-- Cada herramienta se reconoce por su icono y su nombre, no por un color propio -->
                      <div class="tool-badge">
                        <span class="tool-tile" aria-hidden="true">
                        <!-- Deep Insight - Lightbulb -->
                        <svg v-if="getToolIcon(log.details?.tool_name) === 'lightbulb'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                        </svg>
                        <!-- Panorama Search - Globe -->
                        <svg v-else-if="getToolIcon(log.details?.tool_name) === 'globe'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <circle cx="12" cy="12" r="10"></circle>
                          <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                        </svg>
                        <!-- Agent Interview - Users -->
                        <svg v-else-if="getToolIcon(log.details?.tool_name) === 'users'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                          <circle cx="9" cy="7" r="4"></circle>
                          <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                        </svg>
                        <!-- Quick Search - Zap -->
                        <svg v-else-if="getToolIcon(log.details?.tool_name) === 'zap'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                        </svg>
                        <!-- Graph Stats - Chart -->
                        <svg v-else-if="getToolIcon(log.details?.tool_name) === 'chart'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <line x1="18" y1="20" x2="18" y2="10"></line>
                          <line x1="12" y1="20" x2="12" y2="4"></line>
                          <line x1="6" y1="20" x2="6" y2="14"></line>
                        </svg>
                        <!-- Entity Query - Database -->
                        <svg v-else-if="getToolIcon(log.details?.tool_name) === 'database'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                        </svg>
                        <!-- Default - Tool -->
                        <svg v-else class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                        </svg>
                        </span>
                        <span class="tool-name">{{ getToolDisplayName(log.details?.tool_name) }}</span>
                      </div>
                      <div v-if="log.details?.parameters && expandedLogs.has(log.timestamp)" class="tool-params">
                        <pre>{{ formatParams(log.details.parameters) }}</pre>
                      </div>
                    </template>

                    <!-- Tool Result -->
                    <template v-if="log.action === 'tool_result'">
                      <div class="result-wrapper" :class="'result-' + log.details?.tool_name">
                        <!-- Hide result-meta for tools that show stats in their own header -->
                        <div v-if="!['interview_agents', 'insight_forge', 'panorama_search', 'quick_search'].includes(log.details?.tool_name)" class="result-meta">
                          <span class="result-tool">{{ getToolDisplayName(log.details?.tool_name) }}</span>
                          <span class="result-size">{{ formatResultSize(log.details?.result_length) }}</span>
                        </div>
                        
                        <!-- Structured Result Display -->
                        <div v-if="!showRawResult[log.timestamp]" class="result-structured">
                          <!-- Interview Agents - Special Display -->
                          <template v-if="log.details?.tool_name === 'interview_agents'">
                            <InterviewDisplay :result="parseInterview(log.details.result)" :result-length="log.details?.result_length" />
                          </template>
                          
                          <!-- Insight Forge -->
                          <template v-else-if="log.details?.tool_name === 'insight_forge'">
                            <InsightDisplay :result="parseInsightForge(log.details.result)" :result-length="log.details?.result_length" />
                          </template>
                          
                          <!-- Panorama Search -->
                          <template v-else-if="log.details?.tool_name === 'panorama_search'">
                            <PanoramaDisplay :result="parsePanorama(log.details.result)" :result-length="log.details?.result_length" />
                          </template>
                          
                          <!-- Quick Search -->
                          <template v-else-if="log.details?.tool_name === 'quick_search'">
                            <QuickSearchDisplay :result="parseQuickSearch(log.details.result)" :result-length="log.details?.result_length" />
                          </template>
                          
                          <!-- Default -->
                          <template v-else>
                            <pre class="raw-preview">{{ truncateText(log.details?.result, 300) }}</pre>
                          </template>
                        </div>
                        
                        <!-- Raw Result -->
                        <div v-else class="result-raw">
                          <pre>{{ log.details?.result }}</pre>
                        </div>
                      </div>
                    </template>

                    <!-- LLM Response -->
                    <template v-if="log.action === 'llm_response'">
                      <!-- «Sí» y «no» se distinguen por el relleno (gris suave frente a solo contorno), no por un tono -->
                      <div class="llm-meta">
                        <span class="meta-tag">{{ $t('step4.iteration', { n: log.details?.iteration }) }}</span>
                        <span class="meta-tag" :class="{ active: log.details?.has_tool_calls }">
                          {{ log.details?.has_tool_calls ? $t('ui.toolsYes') : $t('ui.toolsNo') }}
                        </span>
                        <span class="meta-tag" :class="{ active: log.details?.has_final_answer, 'final-answer': log.details?.has_final_answer }">
                          {{ log.details?.has_final_answer ? $t('step4.finalAnswerYes') : $t('step4.finalAnswerNo') }}
                        </span>
                      </div>
                      <!-- 当是最终答案时，显示特殊提示 -->
                      <div v-if="log.details?.has_final_answer" class="final-answer-hint">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>{{ $t('step4.sectionContentGenerated', { title: log.section_title }) }}</span>
                      </div>
                      <div v-if="expandedLogs.has(log.timestamp) && log.details?.response" class="llm-content">
                        <pre>{{ log.details.response }}</pre>
                      </div>
                    </template>

                    <!-- Report Complete -->
                    <template v-if="log.action === 'report_complete'">
                      <div class="complete-banner">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                          <polyline points="22 4 12 14.01 9 11.01"></polyline>
                        </svg>
                        <span>{{ $t('ui.reportGenerationComplete') }}</span>
                      </div>
                    </template>
                  </div>

                  <!-- Footer: Elapsed Time + Action Buttons -->
                  <div class="timeline-footer" v-if="log.elapsed_seconds || (log.action === 'tool_call' && log.details?.parameters) || log.action === 'tool_result' || (log.action === 'llm_response' && log.details?.response)">
                    <span v-if="log.elapsed_seconds" class="elapsed-badge">+{{ log.elapsed_seconds.toFixed(1) }}s</span>
                    <span v-else class="elapsed-placeholder"></span>
                    
                    <div class="footer-actions">
                      <!-- Tool Call: Show/Hide Params -->
                      <button v-if="log.action === 'tool_call' && log.details?.parameters" type="button" class="r4-btn action-btn" :aria-expanded="String(expandedLogs.has(log.timestamp))" @click.stop="toggleLogExpand(log)">
                        {{ expandedLogs.has(log.timestamp) ? $t('step4.hideParams') : $t('step4.showParams') }}
                      </button>

                      <!-- Tool Result: Raw/Structured View -->
                      <button v-if="log.action === 'tool_result'" type="button" class="r4-btn action-btn" @click.stop="toggleRawResult(log.timestamp, $event)">
                        {{ showRawResult[log.timestamp] ? $t('ui.structuredView') : $t('ui.rawOutput') }}
                      </button>

                      <!-- LLM Response: Show/Hide Response -->
                      <button v-if="log.action === 'llm_response' && log.details?.response" type="button" class="r4-btn action-btn" :aria-expanded="String(expandedLogs.has(log.timestamp))" @click.stop="toggleLogExpand(log)">
                        {{ expandedLogs.has(log.timestamp) ? $t('ui.hideResponse') : $t('ui.showResponse') }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </TransitionGroup>

          </div>
        </section>

        <!-- Estado vacío -->
        <div v-if="agentLogs.length === 0 && !isComplete" class="workflow-empty">
          <div class="empty-pulse" aria-hidden="true"></div>
          <span>{{ $t('step4.waitingAgentActivity') }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom Console Logs -->
    <div class="console-logs" :class="{ 'is-open': showTech }">
      <div class="log-header">
        <span class="log-title">{{ $t('ui.consoleOutput') }}</span>
        <span v-if="!showTech && lastLog" class="log-last">{{ lastLog }}</span>
        <button type="button" class="log-toggle" :aria-expanded="String(showTech)" @click="toggleTech">{{ showTech ? $t('ui.hideLog') : $t('ui.showLog') }}</button>
        <span class="log-id tech-only">{{ reportId || 'NO_REPORT' }}</span>
      </div>
      <div class="log-content" ref="logContent" v-show="showTech">
        <!-- Aviso y error se marcan por peso y filete, no por un tono nuevo: el texto ya dice WARNING / ERROR -->
        <div class="log-line" :class="getLogLevelClass(log)" v-for="(log, idx) in consoleLogs" :key="idx">
          <span class="log-msg">{{ log }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import SimulationEvidenceNotice from './SimulationEvidenceNotice.vue'
import { useTechDetails } from '../composables/useTechDetails'
import { ref, computed, watch, onMounted, onUnmounted, nextTick, h, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getAgentLog, getConsoleLog, getReport, generateReport } from '../api/report'
import ReportDownloads from './ReportDownloads.vue'
import { getPoblacionSimulacion } from '../api/simulation'

const router = useRouter()
const { t, locale } = useI18n()

// «12,3 mil caracteres» / «12.3K characters»: el tamaño del resultado en el idioma de la pantalla
const formatCharCount = (length, tr, loc) => {
  if (!length) return ''
  let n
  try {
    n = new Intl.NumberFormat(loc, { notation: 'compact', maximumFractionDigits: 1 }).format(length)
  } catch {
    n = String(length)
  }
  return tr('step4.charCount', { n })
}

const props = defineProps({
  reportId: String,
  simulationId: String,
  systemLogs: Array
})

const emit = defineEmits(['add-log', 'update-status'])

// Navigation
const goToInteraction = () => {
  if (props.reportId) {
    router.push({ name: 'Interaction', params: { reportId: props.reportId } })
  }
}

// State
const agentLogs = ref([])
const consoleLogs = ref([])
const { showTech, toggleTech } = useTechDetails()
const lastLog = computed(() => {
  const last = consoleLogs.value[consoleLogs.value.length - 1]
  return last ? String(last).replace(/^\[[^\]]*\]\s*(INFO|WARNING|ERROR|DEBUG)?:?\s*/, '') : ''
})
const agentLogLine = ref(0)
const consoleLogLine = ref(0)
const reportEvidence = ref(null)
const reportChecked = ref(false)
const reportOutline = ref(null)
const currentSectionIndex = ref(null)
const generatedSections = ref({})
const expandedContent = ref(new Set())
const expandedLogs = ref(new Set())
const collapsedSections = ref(new Set())
const isComplete = ref(false)
const reportError = ref(null)
const regenerating = ref(false)
const regenerateError = ref('')
const startTime = ref(null)
const leftPanel = ref(null)
const rightPanel = ref(null)
const logContent = ref(null)
const showRawResult = reactive({})

// Toggle functions
const toggleRawResult = (timestamp, event) => {
  // 保存按钮相对于视口的位置
  const button = event?.target
  const buttonRect = button?.getBoundingClientRect()
  const buttonTopBeforeToggle = buttonRect?.top
  
  // 切换状态
  showRawResult[timestamp] = !showRawResult[timestamp]
  
  // 等待 DOM 更新后，调整滚动位置以保持按钮在相同位置
  if (button && buttonTopBeforeToggle !== undefined && rightPanel.value) {
    nextTick(() => {
      const newButtonRect = button.getBoundingClientRect()
      const buttonTopAfterToggle = newButtonRect.top
      const scrollDelta = buttonTopAfterToggle - buttonTopBeforeToggle
      
      // 调整滚动位置
      rightPanel.value.scrollTop += scrollDelta
    })
  }
}

const toggleSectionContent = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(expandedContent.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  expandedContent.value = newSet
}

const toggleSectionCollapse = (idx) => {
  // 只有已完成的章节才能折叠
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const toggleLogExpand = (log) => {
  const newSet = new Set(expandedLogs.value)
  if (newSet.has(log.timestamp)) {
    newSet.delete(log.timestamp)
  } else {
    newSet.add(log.timestamp)
  }
  expandedLogs.value = newSet
}

const isLogCollapsed = (log) => {
  if (['tool_call', 'tool_result', 'llm_response'].includes(log.action)) {
    return !expandedLogs.value.has(log.timestamp)
  }
  return false
}

// Herramientas: nombre (clave i18n) e icono. Antes cada una llevaba un color propio (violeta, azul, verde,
// naranja, cian, rosa) fuera de la marca; ahora se distinguen por icono y nombre.
const toolConfig = {
  'insight_forge': {
    nameKey: 'ui.deepInsight',
    icon: 'lightbulb' // 灯泡图标 - 代表洞察
  },
  'panorama_search': {
    nameKey: 'step4.toolPanorama',
    icon: 'globe' // 地球图标 - 代表全景搜索
  },
  'interview_agents': {
    nameKey: 'ui.agentInterview',
    icon: 'users' // 用户图标 - 代表对话
  },
  'quick_search': {
    nameKey: 'step4.toolQuickSearch',
    icon: 'zap' // 闪电图标 - 代表快速
  },
  'get_graph_statistics': {
    nameKey: 'step4.toolGraphStats',
    icon: 'chart' // 图表图标 - 代表统计
  },
  'get_entities_by_type': {
    nameKey: 'step4.toolEntityQuery',
    icon: 'database' // 数据库图标 - 代表实体
  }
}

const getToolDisplayName = (toolName) => {
  const key = toolConfig[toolName]?.nameKey
  return key ? t(key) : toolName
}

const getToolIcon = (toolName) => {
  return toolConfig[toolName]?.icon || 'tool'
}

// Parse functions
const parseInsightForge = (text) => {
  const result = {
    query: '',
    simulationRequirement: '',
    stats: { facts: 0, entities: 0, relationships: 0 },
    subQueries: [],
    facts: [],
    entities: [],
    relations: []
  }
  
  try {
    // Extract analysis question (Spanish + legacy CN)
    const queryMatch = text.match(/(?:分析问题|Pregunta de análisis):\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract simulated scenario (los informes guardados antes de «ensayo» dicen «Escenario predicho»)
    const reqMatch = text.match(/(?:预测场景|Escenario predicho|Escenario simulado):\s*(.+?)(?:\n|$)/)
    if (reqMatch) result.simulationRequirement = reqMatch[1].trim()

    // Extract stats — match both Chinese and Spanish labels
    const factMatch = text.match(/(?:相关预测事实|Hechos predichos relacionados|Hechos predichos relevantes|Hechos simulados relevantes|Hechos relacionados):\s*(\d+)/)
    const entityMatch = text.match(/(?:涉及实体|Entidades involucradas|Entidades relacionadas):\s*(\d+)/)
    const relMatch = text.match(/(?:关系链|Cadenas de relación|Relaciones):\s*(\d+)/)
    if (factMatch) result.stats.facts = parseInt(factMatch[1])
    if (entityMatch) result.stats.entities = parseInt(entityMatch[1])
    if (relMatch) result.stats.relationships = parseInt(relMatch[1])

    // Extract sub-questions
    const subQSection = text.match(/### (?:分析的子问题|Subpreguntas analizadas)\n([\s\S]*?)(?=\n###|$)/)
    if (subQSection) {
      const lines = subQSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.subQueries = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }

    // Extract key facts
    const factsSection = text.match(/### (?:【关键事实】|\[Hechos clave\])[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => {
        const match = l.match(/^\d+\.\s*"?(.+?)"?\s*$/)
        return match ? match[1].replace(/^"|"$/g, '').trim() : l.replace(/^\d+\.\s*/, '').trim()
      }).filter(Boolean)
    }

    // Extract core entities
    const entitySection = text.match(/### (?:【核心实体】|\[Entidades principales\])\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const entityText = entitySection[1]
      const entityBlocks = entityText.split(/\n(?=- \*\*)/).filter(b => b.trim().startsWith('- **'))
      result.entities = entityBlocks.map(block => {
        const nameMatch = block.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        const summaryMatch = block.match(/(?:摘要|Resumen):\s*"?(.+?)"?(?:\n|$)/)
        const relatedMatch = block.match(/(?:相关事实|Hechos relacionados):\s*(\d+)/)
        return {
          name: nameMatch ? nameMatch[1].trim() : '',
          type: nameMatch ? nameMatch[2].trim() : '',
          summary: summaryMatch ? summaryMatch[1].trim() : '',
          relatedFactsCount: relatedMatch ? parseInt(relatedMatch[1]) : 0
        }
      }).filter(e => e.name)
    }

    // Extract relation chains
    const relSection = text.match(/### (?:【关系链】|\[Cadenas de relación\])\n([\s\S]*?)(?=\n###|$)/)
    if (relSection) {
      const lines = relSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.relations = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse insight_forge failed:', e)
  }
  
  return result
}

const parsePanorama = (text) => {
  const result = {
    query: '',
    stats: { nodes: 0, edges: 0, activeFacts: 0, historicalFacts: 0 },
    activeFacts: [],
    historicalFacts: [],
    entities: []
  }
  
  try {
    // Extract query
    const queryMatch = text.match(/(?:查询|Consulta):\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract stats
    const nodesMatch = text.match(/(?:总节点数|Total de nodos):\s*(\d+)/)
    const edgesMatch = text.match(/(?:总边数|Total de aristas):\s*(\d+)/)
    const activeMatch = text.match(/(?:当前有效事实|Hechos vigentes):\s*(\d+)/)
    const histMatch = text.match(/(?:历史\/过期事实|Hechos históricos\/expirados):\s*(\d+)/)
    if (nodesMatch) result.stats.nodes = parseInt(nodesMatch[1])
    if (edgesMatch) result.stats.edges = parseInt(edgesMatch[1])
    if (activeMatch) result.stats.activeFacts = parseInt(activeMatch[1])
    if (histMatch) result.stats.historicalFacts = parseInt(histMatch[1])

    // Extract active (current) facts
    const activeSection = text.match(/### (?:【当前有效事实】|\[Hechos vigentes\])[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (activeSection) {
      const lines = activeSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.activeFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // Extract historical / expired facts
    const histSection = text.match(/### (?:【历史\/过期事实】|\[Hechos históricos\/expirados\])[\s\S]*?\n([\s\S]*?)(?=\n###|$)/)
    if (histSection) {
      const lines = histSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.historicalFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // Extract involved entities
    const entitySection = text.match(/### (?:【涉及实体】|\[Entidades involucradas\])\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const lines = entitySection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.entities = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse panorama failed:', e)
  }
  
  return result
}

const parseInterview = (text) => {
  const result = {
    topic: '',
    agentCount: '',
    successCount: 0,
    totalCount: 0,
    selectionReason: '',
    interviews: [],
    summary: ''
  }
  
  try {
    // Extract interview topic (Spanish + legacy CN)
    const topicMatch = text.match(/\*\*(?:采访主题|Tema de la entrevista):\*\*\s*(.+?)(?:\n|$)/)
    if (topicMatch) result.topic = topicMatch[1].trim()

    // Extract interviewed agent count (e.g. "5 / 9 Agents")
    const countMatch = text.match(/\*\*(?:采访人数|Agentes entrevistados):\*\*\s*(\d+)\s*\/\s*(\d+)/)
    if (countMatch) {
      result.successCount = parseInt(countMatch[1])
      result.totalCount = parseInt(countMatch[2])
      result.agentCount = `${countMatch[1]} / ${countMatch[2]}`
    }

    // Extract selection reasoning
    const reasonMatch = text.match(/### (?:采访对象选择理由|Criterio de selección de entrevistados)\n([\s\S]*?)(?=\n---\n|\n### (?:采访实录|Transcripciones))/)
    if (reasonMatch) {
      result.selectionReason = reasonMatch[1].trim()
    }
    
    // 解析每个人的选择理由
    const parseIndividualReasons = (reasonText) => {
      const reasons = {}
      if (!reasonText) return reasons
      
      const lines = reasonText.split(/\n+/)
      let currentName = null
      let currentReason = []
      
      for (const line of lines) {
        let headerMatch = null
        let name = null
        let reasonStart = null
        
        // 格式1: 数字. **名字（index=X）**：理由
        // 例如: 1. **校友_345（index=1）**：作为武大校友...
        headerMatch = line.match(/^\d+\.\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
        if (headerMatch) {
          name = headerMatch[1].trim()
          reasonStart = headerMatch[2]
        }
        
        // 格式2: - 选择名字（index X）：理由
        // 例如: - 选择家长_601（index 0）：作为家长群体代表...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*选择([^（(]+)(?:[（(]index\s*=?\s*\d+[)）])?[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        // 格式3: - **名字（index X）**：理由
        // 例如: - **家长_601（index 0）**：作为家长群体代表...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        if (name) {
          // 保存上一个人的理由
          if (currentName && currentReason.length > 0) {
            reasons[currentName] = currentReason.join(' ').trim()
          }
          // 开始新的人
          currentName = name
          currentReason = reasonStart ? [reasonStart.trim()] : []
        } else if (currentName && line.trim() && !line.match(/^未选|^综上|^最终选择/)) {
          // 理由的续行（排除结尾总结段落）
          currentReason.push(line.trim())
        }
      }
      
      // 保存最后一个人的理由
      if (currentName && currentReason.length > 0) {
        reasons[currentName] = currentReason.join(' ').trim()
      }
      
      return reasons
    }
    
    const individualReasons = parseIndividualReasons(result.selectionReason)
    
    // Split per interview block (Spanish + legacy CN)
    const interviewBlocks = text.split(/#### (?:采访|Entrevista)\s*#\d+:/).slice(1)
    
    interviewBlocks.forEach((block, index) => {
      const interview = {
        num: index + 1,
        title: '',
        name: '',
        role: '',
        bio: '',
        selectionReason: '',
        questions: [],
        twitterAnswer: '',
        redditAnswer: '',
        quotes: []
      }
      
      // 提取标题（如 "学生"、"教育从业者" 等）
      const titleMatch = block.match(/^(.+?)\n/)
      if (titleMatch) interview.title = titleMatch[1].trim()
      
      // 提取姓名和角色
      const nameRoleMatch = block.match(/\*\*(.+?)\*\*\s*\((.+?)\)/)
      if (nameRoleMatch) {
        interview.name = nameRoleMatch[1].trim()
        interview.role = nameRoleMatch[2].trim()
        // 设置该人的选择理由
        interview.selectionReason = individualReasons[interview.name] || ''
      }
      
      // Extract bio (Spanish + legacy CN)
      const bioMatch = block.match(/_(?:简介|Perfil):\s*([\s\S]*?)_\n/)
      if (bioMatch) {
        interview.bio = bioMatch[1].trim().replace(/\.\.\.$/, '...')
      }

      // Extract questions list (Q/P)
      const qMatch = block.match(/\*\*(?:Q|P):\*\*\s*([\s\S]*?)(?=\n\n\*\*(?:A|R):\*\*|\*\*(?:A|R):\*\*)/)
      if (qMatch) {
        const qText = qMatch[1].trim()
        // 按数字编号分割问题
        const questions = qText.split(/\n\d+\.\s+/).filter(q => q.trim())
        if (questions.length > 0) {
          // 如果第一个问题前面有"1."，需要特殊处理
          const firstQ = qText.match(/^1\.\s+(.+)/)
          if (firstQ) {
            interview.questions = [firstQ[1].trim(), ...questions.slice(1).map(q => q.trim())]
          } else {
            interview.questions = questions.map(q => q.trim())
          }
        }
      }
      
      // Extract answer — separated by platform (Spanish + legacy CN)
      const answerMatch = block.match(/\*\*(?:A|R):\*\*\s*([\s\S]*?)(?=\*\*(?:关键引言|Citas clave)|$)/)
      if (answerMatch) {
        const answerText = answerMatch[1].trim()

        // Separate Twitter and Reddit answers
        const twitterMatch = answerText.match(/(?:【Twitter平台回答】|\[Respuesta de Twitter\])\n?([\s\S]*?)(?=(?:【Reddit平台回答】|\[Respuesta de Reddit\])|$)/)
        const redditMatch = answerText.match(/(?:【Reddit平台回答】|\[Respuesta de Reddit\])\n?([\s\S]*?)$/)

        if (twitterMatch) {
          interview.twitterAnswer = twitterMatch[1].trim()
        }
        if (redditMatch) {
          interview.redditAnswer = redditMatch[1].trim()
        }

        // Platform fallback (legacy: only one platform marked)
        const noReplyTexts = ['（该平台未获得回复）', '(Sin respuesta en esta plataforma)']
        if (!twitterMatch && redditMatch) {
          if (interview.redditAnswer && !noReplyTexts.includes(interview.redditAnswer)) {
            interview.twitterAnswer = interview.redditAnswer
          }
        } else if (twitterMatch && !redditMatch) {
          if (interview.twitterAnswer && !noReplyTexts.includes(interview.twitterAnswer)) {
            interview.redditAnswer = interview.twitterAnswer
          }
        } else if (!twitterMatch && !redditMatch) {
          interview.twitterAnswer = answerText
        }
      }

      // Extract key quotes (Spanish + legacy CN)
      const quotesMatch = block.match(/\*\*(?:关键引言|Citas clave):\*\*\n([\s\S]*?)(?=\n---|\n####|$)/)
      if (quotesMatch) {
        const quotesText = quotesMatch[1]
        // 优先匹配 > "text" 格式
        let quoteMatches = quotesText.match(/> "([^"]+)"/g)
        // 回退：匹配 > "text" 或 > \u201Ctext\u201D（中文引号）
        if (!quoteMatches) {
          quoteMatches = quotesText.match(/> [\u201C""]([^\u201D""]+)[\u201D""]/g)
        }
        if (quoteMatches) {
          interview.quotes = quoteMatches
            .map(q => q.replace(/^> [\u201C""]|[\u201D""]$/g, '').trim())
            .filter(q => q)
        }
      }
      
      if (interview.name || interview.title) {
        result.interviews.push(interview)
      }
    })
    
    // Extract interview summary (Spanish + legacy CN)
    const summaryMatch = text.match(/### (?:采访摘要与核心观点|Resumen y puntos clave)\n([\s\S]*?)$/)
    if (summaryMatch) {
      result.summary = summaryMatch[1].trim()
    }
  } catch (e) {
    console.warn('Parse interview failed:', e)
  }
  
  return result
}

const parseQuickSearch = (text) => {
  const result = {
    query: '',
    count: 0,
    facts: [],
    edges: [],
    nodes: []
  }
  
  try {
    // Extract search query (Spanish + legacy CN)
    const queryMatch = text.match(/(?:搜索查询|Consulta):\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract result count
    const countMatch = text.match(/(?:找到\s*(\d+)\s*条|Se encontraron\s*(\d+)\s*resultados)/)
    if (countMatch) result.count = parseInt(countMatch[1] || countMatch[2])

    // Extract related facts
    const factsSection = text.match(/### (?:相关事实|Hechos relevantes):\n([\s\S]*)$/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }

    // Extract related edges
    const edgesSection = text.match(/### (?:相关边|Relaciones relacionadas|Relaciones):\n([\s\S]*?)(?=\n###|$)/)
    if (edgesSection) {
      const lines = edgesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.edges = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }

    // Extract related nodes
    const nodesSection = text.match(/### (?:相关节点|Nodos relacionados):\n([\s\S]*?)(?=\n###|$)/)
    if (nodesSection) {
      const lines = nodesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.nodes = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        const simpleMatch = l.match(/^-\s*(.+)$/)
        if (simpleMatch) return { name: simpleMatch[1].trim(), type: '' }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse quick_search failed:', e)
  }
  
  return result
}

// ========== Sub Components ==========

// Piezas comunes de las cuatro vistas de resultado (análisis, panorámica, entrevista, búsqueda rápida).
// Separadores «/» y «·»: decorativos, fuera del árbol de accesibilidad (y con el mismo gris legible que las etiquetas).
const statDivider = (ch) => h('span', { class: 'stat-divider', 'aria-hidden': 'true' }, ch)
const statItem = (value, label) => h('span', { class: 'stat-item' }, [
  h('span', { class: 'stat-value' }, value),
  h('span', { class: 'stat-label' }, label)
])
// Pestaña: la activa se marca con texto tinta en negrita y un filete inferior (forma), no con un color propio
const tabButton = (extraClass, label, active, onClick) => h('button', {
  type: 'button',
  class: ['r4-tab', extraClass, { active }],
  'aria-pressed': String(active),
  onClick
}, [h('span', { class: 'tab-label' }, label)])
const expandButton = (expanded, labelCollapsed, labelExpanded, onClick) => h('button', {
  type: 'button',
  class: 'r4-btn expand-btn',
  'aria-expanded': String(expanded),
  onClick
}, expanded ? labelExpanded : labelCollapsed)

// Insight Display Component - Enhanced with full data rendering (Interview-like style)
const InsightDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t, locale } = useI18n()
    const activeTab = ref('facts') // 'facts', 'entities', 'relations', 'subqueries'
    const expandedFacts = ref(false)
    const expandedEntities = ref(false)
    const expandedRelations = ref(false)
    const INITIAL_SHOW_COUNT = 5

    return () => h('div', { class: 'insight-display' }, [
      // Header Section - like interview header
      h('div', { class: 'insight-header result-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, t('ui.deepInsight')),
          h('div', { class: 'header-stats' }, [
            statItem(props.result.stats.facts || props.result.facts.length, t('ui.facts')),
            statDivider('/'),
            statItem(props.result.stats.entities || props.result.entities.length, t('ui.entities')),
            statDivider('/'),
            statItem(props.result.stats.relationships || props.result.relations.length, t('ui.relations')),
            props.resultLength && statDivider('·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatCharCount(props.resultLength, t, locale.value))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query),
        props.result.simulationRequirement && h('div', { class: 'header-scenario' }, [
          h('span', { class: 'scenario-label' }, t('step4.scenarioLabel')),
          h('span', { class: 'scenario-text' }, props.result.simulationRequirement)
        ])
      ]),

      // Tab Navigation
      h('div', { class: 'insight-tabs result-tabs' }, [
        tabButton('insight-tab', t('step4.tabKeyFacts', { count: props.result.facts.length }), activeTab.value === 'facts', () => { activeTab.value = 'facts' }),
        tabButton('insight-tab', t('step4.tabCoreEntities', { count: props.result.entities.length }), activeTab.value === 'entities', () => { activeTab.value = 'entities' }),
        tabButton('insight-tab', t('step4.tabRelationChains', { count: props.result.relations.length }), activeTab.value === 'relations', () => { activeTab.value = 'relations' }),
        props.result.subQueries.length > 0 && tabButton('insight-tab', t('step4.tabSubQueries', { count: props.result.subQueries.length }), activeTab.value === 'subqueries', () => { activeTab.value = 'subqueries' })
      ]),

      // Tab Content
      h('div', { class: 'insight-content result-content' }, [
        // Facts Tab
        activeTab.value === 'facts' && props.result.facts.length > 0 && h('div', { class: 'facts-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelKeyFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.facts.length }))
          ]),
          h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ),
          props.result.facts.length > INITIAL_SHOW_COUNT && expandButton(expandedFacts.value, t('step4.expandAll', { count: props.result.facts.length }), t('step4.collapse'), () => { expandedFacts.value = !expandedFacts.value })
        ]),

        // Entities Tab
        activeTab.value === 'entities' && props.result.entities.length > 0 && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelCoreEntities')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.entities.length }))
          ]),
          h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 12)).map((entity, i) =>
              h('div', { class: 'entity-tag', key: i, title: entity.summary || '' }, [
                h('span', { class: 'entity-name' }, entity.name),
                h('span', { class: 'entity-type' }, entity.type),
                entity.relatedFactsCount > 0 && h('span', { class: 'entity-fact-count' }, t('step4.factCount', { count: entity.relatedFactsCount }))
              ])
            )
          ),
          props.result.entities.length > 12 && expandButton(expandedEntities.value, t('step4.expandAllEntities', { count: props.result.entities.length }), t('step4.collapse'), () => { expandedEntities.value = !expandedEntities.value })
        ]),

        // Relations Tab
        activeTab.value === 'relations' && props.result.relations.length > 0 && h('div', { class: 'relations-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelationChains')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.relations.length }))
          ]),
          h('div', { class: 'relations-list' },
            (expandedRelations.value ? props.result.relations : props.result.relations.slice(0, INITIAL_SHOW_COUNT)).map((rel, i) =>
              h('div', { class: 'relation-item', key: i }, [
                h('span', { class: 'rel-source' }, rel.source),
                h('span', { class: 'rel-arrow' }, [
                  h('span', { class: 'rel-line', 'aria-hidden': 'true' }),
                  h('span', { class: 'rel-label' }, rel.relation),
                  h('span', { class: 'rel-line', 'aria-hidden': 'true' })
                ]),
                h('span', { class: 'rel-target' }, rel.target)
              ])
            )
          ),
          props.result.relations.length > INITIAL_SHOW_COUNT && expandButton(expandedRelations.value, t('step4.expandAll', { count: props.result.relations.length }), t('step4.collapse'), () => { expandedRelations.value = !expandedRelations.value })
        ]),

        // Sub-queries Tab
        activeTab.value === 'subqueries' && props.result.subQueries.length > 0 && h('div', { class: 'subqueries-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelSubQueries')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.subQueries.length }))
          ]),
          h('div', { class: 'subqueries-list' },
            props.result.subQueries.map((sq, i) =>
              h('div', { class: 'subquery-item', key: i }, [
                h('span', { class: 'subquery-number' }, `Q${i + 1}`),
                h('div', { class: 'subquery-text' }, sq)
              ])
            )
          )
        ]),

        // Empty state
        activeTab.value === 'facts' && props.result.facts.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyKeyFacts')),
        activeTab.value === 'entities' && props.result.entities.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyCoreEntities')),
        activeTab.value === 'relations' && props.result.relations.length === 0 && h('div', { class: 'empty-state' }, t('step4.emptyRelationChains'))
      ])
    ])
  }
}

// Panorama Display Component - Enhanced with Active/Historical tabs
const PanoramaDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t, locale } = useI18n()
    const activeTab = ref('active') // 'active', 'historical', 'entities'
    const expandedActive = ref(false)
    const expandedHistorical = ref(false)
    const expandedEntities = ref(false)
    const INITIAL_SHOW_COUNT = 5

    return () => h('div', { class: 'panorama-display' }, [
      // Header Section
      h('div', { class: 'panorama-header result-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, t('step4.toolPanorama')),
          h('div', { class: 'header-stats' }, [
            statItem(props.result.stats.nodes, t('step4.statNodes')),
            statDivider('/'),
            statItem(props.result.stats.edges, t('step4.statEdges')),
            props.resultLength && statDivider('·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatCharCount(props.resultLength, t, locale.value))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query)
      ]),

      // Tab Navigation
      h('div', { class: 'panorama-tabs result-tabs' }, [
        tabButton('panorama-tab', t('step4.tabActiveFacts', { count: props.result.activeFacts.length }), activeTab.value === 'active', () => { activeTab.value = 'active' }),
        tabButton('panorama-tab', t('step4.tabHistoricalFacts', { count: props.result.historicalFacts.length }), activeTab.value === 'historical', () => { activeTab.value = 'historical' }),
        tabButton('panorama-tab', t('step4.tabEntities', { count: props.result.entities.length }), activeTab.value === 'entities', () => { activeTab.value = 'entities' })
      ]),

      // Tab Content
      h('div', { class: 'panorama-content result-content' }, [
        // Active Facts Tab
        activeTab.value === 'active' && h('div', { class: 'facts-panel active-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelActiveFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.activeFacts.length }))
          ]),
          props.result.activeFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedActive.value ? props.result.activeFacts : props.result.activeFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item active', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyActiveFacts')),
          props.result.activeFacts.length > INITIAL_SHOW_COUNT && expandButton(expandedActive.value, t('step4.expandAll', { count: props.result.activeFacts.length }), t('step4.collapse'), () => { expandedActive.value = !expandedActive.value })
        ]),

        // Historical Facts Tab: el hecho caducado lleva número en gris oscuro y contorno discontinuo (luminosidad y forma)
        activeTab.value === 'historical' && h('div', { class: 'facts-panel historical-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelHistoricalFacts')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.historicalFacts.length }))
          ]),
          props.result.historicalFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedHistorical.value ? props.result.historicalFacts : props.result.historicalFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item historical', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, [
                  // 尝试提取时间信息 [time - time]
                  (() => {
                    const timeMatch = fact.match(/^\[(.+?)\]\s*(.*)$/)
                    if (timeMatch) {
                      return [
                        h('span', { class: 'fact-time' }, timeMatch[1]),
                        h('span', { class: 'fact-text' }, timeMatch[2])
                      ]
                    }
                    return h('span', { class: 'fact-text' }, fact)
                  })()
                ])
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyHistoricalFacts')),
          props.result.historicalFacts.length > INITIAL_SHOW_COUNT && expandButton(expandedHistorical.value, t('step4.expandAll', { count: props.result.historicalFacts.length }), t('step4.collapse'), () => { expandedHistorical.value = !expandedHistorical.value })
        ]),

        // Entities Tab
        activeTab.value === 'entities' && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelEntities')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.entities.length }))
          ]),
          props.result.entities.length > 0 ? h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 8)).map((entity, i) =>
              h('div', { class: 'entity-tag', key: i }, [
                h('span', { class: 'entity-name' }, entity.name),
                entity.type && h('span', { class: 'entity-type' }, entity.type)
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptyEntities')),
          props.result.entities.length > 8 && expandButton(expandedEntities.value, t('step4.expandAllEntities', { count: props.result.entities.length }), t('step4.collapse'), () => { expandedEntities.value = !expandedEntities.value })
        ])
      ])
    ])
  }
}

// Interview Display Component - Conversation Style (Q&A Format)
const InterviewDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t, locale } = useI18n()

    // Clean quote text - remove leading list numbers to avoid double numbering
    const cleanQuoteText = (text) => {
      if (!text) return ''
      // Remove leading patterns like "1. ", "2. ", "1、", "（1）", "(1)" etc.
      return text.replace(/^\s*\d+[\.\、\)）]\s*/, '').trim()
    }

    const activeIndex = ref(0)
    const expandedAnswers = ref(new Set())
    // 为每个问题-回答对维护独立的平台选择状态
    const platformTabs = reactive({}) // { 'agentIdx-qIdx': 'twitter' | 'reddit' }

    // 获取某个问题的当前平台选择
    const getPlatformTab = (agentIdx, qIdx) => {
      const key = `${agentIdx}-${qIdx}`
      return platformTabs[key] || 'twitter'
    }

    // 设置某个问题的平台选择
    const setPlatformTab = (agentIdx, qIdx, platform) => {
      const key = `${agentIdx}-${qIdx}`
      platformTabs[key] = platform
    }

    const toggleAnswer = (key) => {
      const newSet = new Set(expandedAnswers.value)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      expandedAnswers.value = newSet
    }

    const formatAnswer = (text, expanded) => {
      if (!text) return ''
      if (expanded || text.length <= 400) return text
      return text.substring(0, 400) + '...'
    }

    // Check whether the text is a platform-placeholder (no-reply) marker
    const isPlaceholderText = (text) => {
      if (!text) return true
      const t = text.trim()
      return (
        t === '（该平台未获得回复）' ||
        t === '(该平台未获得回复)' ||
        t === '[无回复]' ||
        t === '(Sin respuesta en esta plataforma)' ||
        t === '[Sin respuesta]'
      )
    }

    // Split answer by question numbering
    const splitAnswerByQuestions = (answerText, questionCount) => {
      if (!answerText || questionCount <= 0) return [answerText]
      if (isPlaceholderText(answerText)) return ['']

      // Supports multiple numbering formats:
      // 1. "问题X:" or "Pregunta X:" / "Pregunta X：" (header format)
      // 2. "1. " or "\n1. " (numeric fallback)
      let matches = []
      let match

      // First try header format for both CN and ES
      const headerPattern = /(?:^|[\r\n]+)(?:问题|Pregunta)\s*(\d+)[：:]\s*/g
      while ((match = headerPattern.exec(answerText)) !== null) {
        matches.push({
          num: parseInt(match[1]),
          index: match.index,
          fullMatch: match[0]
        })
      }

      // 如果没匹配到，回退到 "数字." 格式
      if (matches.length === 0) {
        const numPattern = /(?:^|[\r\n]+)(\d+)\.\s+/g
        while ((match = numPattern.exec(answerText)) !== null) {
          matches.push({
            num: parseInt(match[1]),
            index: match.index,
            fullMatch: match[0]
          })
        }
      }

      // If no numbering matches or only one matches, return whole answer
      if (matches.length <= 1) {
        const cleaned = answerText
          .replace(/^(?:问题|Pregunta)\s*\d+[：:]\s*/, '')
          .replace(/^\d+\.\s+/, '')
          .trim()
        return [cleaned || answerText]
      }

      // 按编号提取各部分
      const parts = []
      for (let i = 0; i < matches.length; i++) {
        const current = matches[i]
        const next = matches[i + 1]

        const startIdx = current.index + current.fullMatch.length
        const endIdx = next ? next.index : answerText.length

        let part = answerText.substring(startIdx, endIdx).trim()
        part = part.replace(/[\r\n]+$/, '').trim()
        parts.push(part)
      }

      if (parts.length > 0 && parts.some(p => p)) {
        return parts
      }

      return [answerText]
    }

    // 获取某个问题对应的回答
    const getAnswerForQuestion = (interview, qIdx, platform) => {
      const answer = platform === 'twitter' ? interview.twitterAnswer : (interview.redditAnswer || interview.twitterAnswer)
      if (!answer || isPlaceholderText(answer)) return answer || ''

      const questionCount = interview.questions?.length || 1
      const answers = splitAnswerByQuestions(answer, questionCount)

      // 分割成功且索引有效
      if (answers.length > 1 && qIdx < answers.length) {
        return answers[qIdx] || ''
      }

      // 分割失败：第一个问题返回完整回答，其余返回空
      return qIdx === 0 ? answer : ''
    }

    // 检查某个问题是否有双平台回答（过滤占位文本）
    const hasMultiplePlatforms = (interview, qIdx) => {
      if (!interview.twitterAnswer || !interview.redditAnswer) return false
      const twitterAnswer = getAnswerForQuestion(interview, qIdx, 'twitter')
      const redditAnswer = getAnswerForQuestion(interview, qIdx, 'reddit')
      // 两个平台都有真实回答（非占位文本）且内容不同
      return !isPlaceholderText(twitterAnswer) && !isPlaceholderText(redditAnswer) && twitterAnswer !== redditAnswer
    }

    // Botón de plataforma: misma firma que las pestañas (la elegida, en tinta y con filete)
    const platformButton = (agentIdx, qIdx, platform, active, label, iconChildren) => h('button', {
      type: 'button',
      class: ['r4-tab', 'platform-btn', { active }],
      'aria-pressed': String(active),
      onClick: (e) => { e.stopPropagation(); setPlatformTab(agentIdx, qIdx, platform) }
    }, [
      h('svg', { class: 'platform-icon', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'aria-hidden': 'true' }, iconChildren),
      h('span', {}, label)
    ])

    return () => h('div', { class: 'interview-display' }, [
      // Header Section
      h('div', { class: 'interview-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, t('ui.agentInterview')),
          h('div', { class: 'header-stats' }, [
            statItem(props.result.successCount || props.result.interviews.length, t('step4.statInterviewed')),
            props.result.totalCount > 0 && statDivider('/'),
            props.result.totalCount > 0 && statItem(props.result.totalCount, t('step4.statTotal')),
            props.resultLength && statDivider('·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatCharCount(props.resultLength, t, locale.value))
          ])
        ]),
        props.result.topic && h('div', { class: 'header-topic' }, props.result.topic)
      ]),

      // Agent Selector Tabs
      props.result.interviews.length > 0 && h('div', { class: 'agent-tabs' },
        props.result.interviews.map((interview, i) => h('button', {
          type: 'button',
          class: ['r4-tab', 'agent-tab', { active: activeIndex.value === i }],
          'aria-pressed': String(activeIndex.value === i),
          title: interview.name || interview.title || '',
          key: i,
          onClick: () => { activeIndex.value = i }
        }, [
          h('span', { class: 'tab-avatar', 'aria-hidden': 'true' }, interview.name ? interview.name.charAt(0) : (i + 1)),
          h('span', { class: 'tab-name' }, interview.title || interview.name || t('step4.agentN', { n: i + 1 }))
        ]))
      ),

      // Active Interview Detail
      props.result.interviews.length > 0 && h('div', { class: 'interview-detail' }, [
        // Agent Profile Card
        h('div', { class: 'agent-profile' }, [
          h('div', { class: 'profile-avatar', 'aria-hidden': 'true' }, props.result.interviews[activeIndex.value]?.name?.charAt(0) || 'A'),
          h('div', { class: 'profile-info' }, [
            h('div', { class: 'profile-name' }, props.result.interviews[activeIndex.value]?.name || t('step4.agent')),
            h('div', { class: 'profile-role' }, props.result.interviews[activeIndex.value]?.role || ''),
            props.result.interviews[activeIndex.value]?.bio && h('div', { class: 'profile-bio' }, props.result.interviews[activeIndex.value].bio)
          ])
        ]),

        // Selection Reason - 选择理由
        props.result.interviews[activeIndex.value]?.selectionReason && h('div', { class: 'selection-reason' }, [
          h('div', { class: 'reason-label' }, t('step4.selectionReason')),
          h('div', { class: 'reason-content' }, props.result.interviews[activeIndex.value].selectionReason)
        ]),

        // Q&A Conversation Thread - 一问一答样式
        h('div', { class: 'qa-thread' },
          (props.result.interviews[activeIndex.value]?.questions?.length > 0
            ? props.result.interviews[activeIndex.value].questions
            : [props.result.interviews[activeIndex.value]?.question || t('step4.noQuestion')]
          ).map((question, qIdx) => {
            const interview = props.result.interviews[activeIndex.value]
            const currentPlatform = getPlatformTab(activeIndex.value, qIdx)
            const answerText = getAnswerForQuestion(interview, qIdx, currentPlatform)
            const hasDualPlatform = hasMultiplePlatforms(interview, qIdx)
            const expandKey = `${activeIndex.value}-${qIdx}`
            const isExpanded = expandedAnswers.value.has(expandKey)
            const isPlaceholder = isPlaceholderText(answerText)

            return h('div', { class: 'qa-pair', key: qIdx }, [
              // Question Block: «Q» en contorno, «A» rellena en tinta (forma y luminosidad, no color)
              h('div', { class: 'qa-question' }, [
                h('div', { class: 'qa-badge q-badge' }, `Q${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-sender' }, t('step4.interviewer')),
                  h('div', { class: 'qa-text' }, question)
                ])
              ]),

              // Answer Block
              answerText && h('div', { class: ['qa-answer', { 'answer-placeholder': isPlaceholder }] }, [
                h('div', { class: 'qa-badge a-badge' }, `A${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-answer-header' }, [
                    h('div', { class: 'qa-sender' }, interview?.name || t('step4.agent')),
                    // 双平台切换按钮（仅在有真实双平台回答时显示）
                    hasDualPlatform && h('div', { class: 'platform-switch' }, [
                      platformButton(activeIndex.value, qIdx, 'twitter', currentPlatform === 'twitter', t('step4.world1'), [
                        h('circle', { cx: '12', cy: '12', r: '10' }),
                        h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
                        h('path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' })
                      ]),
                      platformButton(activeIndex.value, qIdx, 'reddit', currentPlatform === 'reddit', t('step4.world2'), [
                        h('path', { d: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z' })
                      ])
                    ])
                  ]),
                  h('div', {
                    class: ['qa-text', 'answer-text', { 'placeholder-text': isPlaceholder }],
                    innerHTML: isPlaceholder
                      ? answerText
                      : formatAnswer(answerText, isExpanded)
                          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br>')
                  }),
                  // Expand/Collapse Button（占位文本不显示）
                  !isPlaceholder && answerText.length > 400 && h('button', {
                    type: 'button',
                    class: 'r4-link expand-answer-btn',
                    'aria-expanded': String(isExpanded),
                    onClick: () => toggleAnswer(expandKey)
                  }, isExpanded ? t('step4.showLess') : t('step4.showMore'))
                ])
              ])
            ])
          })
        ),

        // Key Quotes Section
        props.result.interviews[activeIndex.value]?.quotes?.length > 0 && h('div', { class: 'quotes-section' }, [
          h('div', { class: 'quotes-header' }, t('step4.keyQuotes')),
          h('div', { class: 'quotes-list' },
            props.result.interviews[activeIndex.value].quotes.slice(0, 3).map((quote, qi) => {
              const cleanedQuote = cleanQuoteText(quote)
              const displayQuote = cleanedQuote.length > 200 ? cleanedQuote.substring(0, 200) + '...' : cleanedQuote
              return h('blockquote', {
                key: qi,
                class: 'quote-item',
                innerHTML: renderMarkdown(displayQuote)
              })
            })
          )
        ])
      ]),

      // Summary Section (Collapsible)
      props.result.summary && h('div', { class: 'summary-section' }, [
        h('div', { class: 'summary-header' }, t('ui.interviewSummary')),
        h('div', {
          class: 'summary-content',
          innerHTML: renderMarkdown(props.result.summary.length > 500 ? props.result.summary.substring(0, 500) + '...' : props.result.summary)
        })
      ])
    ])
  }
}

// Quick Search Display Component - Enhanced with full data rendering
const QuickSearchDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const { t, locale } = useI18n()
    const activeTab = ref('facts') // 'facts', 'edges', 'nodes'
    const expandedFacts = ref(false)
    const INITIAL_SHOW_COUNT = 5

    // Check if there are edges or nodes to show tabs
    const hasEdges = computed(() => props.result.edges && props.result.edges.length > 0)
    const hasNodes = computed(() => props.result.nodes && props.result.nodes.length > 0)
    const showTabs = computed(() => hasEdges.value || hasNodes.value)

    return () => h('div', { class: 'quick-search-display' }, [
      // Header Section
      h('div', { class: 'quicksearch-header result-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, t('step4.toolQuickSearch')),
          h('div', { class: 'header-stats' }, [
            statItem(props.result.count || props.result.facts.length, t('step4.statResults')),
            props.resultLength && statDivider('·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatCharCount(props.resultLength, t, locale.value))
          ])
        ]),
        props.result.query && h('div', { class: 'header-query' }, [
          h('span', { class: 'query-label' }, t('step4.searchLabel')),
          h('span', { class: 'query-text' }, props.result.query)
        ])
      ]),

      // Tab Navigation (only show if there are edges or nodes)
      showTabs.value && h('div', { class: 'quicksearch-tabs result-tabs' }, [
        tabButton('quicksearch-tab', t('step4.tabFacts', { count: props.result.facts.length }), activeTab.value === 'facts', () => { activeTab.value = 'facts' }),
        hasEdges.value && tabButton('quicksearch-tab', t('step4.tabEdges', { count: props.result.edges.length }), activeTab.value === 'edges', () => { activeTab.value = 'edges' }),
        hasNodes.value && tabButton('quicksearch-tab', t('step4.tabNodes', { count: props.result.nodes.length }), activeTab.value === 'nodes', () => { activeTab.value = 'nodes' })
      ]),

      // Content Area
      h('div', { class: ['quicksearch-content', 'result-content', { 'no-tabs': !showTabs.value }] }, [
        // Facts (always show if no tabs, or when facts tab is active)
        ((!showTabs.value) || activeTab.value === 'facts') && h('div', { class: 'facts-panel' }, [
          !showTabs.value && h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelSearchResults')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.facts.length }))
          ]),
          props.result.facts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) =>
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, t('step4.emptySearchResults')),
          props.result.facts.length > INITIAL_SHOW_COUNT && expandButton(expandedFacts.value, t('step4.expandAll', { count: props.result.facts.length }), t('step4.collapse'), () => { expandedFacts.value = !expandedFacts.value })
        ]),

        // Edges Tab
        activeTab.value === 'edges' && hasEdges.value && h('div', { class: 'edges-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelatedEdges')),
            h('span', { class: 'panel-count' }, t('step4.totalCount', { count: props.result.edges.length }))
          ]),
          h('div', { class: 'edges-list' },
            props.result.edges.map((edge, i) =>
              h('div', { class: 'edge-item', key: i }, [
                h('span', { class: 'edge-source' }, edge.source),
                h('span', { class: 'edge-arrow' }, [
                  h('span', { class: 'edge-line', 'aria-hidden': 'true' }),
                  h('span', { class: 'edge-label' }, edge.relation),
                  h('span', { class: 'edge-line', 'aria-hidden': 'true' })
                ]),
                h('span', { class: 'edge-target' }, edge.target)
              ])
            )
          )
        ]),

        // Nodes Tab
        activeTab.value === 'nodes' && hasNodes.value && h('div', { class: 'nodes-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, t('step4.panelRelatedNodes')),
            h('span', { class: 'panel-count' }, t('step4.totalEntityCount', { count: props.result.nodes.length }))
          ]),
          h('div', { class: 'nodes-grid' },
            props.result.nodes.map((node, i) =>
              h('div', { class: 'node-tag', key: i }, [
                h('span', { class: 'node-name' }, node.name),
                node.type && h('span', { class: 'node-type' }, node.type)
              ])
            )
          )
        ])
      ])
    ])
  }
}

// Computed
const statusClass = computed(() => {
  if (reportError.value) return 'failed'
  if (isComplete.value) return 'completed'
  if (agentLogs.value.length > 0) return 'processing'
  return 'pending'
})

const statusText = computed(() => {
  if (reportError.value) return t('step4.statusFailed')
  if (isComplete.value) return t('step4.statusCompleted')
  if (agentLogs.value.length > 0) return t('step4.statusGenerating')
  return t('step4.statusWaiting')
})

const totalSections = computed(() => {
  return reportOutline.value?.sections?.length || 0
})

const completedSections = computed(() => {
  return Object.keys(generatedSections.value).length
})

const progressPercent = computed(() => {
  if (totalSections.value === 0) return 0
  return Math.round((completedSections.value / totalSections.value) * 100)
})

const totalToolCalls = computed(() => {
  return agentLogs.value.filter(l => l.action === 'tool_call').length
})

const formatElapsedTime = computed(() => {
  if (!startTime.value) return '0s'
  const lastLog = agentLogs.value[agentLogs.value.length - 1]
  const elapsed = lastLog?.elapsed_seconds || 0
  if (elapsed < 60) return `${Math.round(elapsed)}s`
  const mins = Math.floor(elapsed / 60)
  const secs = Math.round(elapsed % 60)
  return `${mins}m ${secs}s`
})

const displayLogs = computed(() => {
  return agentLogs.value
})

// Workflow steps overview (status-based, no nested cards)
const activeSectionIndex = computed(() => {
  if (isComplete.value) return null
  if (currentSectionIndex.value) return currentSectionIndex.value
  if (totalSections.value > 0 && completedSections.value < totalSections.value) return completedSections.value + 1
  return null
})

const isPlanningDone = computed(() => {
  return !!reportOutline.value?.sections?.length || agentLogs.value.some(l => l.action === 'planning_complete')
})

const isPlanningStarted = computed(() => {
  return agentLogs.value.some(l => l.action === 'planning_start' || l.action === 'report_start')
})

const isFinalizing = computed(() => {
  return !isComplete.value && isPlanningDone.value && totalSections.value > 0 && completedSections.value >= totalSections.value
})

// 当前活跃的步骤（用于顶部显示）
const activeStep = computed(() => {
  const steps = workflowSteps.value
  // 找到当前 active 的步骤
  const active = steps.find(s => s.status === 'active')
  if (active) return active
  
  // 如果没有 active，返回最后一个 done 的步骤
  const doneSteps = steps.filter(s => s.status === 'done')
  if (doneSteps.length > 0) return doneSteps[doneSteps.length - 1]
  
  // 否则返回第一个步骤
  return steps[0] || { noLabel: '--', title: t('step4.waitingToStart'), status: 'todo', meta: '' }
})

const workflowSteps = computed(() => {
  const steps = []

  // Planning / Outline
  const planningStatus = isPlanningDone.value ? 'done' : (isPlanningStarted.value ? 'active' : 'todo')
  steps.push({
    key: 'planning',
    noLabel: 'PL',
    title: t('ui.planningOutline'),
    status: planningStatus,
    meta: planningStatus === 'active' ? t('ui.status.processing') : ''
  })

  // Sections (if outline exists)
  const sections = reportOutline.value?.sections || []
  sections.forEach((section, i) => {
    const idx = i + 1
    const status = (isComplete.value || !!generatedSections.value[idx])
      ? 'done'
      : (activeSectionIndex.value === idx ? 'active' : 'todo')

    steps.push({
      key: `section-${idx}`,
      noLabel: String(idx).padStart(2, '0'),
      title: section.title,
      status,
      meta: status === 'active' ? t('ui.status.processing') : ''
    })
  })

  // Complete
  const completeStatus = isComplete.value ? 'done' : (isFinalizing.value ? 'active' : 'todo')
  steps.push({
    key: 'complete',
    noLabel: 'OK',
    title: t('ui.complete'),
    status: completeStatus,
    meta: completeStatus === 'active' ? t('step4.metaFinalizing') : ''
  })

  return steps
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  } catch {
    return ''
  }
}

const formatParams = (params) => {
  if (!params) return ''
  try {
    return JSON.stringify(params, null, 2)
  } catch {
    return String(params)
  }
}

const formatResultSize = (length) => formatCharCount(length, t, locale.value)

const truncateText = (text, maxLen) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '...'
}

const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')

const renderMarkdown = (content) => {
  if (!content) return ''
  
  // 去掉开头的二级标题（## xxx），因为章节标题已在外层显示
  let processedContent = escapeHtml(content.replace(/^##\s+.+\n+/, ''))
  
  // 处理代码块
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  
  // 处理行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  
  // 处理标题
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  
  // 处理引用块
  // El escape de arriba convierte «>» en «&gt;», así que la regla antigua (/^> /) no casaba nunca y las citas
  // salían como texto con «> » delante. Las líneas seguidas forman una sola cita; «— Fulano» es su firma.
  html = html.replace(/^&gt;(?: (.*))?$/gm, (m, text = '') => {
    const cite = text.match(/^\s*[—–]\s*(.+)$/)
    return cite
      ? `<blockquote class="md-quote"><span class="md-quote-cite">— ${cite[1]}</span></blockquote>`
      : `<blockquote class="md-quote">${text}</blockquote>`
  })
  html = html.replace(/<\/blockquote>\n<blockquote class="md-quote">(?=<span class="md-quote-cite">)/g, '')
  html = html.replace(/<\/blockquote>\n<blockquote class="md-quote">/g, '<br>')

  // Tablas (GFM): cabecera, fila separadora |---|:--:| y filas. Sin separador no es tabla y no se toca.
  html = html.replace(/^(\|.*\|)[ \t]*\n(\|[ \t:|-]*-[ \t:|-]*\|)[ \t]*\n((?:\|.*\|[ \t]*(?:\n|$))*)/gm, (m, head, sep, body) => {
    const cells = row => row.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
    const aligns = cells(sep).map(c => (c.startsWith(':') && c.endsWith(':') ? ' class="is-center"' : c.endsWith(':') ? ' class="is-right"' : ''))
    const th = cells(head).map((c, i) => `<th${aligns[i] || ''}>${c}</th>`).join('')
    const rows = body.trim() ? body.trim().split('\n').map(r => `<tr>${cells(r).map((c, i) => `<td${aligns[i] || ''}>${c}</td>`).join('')}</tr>`).join('') : ''
    return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${th}</tr></thead><tbody>${rows}</tbody></table></div>\n`
  })

  // 处理列表 - 支持子列表
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  // 包装无序列表
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // 包装有序列表
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')

  // 清理列表项之间的所有空白
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // 清理列表开始标签后的空白
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // 清理列表结束标签前的空白
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  // 处理粗体和斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  
  // 处理分隔线
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  
  // 处理换行 - 空行变成段落分隔，单换行变成 <br>
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  
  // 包装在段落中
  html = '<p class="md-p">' + html + '</p>'
  
  // 清理空段落
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr|<div class="md-table-wrap")/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>|<\/table><\/div>)<\/p>/g, '$1')
  // 清理块级元素前后的 <br> 标签
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote|<div class="md-table-wrap")/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/table><\/div>)\s*<br>/g, '$1')
  // 清理 <p><br> 紧跟块级元素的情况（多余空行导致）
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr|<div class="md-table-wrap")/g, '$2')
  // 清理连续的 <br> 标签
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // 清理块级元素后紧跟的段落开始标签前的 <br>
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>|<\/table><\/div>)<br>(<p|<div)/g, '$1$2')

  // 修复非连续有序列表的编号：当单项 <ol> 被段落内容隔开时，保持编号递增
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  return html
}

const getTimelineItemClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  const isMilestone = log.action === 'section_complete' || log.action === 'report_complete'
  return {
    'node--active': isLatest,
    'node--done': !isLatest && isMilestone,
    'node--muted': !isLatest && !isMilestone,
    'node--tool': log.action === 'tool_call' || log.action === 'tool_result'
  }
}

const getConnectorClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  if (isLatest) return 'dot-active'
  if (log.action === 'section_complete' || log.action === 'report_complete') return 'dot-done'
  return 'dot-muted'
}

const getActionLabel = (action) => {
  const labels = {
    'report_start': t('ui.act.report_start'),
    'planning_start': t('ui.act.planning_start'),
    'planning_complete': t('ui.act.planning_complete'),
    'section_start': t('ui.act.section_start'),
    'section_content': t('ui.act.section_content'),
    'section_complete': t('ui.act.section_complete'),
    'tool_call': t('ui.act.tool_call'),
    'tool_result': t('ui.act.tool_result'),
    'llm_response': t('ui.act.llm_response'),
    'report_complete': t('ui.act.report_complete')
  }
  return labels[action] || action
}

const getLogLevelClass = (log) => {
  if (log.includes('ERROR') || log.includes('错误')) return 'error'
  if (log.includes('WARNING') || log.includes('警告')) return 'warning'
  // INFO 使用默认颜色，不标记为 success
  return ''
}

// Polling
let agentLogTimer = null
let consoleLogTimer = null

const fetchAgentLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, agentLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        newLogs.forEach(log => {
          agentLogs.value.push(log)
          
          if (log.action === 'planning_complete' && log.details?.outline) {
            reportOutline.value = log.details.outline
          }
          
          if (log.action === 'section_start') {
            currentSectionIndex.value = log.section_index
          }

          // section_complete - 章节生成完成
          if (log.action === 'section_complete') {
            if (log.details?.content) {
              generatedSections.value[log.section_index] = log.details.content
              // 自动展开刚生成的章节
              expandedContent.value.add(log.section_index - 1)
              currentSectionIndex.value = null
            }
          }
          
          if (log.action === 'report_complete') {
            isComplete.value = true
            currentSectionIndex.value = null  // 确保清除 loading 状态
            emit('update-status', 'completed')
            stopPolling()
            // 滚动逻辑统一在循环结束后的 nextTick 中处理
          }

          // report_failed - 后端生成报告时崩溃/异常，停止轮询避免无限转菊花
          // El servidor escribe la acción `error` cuando la generación se cae; antes solo se reconocían
          // `report_failed`/`report_error` (que nadie escribe) y la pantalla se quedaba en «Generando…» para siempre
          if (log.action === 'report_failed' || log.action === 'report_error' || log.action === 'error') {
            currentSectionIndex.value = null
            reportError.value = log.details?.error || log.message || t('common.unknownError')
            emit('add-log', { level: 'error', message: t('step4.reportFailed', { error: reportError.value }) })
            emit('update-status', 'error')
            stopPolling()
          }

          if (log.action === 'report_start') {
            startTime.value = new Date(log.timestamp)
          }
        })
        
        agentLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (rightPanel.value) {
            // 如果任务已完成，滚动到顶部；否则滚动到底部跟随最新日志
            if (isComplete.value) {
              rightPanel.value.scrollTop = 0
            } else {
              rightPanel.value.scrollTop = rightPanel.value.scrollHeight
            }
          }
        })
      }
    }
    pollFailures = 0
  } catch (err) {
    console.warn('Failed to fetch agent log:', err)
    pollFailures += 1
    // Un informe borrado o ajeno responde 404: no se queda esperando para siempre
    if (err?.response?.status === 404 && pollFailures >= 2) {
      failReport(t('step4.reportNotFound'))
    }
  }
  // Cada ~10 s se mira el estado del propio informe: un informe que quedó fallido (p. ej. por un reinicio del servidor)
  // no escribe nada más en el registro y sin esto la pantalla no se enteraba
  pollsSinceStatusCheck += 1
  if (pollsSinceStatusCheck >= 5 && !isComplete.value && !reportError.value) {
    pollsSinceStatusCheck = 0
    checkReportStatus()
  }
}

let pollFailures = 0
let pollsSinceStatusCheck = 0

const failReport = (message) => {
  currentSectionIndex.value = null
  reportError.value = String(message || t('common.unknownError')).slice(0, 400)
  emit('add-log', { level: 'error', message: t('step4.reportFailed', { error: reportError.value }) })
  emit('update-status', 'error')
  stopPolling()
}

const checkReportStatus = async () => {
  try {
    const res = await getReport(props.reportId)
    const report = res?.data
    if (res?.success && report) { reportEvidence.value = report.evidence || null; reportChecked.value = true }
    if (report?.status === 'failed') failReport(report.error)
  } catch (err) {
    if (err?.response?.status === 404) failReport(t('step4.reportNotFound'))
  }
}

const regenerate = async () => {
  if (regenerating.value || !props.simulationId) return
  regenerating.value = true
  regenerateError.value = ''
  try {
    const res = await generateReport({ simulation_id: props.simulationId, force_regenerate: true })
    const newId = res?.data?.report_id
    if (newId) router.push({ name: 'Report', params: { reportId: newId } })
  } catch (err) {
    regenerateError.value = err?.message || t('common.unknownError')
  } finally {
    regenerating.value = false
  }
}

// 提取最终答案内容 - 从 LLM response 中提取章节内容
const extractFinalContent = (response) => {
  if (!response) return null
  
  // 尝试提取 <final_answer> 标签内的内容
  const finalAnswerTagMatch = response.match(/<final_answer>([\s\S]*?)<\/final_answer>/)
  if (finalAnswerTagMatch) {
    return finalAnswerTagMatch[1].trim()
  }
  
  // 尝试找 Final Answer: 后面的内容（支持多种格式）
  // 格式1: Final Answer:\n\n内容
  // 格式2: Final Answer: 内容
  const finalAnswerMatch = response.match(/Final\s*Answer:\s*\n*([\s\S]*)$/i)
  if (finalAnswerMatch) {
    return finalAnswerMatch[1].trim()
  }
  
  // 尝试找 最终答案: 后面的内容
  const chineseFinalMatch = response.match(/最终答案[:：]\s*\n*([\s\S]*)$/i)
  if (chineseFinalMatch) {
    return chineseFinalMatch[1].trim()
  }
  
  // 如果以 ## 或 # 或 > 开头，可能是直接的 markdown 内容
  const trimmedResponse = response.trim()
  if (trimmedResponse.match(/^[#>]/)) {
    return trimmedResponse
  }
  
  // 如果内容较长且包含markdown格式，尝试移除思考过程后返回
  if (response.length > 300 && (response.includes('**') || response.includes('>'))) {
    // 移除 Thought: 开头的思考过程
    const thoughtMatch = response.match(/^Thought:[\s\S]*?(?=\n\n[^T]|\n\n$)/i)
    if (thoughtMatch) {
      const afterThought = response.substring(thoughtMatch[0].length).trim()
      if (afterThought.length > 100) {
        return afterThought
      }
    }
  }
  
  return null
}

const fetchConsoleLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getConsoleLog(props.reportId, consoleLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        consoleLogs.value.push(...newLogs)
        consoleLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (logContent.value) {
            logContent.value.scrollTop = logContent.value.scrollHeight
          }
        })
      }
    }
  } catch (err) {
    console.warn('Failed to fetch console log:', err)
  }
}

const startPolling = () => {
  if (agentLogTimer || consoleLogTimer) return
  
  fetchAgentLog()
  fetchConsoleLog()
  checkReportStatus()       // ya al abrir: un informe fallido o inexistente no genera registro y no hay que esperar 10 s a saberlo
  
  agentLogTimer = setInterval(fetchAgentLog, 2000)
  consoleLogTimer = setInterval(fetchConsoleLog, 1500)
}

const stopPolling = () => {
  if (agentLogTimer) {
    clearInterval(agentLogTimer)
    agentLogTimer = null
  }
  if (consoleLogTimer) {
    clearInterval(consoleLogTimer)
    consoleLogTimer = null
  }
}

// Lifecycle
// «Fuente de datos: <fuente> (estudio NNNN)» si el público de esta simulación se ancló a datos reales de su país
const cisCita = ref('')
const cargarCitaCis = async () => {
  if (!props.simulationId) return
  try {
    const res = await getPoblacionSimulacion(props.simulationId)
    const d = res?.data
    const est = d?.estudios || []
    const source = d?.fuente || ''
    // sin_datos = se pidió pero no se aplicó: no se cita una fuente que no se usó
    cisCita.value = res.success && d && !d.sin_datos
      ? (est.length ? t('step2.datosSource', { source, ref: est.join(', ') }) : t('step2.datosSourceShort', { source }))
      : ''
  } catch (e) {
    cisCita.value = ''
  }
}

// La página del informe conoce la simulación DESPUÉS de montarse (la saca del informe): pedir la cita solo al montar la
// dejaba sin «Fuente de datos» en pantalla. Se pide cuando llega el id y se vuelve a pedir si cambia.
watch(() => props.simulationId, () => cargarCitaCis(), { immediate: true })

onMounted(() => {
  if (props.reportId) {
    addLog(`Report Agent initialized: ${props.reportId}`)
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    agentLogs.value = []
    consoleLogs.value = []
    agentLogLine.value = 0
    consoleLogLine.value = 0
    reportEvidence.value = null
    reportChecked.value = false
    reportOutline.value = null
    currentSectionIndex.value = null
    generatedSections.value = {}
    expandedContent.value = new Set()
    expandedLogs.value = new Set()
    collapsedSections.value = new Set()
    isComplete.value = false
    reportError.value = null
    regenerateError.value = ''
    pollFailures = 0
    pollsSinceStatusCheck = 0
    startTime.value = null
    
    startPolling()
  }
}, { immediate: true })
</script>

<style scoped>
/*
 * Paso 4 · informe. Solo tokens de koolbrand.css: lima, tinta, grises, crema, --kb-ok-* y --kb-danger-*.
 * Contrastes que se usan aquí (WCAG 2.2, medidos):
 *   --kb-muted #6E6E6E sobre blanco / crema-50 / crema-100 ...... 5,12 / 4,72 / 4,52   (nunca sobre --kb-soft: 4,32)
 *   --kb-text-on-soft #2A2A2A sobre --kb-soft #ECECEC ............ 12,2
 *   --kb-ok-text #5C6C16 sobre --kb-ok-bg #EFF8D8 / blanco ........ 5,3 / 5,81
 *   lima #CCE673 sobre tinta ...................................... 14,27   · --kb-muted-on-dark #8A8A8A sobre tinta 5,5
 *   blanco sobre #6E6E6E (número de un hecho caducado) ............ 5,12
 * Botones, una firma por rol: primario (relleno lima, uno por vista: «Entrar a interacción profunda»),
 * secundario (.r4-btn), texto (.r4-link), pestaña (.r4-tab; la activa, tinta con filete) e icono (.r4-icon-btn).
 * Las categorías (tipo de herramienta, sí/no, hecho vigente/caducado, pregunta/respuesta) se distinguen por
 * icono, texto, forma o luminosidad, nunca por un tono propio.
 */
.report-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--kb-surface-2);
  font-family: var(--kb-font-sans);
  overflow: hidden;
}

/* Foco visible: contorno tinta de 2 px en todo lo enfocable, también los bloques con desplazamiento propio
   (respuesta del modelo, salida en bruto), que Chrome hace enfocables con teclado. Lima sobre el registro oscuro. */
.report-panel :deep(:focus-visible) {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
}
.report-panel :deep(.r4-tab:focus-visible) { outline-offset: -2px; }
.console-logs :focus-visible { outline-color: var(--kb-accent-solid) !important; }

/* Main Split Layout */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ========== Botones: una firma por rol ========== */
/* Secundario: contorno de control (#858585, ≥ 3:1 sobre blanco), texto tinta */
.report-panel :deep(.r4-btn) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  background: var(--kb-surface);
  color: var(--kb-text);
  border: 1px solid var(--kb-control-line);
  border-radius: 8px;
  font: 600 13px/1 var(--kb-font-sans);
  white-space: nowrap;
  cursor: pointer;
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.report-panel :deep(.r4-btn:hover) {
  border-color: var(--kb-text);
  background: var(--kb-surface-2);
}

/* Texto: sin caja; texto tinta con subrayado lima (decorativo) */
.report-panel :deep(.r4-link) {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0;
  background: none;
  border: 0;
  font: 600 13px/1.2 var(--kb-font-sans);
  color: var(--kb-text);
  text-decoration: underline;
  text-decoration-color: var(--kb-accent-line);
  text-decoration-thickness: 2px;
  text-underline-offset: 4px;
  cursor: pointer;
}
.report-panel :deep(.r4-link:hover) { text-decoration-color: var(--kb-text); }

/* Pestaña: la activa, en tinta y negrita con filete inferior; las demás, gris legible sobre blanco */
.report-panel :deep(.r4-tab) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 10px;
  background: transparent;
  color: var(--kb-muted);
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  font: 500 13px/1 var(--kb-font-sans);
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.report-panel :deep(.r4-tab:hover) {
  color: var(--kb-text);
  border-bottom-color: var(--kb-line-strong);
}
.report-panel :deep(.r4-tab.active) {
  color: var(--kb-text);
  font-weight: 600;
  border-bottom-color: var(--kb-text);
}

/* Icono: 32 × 32; la caja aparece al pasar por encima */
.report-panel :deep(.r4-icon-btn) {
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  background: transparent;
  color: var(--kb-text-2);
  border: 1px solid transparent;
  border-radius: 8px;
  font: 600 13px/1 var(--kb-font-sans);
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.report-panel :deep(.r4-icon-btn:hover) {
  background: var(--kb-surface-2);
  border-color: var(--kb-line);
}

/* ========== Cabecera fija del flujo (mientras se genera) ========== */
.panel-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: var(--kb-surface);
  border-bottom: 1px solid var(--kb-line);
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--kb-text);
  flex-shrink: 0;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.header-index {
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.04em;
  color: var(--kb-muted);
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-meta {
  margin-left: auto;
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--kb-text);
  flex-shrink: 0;
}

.panel-header--active {
  background: var(--kb-surface-2);
  border-bottom-color: var(--kb-text);
}

.panel-header--done .header-index { color: var(--kb-accent-text); }
.panel-header--todo .header-title { color: var(--kb-muted); }

/* ========== Panel izquierdo: el informe ========== */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: var(--kb-surface);
  border-right: 1px solid var(--kb-line);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 32px 48px 64px;
}

.left-panel::-webkit-scrollbar,
.right-panel::-webkit-scrollbar { width: 6px; }
.left-panel::-webkit-scrollbar-track,
.right-panel::-webkit-scrollbar-track { background: transparent; }
.left-panel::-webkit-scrollbar-thumb,
.right-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 4px;
  transition: background 0.3s ease;
}
.left-panel:hover::-webkit-scrollbar-thumb,
.right-panel:hover::-webkit-scrollbar-thumb { background: var(--kb-line-strong); }
.left-panel::-webkit-scrollbar-thumb:hover,
.right-panel::-webkit-scrollbar-thumb:hover { background: var(--kb-control-line); }

.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block { margin-bottom: 32px; }
.cis-source-line { margin: 8px 0 0; font-size: 12px; font-weight: 600; color: var(--kb-text-2); }

.report-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 24px;
}

.report-tag {
  background: var(--kb-text);
  color: var(--kb-accent-solid);
  font: 600 12px/1 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 8px;
  border-radius: 4px;
}

.report-id {
  font: 400 12px/1.4 var(--kb-font-mono);
  color: var(--kb-muted);
  overflow-wrap: anywhere;
}

/* El título se lee entero: sin recorte a 3 líneas ni «…», con líneas equilibradas */
.main-title {
  font-family: var(--kb-font-sans);
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 800;
  color: var(--kb-text);
  line-height: 1.15;
  margin: 0 0 16px 0;
  letter-spacing: -0.02em;
  text-wrap: balance;
  overflow-wrap: anywhere;
}

.sub-title {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  line-height: 1.55;
  color: var(--kb-text-2);
  margin: 0 0 32px 0;
  max-width: 56ch;
  text-wrap: pretty;
  overflow-wrap: anywhere;
}

.header-divider {
  height: 1px;
  background: var(--kb-line);
  width: 100%;
}

/* Sections List */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 40px;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 8px 12px;
  margin: -8px -12px;
  border-radius: 8px;
  transition: background-color 0.2s ease;
}

.section-header-row.clickable { cursor: pointer; }
.section-header-row.clickable:hover { background-color: var(--kb-surface-2); }

.collapse-btn {
  margin-left: auto;
  align-self: center;
}

.collapse-icon { transition: transform 0.3s ease; }
.collapse-icon.is-collapsed { transform: rotate(-90deg); }

.section-number {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  font-weight: 500;
  color: var(--kb-muted);
  flex-shrink: 0;
}

.section-title {
  font-family: var(--kb-font-sans);
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: var(--kb-text);
  margin: 0;
  text-wrap: balance;
  overflow-wrap: anywhere;
  transition: color 0.3s ease;
}

/* Pendiente: gris legible (antes #CFCFCF sobre blanco, 1,56:1) */
.report-section-item.is-pending .section-title { color: var(--kb-muted); }

.section-body {
  padding-left: 32px;
  min-width: 0;
}

/* ---------- Markdown del informe: medida ≤ 75 caracteres (56ch de Inter Tight ≈ 72), interlineado 1,6 ---------- */
.generated-content {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  line-height: 1.6;
  color: var(--kb-text-2);
  max-width: 56ch;
  overflow-wrap: anywhere;
}

.generated-content :deep(.md-p) { margin: 0 0 1em; }
.generated-content :deep(.md-p:last-child) { margin-bottom: 0; }

.generated-content :deep(:is(.md-h2, .md-h3, .md-h4, .md-h5)) {
  font-family: var(--kb-font-sans);
  color: var(--kb-text);
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.01em;
  margin: 1.6em 0 0.6em;
  text-wrap: balance;
}
.generated-content :deep(:is(.md-h2, .md-h3, .md-h4, .md-h5):first-child) { margin-top: 0; }
.generated-content :deep(.md-h2) { font-size: 22px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }
.generated-content :deep(.md-h5) { font-size: 14px; letter-spacing: 0.04em; text-transform: uppercase; }

.generated-content :deep(:is(.md-ul, .md-ol)) {
  padding-left: 1.4em;
  margin: 0 0 1em;
}
.generated-content :deep(:is(.md-li, .md-oli)) {
  margin: 0.35em 0;
  padding-left: 0.2em;
}
.generated-content :deep(:is(.md-li, .md-oli)[data-level="1"]) { margin-left: 1.2em; }
.generated-content :deep(:is(.md-li, .md-oli)[data-level="2"]) { margin-left: 2.4em; }
.generated-content :deep(:is(.md-li, .md-oli)::marker) {
  color: var(--kb-accent-text);
  font-weight: 700;
}

/* Citas: filete lima y la firma («— Fulano») debajo, en gris */
.generated-content :deep(.md-quote) {
  margin: 1.5em 0;
  padding: 4px 0 4px 20px;
  border-left: 3px solid var(--kb-accent-line);
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
}
.generated-content :deep(.md-quote-cite) {
  display: block;
  margin-top: 8px;
  font-size: 14px;
  color: var(--kb-muted);
}

/* Tablas: cabecera con filete tinta, filas cebreadas en crema, cifras tabulares, desplazamiento propio */
.generated-content :deep(.md-table-wrap) {
  margin: 1.5em 0;
  max-width: 100%;
  overflow-x: auto;
}
.generated-content :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  line-height: 1.45;
  font-variant-numeric: tabular-nums;
}
.generated-content :deep(.md-table th) {
  padding: 8px 12px;
  text-align: left;
  vertical-align: bottom;
  font-weight: 600;
  color: var(--kb-text);
  border-bottom: 2px solid var(--kb-text);
}
.generated-content :deep(.md-table td) {
  padding: 8px 12px;
  vertical-align: top;
  color: var(--kb-text-2);
  border-bottom: 1px solid var(--kb-line);
}
.generated-content :deep(.md-table tbody tr:nth-child(even)) { background: var(--kb-surface-2); }
.generated-content :deep(.md-table .is-center) { text-align: center; }
.generated-content :deep(.md-table .is-right) { text-align: right; }

.generated-content :deep(.code-block) {
  background: var(--kb-surface-2);
  padding: 12px 16px;
  border-radius: 6px;
  font-family: var(--kb-font-mono);
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  margin: 1em 0;
  border: 1px solid var(--kb-line);
}

.generated-content :deep(.inline-code) {
  font-family: var(--kb-font-mono);
  font-size: 14px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--kb-soft);
  color: var(--kb-text-on-soft);
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: var(--kb-text);
}

.generated-content :deep(.md-hr) {
  border: 0;
  border-top: 1px solid var(--kb-line);
  margin: 2em 0;
}

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  animation: spin 1s linear infinite;
  display: flex;
}
.loading-icon svg { width: 100%; height: 100%; }
.spin-track { stroke: var(--kb-line); }
.spin-head { stroke: var(--kb-text); }

.loading-text {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  color: var(--kb-text-2);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Waiting Placeholder */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  padding: 40px;
  color: var(--kb-muted);
}

.waiting-animation {
  position: relative;
  width: 48px;
  height: 48px;
}

.waiting-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid var(--kb-line-strong);
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}
.waiting-ring:nth-child(2) { animation-delay: 0.4s; }
.waiting-ring:nth-child(3) { animation-delay: 0.8s; }

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text { font-size: 14px; }

/* ========== Panel derecho: flujo de trabajo ========== */
.right-panel {
  flex: 1;
  background: var(--kb-surface);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.mono { font-family: var(--kb-font-mono); }

.workflow-overview { padding: 16px 20px 0 20px; }

.workflow-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-bottom: 12px;
}

.metric {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.metric-right { margin-left: auto; }

.metric-label {
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-muted);
}

.metric-value {
  font: 600 13px/1 var(--kb-font-mono);
  color: var(--kb-text);
}

/* Estado: «hecho» con los semánticos de la marca (lima oscuro sobre lima claro), «en curso» con tinta */
.metric-pill {
  display: inline-block;
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--kb-line);
  background: var(--kb-surface);
  color: var(--kb-muted);
}
.metric-pill.pill--processing { border-color: var(--kb-text); color: var(--kb-text); }
.metric-pill.pill--completed { background: var(--kb-ok-bg); border-color: var(--kb-ok-line); color: var(--kb-ok-text); }
.metric-pill.pill--pending { border-style: dashed; border-color: var(--kb-control-line); }
.metric-pill.pill--failed { border-color: var(--kb-danger-line); color: var(--kb-danger-text); }

.workflow-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 12px;
}

.wf-step {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  background: var(--kb-surface);
}
.wf-step--active { background: var(--kb-surface-2); border-color: var(--kb-text); }
.wf-step--todo { border-style: dashed; }

.wf-step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 16px;
}

/* Estado por forma: aro vacío (pendiente), punto tinta (en curso), punto lima con marca tinta (hecho) */
.wf-step-dot {
  width: 16px;
  height: 16px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: transparent;
  border: 2px solid var(--kb-control-line);
  color: var(--kb-text);
}
.wf-step--active .wf-step-dot { background: var(--kb-text); border-color: var(--kb-text); }
.wf-step--done .wf-step-dot { background: var(--kb-accent-solid); border-color: var(--kb-text); }
.wf-step-line { display: none; }

.wf-step-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.wf-step-index {
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.04em;
  color: var(--kb-muted);
  flex-shrink: 0;
}

.wf-step-title {
  font-family: var(--kb-font-sans);
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
  line-height: 1.35;
  min-width: 0;
  overflow-wrap: anywhere;
}

.wf-step-meta {
  margin-left: auto;
  font: 600 11px/1 var(--kb-font-mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--kb-text);
  flex-shrink: 0;
}

.wf-step--todo .wf-step-title { color: var(--kb-muted); }

/* Primario: el único relleno de la vista, con la firma de la portada (lima + tinta, sombra dura al pasar) */
.next-step-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  margin: 4px 0 0;
  padding: 16px 26px;
  font: 600 16px/1 var(--kb-font-sans);
  color: var(--kb-accent-on);
  background: var(--kb-accent-solid);
  border: 1px solid var(--kb-accent-solid);
  border-radius: 10px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
}
.next-step-btn:hover {
  background: var(--kb-accent-hover);
  border-color: var(--kb-accent-hover);
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--kb-text);
}
.next-step-btn:active { transform: none; box-shadow: none; }
.next-step-btn svg { transition: transform 0.2s ease; }
.next-step-btn:hover svg { transform: translateX(4px); }

.workflow-divider {
  height: 1px;
  background: var(--kb-line);
  margin: 16px 0 0 0;
}

/* Workflow Timeline */
.workflow-timeline {
  padding: 16px 20px 24px;
  flex: 1;
}

.timeline-item {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  background: var(--kb-surface);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.timeline-item:hover { background: var(--kb-surface-2); }
.timeline-item.node--active,
.timeline-item.node--active:hover { background: var(--kb-surface-2); border-color: var(--kb-text); }

.timeline-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 12px;
  padding-top: 2px;
}

.connector-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--kb-line-strong);
  border: 2px solid var(--kb-surface);
  flex-shrink: 0;
}

.connector-line {
  width: 2px;
  flex: 1;
  margin-top: 4px;
  background: var(--kb-soft);
}

/* Punto por luminosidad y contorno: gris (paso), tinta (el último en curso), lima con aro tinta (hito) */
.dot-active { background: var(--kb-text); border-color: var(--kb-text); }
.dot-done { background: var(--kb-accent-solid); border-color: var(--kb-text); }
.dot-muted { background: var(--kb-line-strong); }

.timeline-content { min-width: 0; }

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.action-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.action-time {
  font: 400 11px/1 var(--kb-font-mono);
  color: var(--kb-muted);
  flex-shrink: 0;
}

.timeline-body {
  font-size: 13px;
  line-height: 1.5;
  color: var(--kb-text-2);
  min-width: 0;
}

.timeline-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--kb-line);
}

.elapsed-placeholder { flex-shrink: 0; }

.footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}

/* Tiempo transcurrido: sin fondo gris (era #6E6E6E sobre #ECECEC, 4,32:1) */
.elapsed-badge {
  font: 400 11px/1 var(--kb-font-mono);
  color: var(--kb-muted);
}

/* Timeline Body Elements */
.info-row {
  display: flex;
  gap: 12px;
  margin-bottom: 6px;
}

.info-key {
  font-size: 12px;
  line-height: 1.6;
  color: var(--kb-muted);
  min-width: 80px;
  flex-shrink: 0;
}

.info-val {
  color: var(--kb-text-2);
  min-width: 0;
  overflow-wrap: anywhere;
}

.status-message {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  border: 1px solid transparent;
  background: var(--kb-surface-2);
  color: var(--kb-text-2);
}
.status-message.success { background: var(--kb-ok-bg); border-color: var(--kb-ok-line); color: var(--kb-ok-text); }

.outline-badge {
  display: inline-block;
  margin-top: 8px;
  padding: 4px 10px;
  background: var(--kb-surface);
  color: var(--kb-muted);
  border: 1px solid var(--kb-line);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.section-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  padding: 6px 12px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
}
.section-tag svg { flex-shrink: 0; }
.section-tag.content-ready { border-style: dashed; border-color: var(--kb-control-line); }
.section-tag.completed { background: var(--kb-ok-bg); border-color: var(--kb-ok-line); }
.section-tag.completed svg { color: var(--kb-ok-text); }

.tag-num {
  font: 600 11px/1 var(--kb-font-mono);
  color: var(--kb-muted);
}

.tag-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--kb-text-2);
  min-width: 0;
}
.section-tag.completed .tag-title { color: var(--kb-text); }

/* Herramienta: tesela tinta con el icono en lima + nombre. Lo que la distingue es el icono y el texto. */
.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px 4px 4px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
}

.tool-tile {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: var(--kb-text);
  color: var(--kb-accent-solid);
  flex-shrink: 0;
}

.tool-icon { display: block; }

.tool-params {
  margin-top: 12px;
  overflow-x: auto;
}

.tool-params pre,
.result-raw pre,
.llm-content pre {
  margin: 0;
  font: 400 12px/1.5 var(--kb-font-mono);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--kb-text-2);
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  padding: 12px;
}

/* Result Wrapper */
.result-wrapper { padding-top: 4px; }

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}

.result-tool {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
}

.result-size {
  font: 400 12px/1.4 var(--kb-font-mono);
  color: var(--kb-muted);
}

.result-raw {
  margin-top: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.raw-preview {
  margin: 0;
  font: 400 12px/1.5 var(--kb-font-mono);
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--kb-text-2);
}

/* LLM Response: «no» en contorno, «sí» con relleno gris suave, «respuesta final» con el semántico de hecho */
.llm-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 12px;
  line-height: 1.4;
  padding: 2px 8px;
  border: 1px solid var(--kb-line);
  border-radius: 4px;
  background: var(--kb-surface);
  color: var(--kb-muted);
}
.meta-tag.active { background: var(--kb-soft); border-color: var(--kb-soft); color: var(--kb-text-on-soft); font-weight: 600; }
.meta-tag.final-answer { background: var(--kb-ok-bg); border-color: var(--kb-ok-line); color: var(--kb-ok-text); }

.final-answer-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 10px 14px;
  background: var(--kb-ok-bg);
  border: 1px solid var(--kb-ok-line);
  border-radius: 6px;
  color: var(--kb-ok-text);
  font-size: 13px;
  font-weight: 500;
}
.final-answer-hint svg { flex-shrink: 0; }
.final-answer-hint span { min-width: 0; overflow-wrap: anywhere; }

.llm-content {
  margin-top: 10px;
  max-height: 240px;
  overflow-y: auto;
}

/* Complete Banner */
.complete-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--kb-ok-bg);
  border: 1px solid var(--kb-ok-line);
  border-radius: 8px;
  color: var(--kb-ok-text);
  font-weight: 600;
  font-size: 14px;
}

/* Detalle técnico (cronograma del agente): solo con el conmutador global de «detalles técnicos» */
.tech-timeline { margin: 4px 0 0; border-top: 1px solid var(--kb-line); }
.tech-timeline-title {
  margin: 0;
  padding: 14px 4px 0;
  font: 600 11px/1.3 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-muted);
}

/* Workflow Empty */
.workflow-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--kb-muted);
  font-size: 13px;
}

.empty-pulse {
  width: 24px;
  height: 24px;
  background: var(--kb-line);
  border-radius: 50%;
  margin-bottom: 16px;
  animation: pulse-ring 1.5s infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.5; }
}

/* Timeline Transitions */
.timeline-item-enter-active { transition: all 0.4s ease; }
.timeline-item-enter-from { opacity: 0; transform: translateX(-20px); }

/* ========== Resultados de herramientas: una sola piel para las cuatro (análisis, panorámica, búsqueda, entrevista) ========== */
:deep(.result-header) {
  padding: 12px 16px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
}

:deep(:is(.result-header, .interview-header) .header-main) {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: baseline;
  gap: 4px 16px;
  margin-bottom: 8px;
}

:deep(:is(.result-header, .interview-header) .header-title) {
  font-family: var(--kb-font-sans);
  font-size: 14px;
  font-weight: 700;
  color: var(--kb-text);
}

:deep(.header-stats) {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  font-size: 12px;
}

:deep(.stat-item) {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
}

:deep(.stat-value) {
  font: 700 12px/1.4 var(--kb-font-mono);
  color: var(--kb-text);
}

:deep(:is(.stat-label, .stat-divider)) {
  font-size: 12px;
  color: var(--kb-muted);
}

:deep(.stat-size) {
  font: 400 12px/1.4 var(--kb-font-mono);
  color: var(--kb-muted);
}

:deep(:is(.header-topic, .header-query)) {
  font-size: 13px;
  line-height: 1.5;
  color: var(--kb-text-2);
}

/* Medida del texto corrido del panel derecho: 56ch ≈ 72 caracteres por línea (a 750 px salían más de 100) */
:deep(:is(.header-topic, .header-query, .header-scenario, .fact-content, .subquery-text)),
:deep(.interview-display :is(.qa-text, .reason-content, .summary-content, .quote-item)),
.info-val,
.status-message,
.final-answer-hint {
  max-width: 56ch;
}

:deep(.header-scenario) {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--kb-text-2);
}

:deep(:is(.scenario-label, .query-label)) {
  font-weight: 600;
  color: var(--kb-text);
}

:deep(.result-tabs) {
  display: flex;
  flex-wrap: wrap;
  gap: 0 4px;
  padding: 0 8px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
}
:deep(.result-tabs .r4-tab) { margin-bottom: -1px; }

:deep(.result-content) {
  padding: 12px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-top: 0;
  border-radius: 0 0 8px 8px;
}
:deep(.result-content.no-tabs) { border-top: 1px solid var(--kb-line); }

:deep(.result-content .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--kb-line);
}

:deep(.result-content .panel-title) {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
}

:deep(.result-content .panel-count) {
  font-size: 12px;
  color: var(--kb-muted);
  flex-shrink: 0;
}

:deep(:is(.facts-list, .relations-list, .subqueries-list, .edges-list)) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

:deep(.fact-item) {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
}

/* Hecho caducado: contorno discontinuo y número en gris oscuro (forma y luminosidad) */
:deep(.fact-item.historical) {
  background: var(--kb-surface);
  border-style: dashed;
  border-color: var(--kb-control-line);
}

:deep(.fact-number) {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: inline-grid;
  place-items: center;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-radius: 50%;
  font: 600 12px/1 var(--kb-font-mono);
  color: var(--kb-text-2);
}
:deep(.fact-item.historical .fact-number) {
  background: var(--kb-muted);
  border-color: var(--kb-muted);
  color: var(--kb-surface);
}

:deep(.fact-content) {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--kb-text-2);
}

:deep(.fact-time) {
  display: block;
  margin-bottom: 4px;
  font: 400 12px/1.4 var(--kb-font-mono);
  color: var(--kb-muted);
}

:deep(.fact-text) { display: block; }

:deep(:is(.entities-grid, .nodes-grid)) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(:is(.entity-tag, .node-tag)) {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 4px 8px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
}

:deep(:is(.entity-name, .node-name)) {
  font-size: 13px;
  font-weight: 500;
  color: var(--kb-text);
  overflow-wrap: anywhere;
}

:deep(:is(.entity-type, .node-type)) {
  font-size: 12px;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  padding: 1px 6px;
  border-radius: 4px;
}

:deep(.entity-fact-count) {
  font-size: 12px;
  color: var(--kb-muted);
}

:deep(:is(.relation-item, .edge-item)) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
}

:deep(:is(.rel-source, .rel-target, .edge-source, .edge-target)) {
  min-width: 0;
  padding: 4px 8px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line-strong);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--kb-text);
  overflow-wrap: anywhere;
}

:deep(:is(.rel-arrow, .edge-arrow)) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1 1 80px;
  min-width: 80px;
}

:deep(:is(.rel-line, .edge-line)) {
  flex: 1;
  height: 1px;
  background: var(--kb-line-strong);
}

/* El verbo de la relación: la etiqueta de acento de la marca (lima oscuro sobre lima claro, 5,3:1) */
:deep(:is(.rel-label, .edge-label)) {
  padding: 2px 6px;
  background: var(--kb-accent-subtle);
  border-radius: 4px;
  font: 500 12px/1.4 var(--kb-font-mono);
  color: var(--kb-accent-text);
  white-space: nowrap;
}

:deep(.subquery-item) {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
}

:deep(.subquery-number) {
  flex-shrink: 0;
  padding: 4px 6px;
  background: var(--kb-text);
  border-radius: 4px;
  font: 700 11px/1 var(--kb-font-mono);
  color: var(--kb-accent-solid);
}

:deep(.subquery-text) {
  font-size: 13px;
  line-height: 1.5;
  color: var(--kb-text-2);
}

/* «Ver todos»: botón secundario a todo el ancho */
:deep(.expand-btn) {
  display: flex;
  width: 100%;
  margin-top: 12px;
}

:deep(.empty-state) {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: var(--kb-muted);
}

/* ---------- Entrevista a agentes ---------- */
:deep(.interview-display .interview-header) { margin-bottom: 12px; }

:deep(.interview-display .agent-tabs) {
  display: flex;
  flex-wrap: wrap;
  gap: 0 4px;
  border-bottom: 1px solid var(--kb-line);
}

:deep(.interview-display .tab-avatar) {
  width: 20px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  background: var(--kb-soft);
  color: var(--kb-text-on-soft);
  font: 600 11px/1 var(--kb-font-mono);
  text-transform: uppercase;
  border-radius: 50%;
}
:deep(.interview-display .agent-tab.active .tab-avatar) {
  background: var(--kb-text);
  color: var(--kb-accent-solid);
}

:deep(.interview-display .tab-name) {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

:deep(.interview-display .interview-detail) { padding: 16px 0 0; }

:deep(.interview-display .agent-profile) {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

:deep(.interview-display .profile-avatar) {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  background: var(--kb-text);
  color: var(--kb-accent-solid);
  font: 700 14px/1 var(--kb-font-mono);
  text-transform: uppercase;
  border-radius: 50%;
}

:deep(.interview-display .profile-info) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .profile-name) {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text);
  margin-bottom: 2px;
  overflow-wrap: anywhere;
}

:deep(.interview-display .profile-role) {
  font-size: 12px;
  color: var(--kb-muted);
  margin-bottom: 4px;
}

:deep(.interview-display .profile-bio) {
  font-size: 12px;
  color: var(--kb-muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

:deep(.interview-display .selection-reason) {
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

/* Rótulos de apartado: mono en mayúsculas, gris legible */
:deep(.interview-display :is(.reason-label, .quotes-header, .summary-header)) {
  font: 600 12px/1.4 var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-muted);
  margin-bottom: 8px;
}

:deep(.interview-display .reason-content) {
  font-size: 13px;
  color: var(--kb-text-2);
  line-height: 1.55;
}

:deep(.interview-display .qa-thread) {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

:deep(.interview-display .qa-pair) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:deep(.interview-display :is(.qa-question, .qa-answer)) {
  display: flex;
  gap: 12px;
}

:deep(.interview-display .qa-badge) {
  width: 28px;
  height: 24px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font: 700 11px/1 var(--kb-font-mono);
  border-radius: 4px;
}

/* Pregunta en contorno; respuesta rellena en tinta con letra lima */
:deep(.interview-display .q-badge) {
  background: var(--kb-surface);
  color: var(--kb-text-2);
  border: 1px solid var(--kb-control-line);
}
:deep(.interview-display .a-badge) {
  background: var(--kb-text);
  color: var(--kb-accent-solid);
  border: 1px solid var(--kb-text);
}

:deep(.interview-display .qa-content) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .qa-sender) {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  overflow-wrap: anywhere;
}

:deep(.interview-display .qa-text) {
  font-size: 14px;
  color: var(--kb-text-2);
  line-height: 1.55;
}

:deep(.interview-display .answer-text) { color: var(--kb-text); }
:deep(.interview-display .answer-text strong) { font-weight: 600; }
:deep(.interview-display .placeholder-text) { font-style: italic; color: var(--kb-muted); }

:deep(.interview-display .qa-answer-header) {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 4px 12px;
  margin-bottom: 4px;
}

:deep(.interview-display .platform-switch) {
  display: flex;
  gap: 4px;
}
:deep(.interview-display .platform-icon) { flex-shrink: 0; }

:deep(.interview-display .expand-answer-btn) { margin-top: 8px; }

:deep(.interview-display .quotes-section) {
  border-top: 1px solid var(--kb-line);
  padding-top: 16px;
  margin-top: 16px;
}

:deep(.interview-display .quotes-list) {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

:deep(.interview-display .quote-item) {
  margin: 0;
  padding: 4px 0 4px 16px;
  border-left: 3px solid var(--kb-accent-line);
  font-size: 13px;
  line-height: 1.55;
  color: var(--kb-text);
}
:deep(.interview-display .quote-item .md-p) { margin: 0; }
:deep(.interview-display .quote-item strong) { font-weight: 600; }

:deep(.interview-display .summary-section) {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--kb-line);
}

:deep(.interview-display .summary-content) {
  font-size: 13px;
  color: var(--kb-text-2);
  line-height: 1.6;
}
:deep(.interview-display .summary-content :is(h2, h3, h4, h5)) {
  margin: 12px 0 8px 0;
  font-weight: 600;
  color: var(--kb-text);
}
:deep(.interview-display .summary-content :is(h2, h3)) { font-size: 14px; }
:deep(.interview-display .summary-content :is(h4, h5)) { font-size: 13px; }
:deep(.interview-display .summary-content p) { margin: 8px 0; }
:deep(.interview-display .summary-content strong) { font-weight: 600; color: var(--kb-text); }
:deep(.interview-display .summary-content :is(ul, ol)) { margin: 8px 0; padding-left: 20px; }
:deep(.interview-display .summary-content li) { margin: 4px 0; }
:deep(.interview-display .summary-content blockquote) {
  margin: 8px 0;
  padding-left: 12px;
  border-left: 3px solid var(--kb-accent-line);
  color: var(--kb-text-2);
}

/* ========== Registro técnico (fondo tinta) ========== */
.console-logs {
  background: var(--kb-text);
  color: var(--kb-line-strong);
  padding: 10px 16px;
  font-family: var(--kb-font-mono);
  border-top: 1px solid var(--kb-text);
  flex-shrink: 0;
}
.console-logs.is-open { padding-bottom: 16px; }

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--kb-muted-on-dark);
}
.console-logs.is-open .log-header {
  border-bottom: 1px solid var(--kb-text-2);
  padding-bottom: 8px;
  margin-bottom: 8px;
}

.log-header .log-toggle { margin-left: auto; }

.log-title {
  flex-shrink: 0;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--kb-muted-on-dark);
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 120px;
  overflow-y: auto;
  padding-right: 4px;
}
.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: var(--kb-text-2); border-radius: 4px; }

.log-line {
  font-size: 12px;
  line-height: 1.5;
}

.log-msg {
  color: var(--kb-line-strong);
  word-break: break-all;
}

/* Aviso y error: blanco en negrita; el error, además, con filete rojo de la marca a la izquierda */
.log-line.warning .log-msg,
.log-line.error .log-msg { color: var(--kb-surface); font-weight: 600; }
.log-line.error {
  border-left: 2px solid var(--kb-danger-line);
  padding-left: 8px;
}

/* Pantallas estrechas: informe arriba y flujo de trabajo debajo, en una sola columna que se desplaza */
@media (max-width: 900px) {
  .main-split-layout { flex-direction: column; overflow-y: auto; }
  .left-panel.report-style { width: 100%; min-width: 0; flex: none; padding: 24px 18px 32px; border-right: 0; border-bottom: 1px solid var(--kb-line); overflow-y: visible; }
  .right-panel { flex: none; overflow: visible; }
  .right-panel :is(.workflow-overview, .workflow-timeline, .wf-step, .wf-step-content, .wf-step-title-row) { min-width: 0; max-width: 100%; }
  .workflow-overview { padding: 16px 16px 0; }
  .workflow-timeline { padding: 16px 16px 24px; }
  .section-title { font-size: 22px; }
  .section-body { padding-left: 0; }
  :deep(.result-header) { padding: 12px; }
}

/* Móvil: la columna de puntos se come 24 px de cada tarjeta; el estado ya lo dicen el contorno y las etiquetas.
   Las pestañas de agentes se desplazan en horizontal en vez de apilarse en seis filas. */
@media (max-width: 600px) {
  .timeline-item { grid-template-columns: minmax(0, 1fr); }
  .timeline-connector { display: none; }
  :deep(.interview-display .agent-tabs) {
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--kb-line-strong) transparent;
  }
  :deep(.interview-display .agent-tab) { flex-shrink: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .header-dot,
  .loading-icon,
  .waiting-ring,
  .empty-pulse { animation: none; }
  .timeline-item-enter-active,
  .next-step-btn,
  .next-step-btn svg,
  .collapse-icon { transition: none; }
  .next-step-btn:hover { transform: none; }
}
</style>

<style>
/* English locale: smaller report title */
html[lang="en"] .report-header-block .main-title {
  font-size: 28px;
}

/* El informe falló o no existe */
.report-failed {
  margin: 16px 20px 0;
  padding: 14px 16px;
  border: 2px solid var(--ink-950);
  border-radius: 10px;
  background: var(--kb-surface, #fff);
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.12);
}
.report-failed-title { display: block; font: 700 0.98rem/1.3 var(--kb-font-sans); color: var(--ink-950); }
.report-failed-text { margin: 6px 0 0; font: 400 0.88rem/1.5 var(--kb-font-sans); color: var(--kb-text-2); overflow-wrap: anywhere; }
.report-failed-btn {
  margin-top: 12px;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: var(--lime-500, #cce673);
  color: var(--ink-950);
  font: 700 0.9rem/1 var(--kb-font-sans);
  cursor: pointer;
}
.report-failed-btn:hover:not(:disabled) { background: var(--lime-600, #b8d45a); }
.report-failed-btn:disabled { opacity: 0.6; cursor: wait; }
.report-failed-btn:focus-visible { outline: 2px solid var(--ink-950); outline-offset: 2px; }
</style>
