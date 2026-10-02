<template>
  <div class="interaction-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel" data-tour="int-left-panel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">{{ $t('ui.predictionReport') }}</span>
              <span class="report-id">ID: {{ reportId || '—' }}</span>
              <ReportDownloads :report-id="reportId" />
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list">
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
                <!-- botón de verdad para el teclado; el clic en toda la fila sigue funcionando -->
                <button
                  v-if="isSectionCompleted(idx + 1)"
                  type="button"
                  class="collapse-btn"
                  :aria-expanded="!collapsedSections.has(idx)"
                  :aria-label="(collapsedSections.has(idx) ? $t('step5.expandSection') : $t('step5.collapseSection')) + ': ' + section.title"
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

              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <MiniMarkdown v-if="generatedSections[idx + 1]" class="generated-content" headings strip-leading-heading :text="generatedSections[idx + 1]" />

                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="var(--kb-line)"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="var(--kb-text-2)" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">{{ $t('step4.generatingSection', { title: section.title }) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Error / vacío / esperando: siempre una frase clara (antes se quedaba en «Waiting…» para siempre si la carga fallaba) -->
        <div v-if="!reportOutline && reportLoadError" class="panel-notice is-error" role="alert">
          <p class="panel-notice-title">{{ $t('step5.reportLoadFailedTitle') }}</p>
          <p class="panel-notice-text">{{ $t('step5.reportLoadFailedBody') }}</p>
          <details class="notice-details">
            <summary>{{ $t('main.failDetails') }}</summary>
            <code>{{ reportLoadError }}</code>
          </details>
        </div>
        <div v-else-if="!reportOutline && reportLoaded" class="panel-notice" role="status">
          <p class="panel-notice-title">{{ $t('step5.reportEmptyTitle') }}</p>
          <p class="panel-notice-text">{{ $t('step5.reportEmptyBody') }}</p>
        </div>
        <div v-else-if="!reportOutline" class="waiting-placeholder" role="status">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">{{ $t('step4.waitingForReportAgent') }}</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Interaction Interface -->
      <div class="right-panel" ref="rightPanel" data-tour="int-right-panel">
        <!-- Unified Action Bar - Professional Design -->
        <div class="action-bar" data-tour="int-action-bar">
        <div class="action-bar-header">
          <svg class="action-bar-icon" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <div class="action-bar-text">
            <span class="action-bar-title">{{ $t('step5.interactiveTools') }}</span>
            <span class="action-bar-subtitle mono">{{ $t('step5.agentsAvailable', { count: profiles.length }) }}</span>
          </div>
        </div>
          <div class="action-bar-tabs">
            <button
              type="button"
              class="tab-pill"
              data-tour="int-tab-report"
              :class="{ active: activeTab === 'chat' && chatTarget === 'report_agent' }"
              :aria-pressed="activeTab === 'chat' && chatTarget === 'report_agent'"
              :title="$t('step5.tipChatReport')"
              @click="selectReportAgentChat"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
              </svg>
              <span>{{ $t('step5.chatWithReportAgent') }}</span>
            </button>
            <div class="agent-dropdown" v-if="profiles.length > 0" data-tour="int-tab-agent">
              <button
                type="button"
                class="tab-pill agent-pill"
                :class="{ active: activeTab === 'chat' && chatTarget === 'agent' }"
                :aria-expanded="showAgentDropdown"
                aria-haspopup="true"
                :title="selectedAgent ? `${selectedAgent.username} · ${$t('step5.tipChatAgent')}` : $t('step5.tipChatAgent')"
                @click="toggleAgentDropdown"
                ref="agentPillRef"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span>{{ selectedAgent ? selectedAgent.username : $t('step5.chatWithAgent') }}</span>
                <svg class="dropdown-arrow" :class="{ open: showAgentDropdown }" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
              <!-- Teleport: escapa el overflow:hidden de los paneles ancestros -->
              <Teleport to="body">
                <div v-if="showAgentDropdown" class="dropdown-menu-global" :style="dropdownGlobalStyle" @keydown.esc="closeAgentDropdown">
                  <div class="dropdown-header-g">{{ $t('step5.selectChatTarget') }}</div>
                  <!-- botones (antes divs): se recorren con Tab y se eligen con Intro -->
                  <button
                    v-for="(agent, idx) in profiles"
                    :key="idx"
                    type="button"
                    class="dropdown-item-g"
                    @click="selectAgent(agent, idx)"
                  >
                    <span class="agent-avatar-g" aria-hidden="true">{{ (agent.username || 'A')[0] }}</span>
                    <span class="agent-info-g">
                      <span class="agent-name-g">{{ agent.username }}</span>
                      <span class="agent-role-g">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                    </span>
                  </button>
                </div>
              </Teleport>
            </div>
            <div class="tab-divider"></div>
            <button
              type="button"
              class="tab-pill explorer-pill"
              data-tour="int-tab-explorer"
              :class="{ active: activeTab === 'explorer' }"
              :aria-pressed="activeTab === 'explorer'"
              :title="$t('step5.tipExplorer')"
              @click="selectExplorerTab"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M2 12h20"></path>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
              </svg>
              <span>{{ $t('step5.worldExplorer') }}</span>
            </button>
            <div class="tab-divider"></div>
            <button
              type="button"
              class="tab-pill survey-pill"
              data-tour="int-tab-survey"
              :class="{ active: activeTab === 'survey' }"
              :aria-pressed="activeTab === 'survey'"
              :title="$t('step5.tipSurvey')"
              @click="selectSurveyTab"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>{{ $t('step5.sendSurvey') }}</span>
            </button>
          </div>
        </div>

        <!-- Chat Mode -->
        <div v-if="activeTab === 'chat'" class="chat-container">

          <!-- Report Agent Tools Card -->
          <div v-if="chatTarget === 'report_agent'" class="report-agent-tools-card">
            <div class="tools-card-header">
              <div class="tools-card-avatar">R</div>
              <div class="tools-card-info">
                <div class="tools-card-name">{{ $t('step5.reportAgentChat') }}</div>
                <div class="tools-card-subtitle">{{ $t('step5.reportAgentDesc') }}</div>
              </div>
              <button
                type="button"
                class="tools-card-toggle"
                :aria-expanded="showToolsDetail"
                :aria-label="showToolsDetail ? $t('step5.hideTools') : $t('step5.showTools')"
                :title="showToolsDetail ? $t('step5.hideTools') : $t('step5.showTools')"
                @click="showToolsDetail = !showToolsDetail"
              >
                <svg :class="{ 'is-expanded': showToolsDetail }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showToolsDetail" class="tools-card-body">
              <div class="tools-grid">
                <div class="tool-item tool-purple">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInsightForge') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInsightForgeDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-blue">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <circle cx="12" cy="12" r="10"></circle>
                      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolPanoramaSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolPanoramaSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-orange">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolQuickSearch') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolQuickSearchDesc') }}</div>
                  </div>
                </div>
                <div class="tool-item tool-green">
                  <div class="tool-icon-wrapper">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                  </div>
                  <div class="tool-content">
                    <div class="tool-name">{{ $t('step5.toolInterviewSubAgent') }}</div>
                    <div class="tool-desc">{{ $t('step5.toolInterviewSubAgentDesc') }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Agent Profile Card -->
          <div v-if="chatTarget === 'agent' && selectedAgent" class="agent-profile-card">
            <div class="profile-card-header">
              <div class="profile-card-avatar">{{ (selectedAgent.username || 'A')[0] }}</div>
              <div class="profile-card-info">
                <div class="profile-card-name">{{ selectedAgent.username }}</div>
                <div class="profile-card-meta">
                  <span v-if="selectedAgent.name" class="profile-card-handle">@{{ selectedAgent.name }}</span>
                  <span class="profile-card-profession">{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                </div>
              </div>
              <button
                type="button"
                class="profile-card-toggle"
                :aria-expanded="showFullProfile"
                :aria-label="showFullProfile ? $t('step5.hideProfile') : $t('step5.showProfile')"
                :title="showFullProfile ? $t('step5.hideProfile') : $t('step5.showProfile')"
                @click="showFullProfile = !showFullProfile"
              >
                <svg :class="{ 'is-expanded': showFullProfile }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>
            </div>
            <div v-if="showFullProfile && selectedAgent.bio" class="profile-card-body">
              <div class="profile-card-bio">
                <div class="profile-card-label">{{ $t('step5.profileBio') }}</div>
                <p>{{ selectedAgent.bio }}</p>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div class="chat-messages" ref="chatMessages">
            <div v-if="chatHistory.length === 0" class="chat-empty">
              <div class="empty-icon">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
              </div>
              <p class="empty-text">
                {{ chatTarget === 'report_agent' ? $t('step5.chatEmptyReportAgent') : $t('step5.chatEmptyAgent') }}
              </p>
            </div>
            <div
              v-for="(msg, idx) in chatHistory"
              :key="idx"
              class="chat-message"
              :class="[msg.role, { 'is-error': msg.error }]"
            >
              <div class="message-avatar" aria-hidden="true">
                <span v-if="msg.role === 'user'">{{ $t('step5.you')[0] }}</span>
                <span v-else>{{ msg.role === 'assistant' && chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="message-header">
                  <span class="sender-name">
                    {{ msg.role === 'user' ? $t('step5.you') : (chatTarget === 'report_agent' ? $t('step5.reportAgentName') : (selectedAgent?.username || $t('step5.agentFallback'))) }}
                  </span>
                  <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
                </div>
                <!-- error: frase clara y el texto técnico plegado -->
                <div v-if="msg.error" class="message-text" role="alert">
                  <p class="md-p">{{ msg.content }}</p>
                  <details v-if="msg.detail" class="notice-details">
                    <summary>{{ $t('main.failDetails') }}</summary>
                    <code>{{ msg.detail }}</code>
                  </details>
                </div>
                <MiniMarkdown v-else-if="msg.role === 'assistant'" class="message-text" :text="msg.content" />
                <div v-else class="message-text is-plain">{{ msg.content }}</div>
              </div>
            </div>
            <div v-if="isSending" class="chat-message assistant" role="status" :aria-label="$t('common.loading')">
              <div class="message-avatar" aria-hidden="true">
                <span>{{ chatTarget === 'report_agent' ? 'R' : (selectedAgent?.username?.[0] || 'A') }}</span>
              </div>
              <div class="message-content">
                <div class="typing-indicator" aria-hidden="true">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Chat Input -->
          <div class="chat-input-area" data-tour="int-chat-input">
            <textarea
              v-model="chatInput"
              class="chat-input"
              :placeholder="$t('step5.chatInputPlaceholder')"
              :aria-label="$t('step5.chatInputPlaceholder')"
              @keydown.enter.exact="onChatEnter"
              :disabled="isSending || (!selectedAgent && chatTarget === 'agent')"
              rows="1"
              ref="chatInputRef"
            ></textarea>
            <button
              type="button"
              class="send-btn"
              :aria-label="$t('step5.sendMessage')"
              :title="$t('step5.sendMessage')"
              @click="sendMessage"
              :disabled="!chatInput.trim() || isSending || (!selectedAgent && chatTarget === 'agent')"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>

        <!-- Survey Mode -->
        <div v-if="activeTab === 'survey'" class="survey-container">
          <!-- Survey Setup -->
          <div class="survey-setup">
            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.selectSurveyTarget') }}</span>
                <span class="selection-count">{{ $t('step5.selectedCount', { selected: selectedAgents.size, total: profiles.length }) }}</span>
              </div>
              <div class="agents-grid">
                <label 
                  v-for="(agent, idx) in profiles" 
                  :key="idx"
                  class="agent-checkbox"
                  :class="{ checked: selectedAgents.has(idx) }"
                >
                  <!-- casilla real (oculta a la vista, no al teclado): con display:none no se podía marcar con Tab + Espacio -->
                  <input
                    type="checkbox"
                    class="checkbox-input"
                    :checked="selectedAgents.has(idx)"
                    @change="toggleAgentSelection(idx)"
                  >
                  <div class="checkbox-avatar" aria-hidden="true">{{ (agent.username || 'A')[0] }}</div>
                  <div class="checkbox-info">
                    <span class="checkbox-name">{{ agent.username }}</span>
                    <span class="checkbox-role">{{ agent.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                  <div class="checkbox-indicator" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                  </div>
                </label>
              </div>
              <div class="selection-actions">
                <button type="button" class="action-link" @click="selectAllAgents">{{ $t('step5.selectAll') }}</button>
                <span class="action-divider" aria-hidden="true"></span>
                <button type="button" class="action-link" @click="clearAgentSelection">{{ $t('step5.clearSelection') }}</button>
              </div>
            </div>

            <div class="setup-section">
              <div class="section-header">
                <span class="section-title">{{ $t('step5.surveyQuestions') }}</span>
              </div>
              <textarea
                v-model="surveyQuestion"
                class="survey-input"
                :placeholder="$t('step5.surveyInputPlaceholder')"
                :aria-label="$t('step5.surveyQuestions')"
                rows="3"
              ></textarea>
            </div>

            <button
              type="button"
              class="survey-submit-btn"
              :disabled="selectedAgents.size === 0 || !surveyQuestion.trim() || isSurveying"
              @click="submitSurvey"
            >
              <span v-if="isSurveying" class="loading-spinner" role="status" :aria-label="$t('common.loading')"></span>
              <span v-else>{{ $t('step5.submitSurvey') }}</span>
            </button>

            <!-- Si falla, se dice (antes solo quedaba en el registro y la pantalla no cambiaba) -->
            <div v-if="surveyError" class="panel-notice is-error survey-error" role="alert">
              <p class="panel-notice-title">{{ $t('step5.surveyFailedTitle') }}</p>
              <p class="panel-notice-text">{{ $t('step5.requestFailedBody') }}</p>
              <details class="notice-details">
                <summary>{{ $t('main.failDetails') }}</summary>
                <code>{{ surveyError }}</code>
              </details>
            </div>
          </div>

          <!-- Survey Results (container closed after this block) -->
          <div v-if="surveyResults.length > 0" class="survey-results">
            <div class="results-header">
              <span class="results-title">{{ $t('step5.surveyResults') }}</span>
              <span class="results-count">{{ $t('step5.surveyResultsCount', { count: surveyResults.length }) }}</span>
            </div>
            <div class="results-list">
              <div 
                v-for="(result, idx) in surveyResults" 
                :key="idx"
                class="result-card"
              >
                <div class="result-header">
                  <div class="result-avatar" aria-hidden="true">{{ (result.agent_name || 'A')[0] }}</div>
                  <div class="result-info">
                    <span class="result-name">{{ result.agent_name }}</span>
                    <span class="result-role">{{ result.profession || $t('step2.unknownProfession') }}</span>
                  </div>
                </div>
                <div class="result-question">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  <span>{{ result.question }}</span>
                </div>
                <MiniMarkdown class="result-answer" :text="result.answer" />
              </div>
            </div>
          </div>
        </div>

        <!-- World Explorer Mode -->
        <div v-if="activeTab === 'explorer'" class="explorer-container">
          <Step5WorldExplorer
            :simulationId="simulationId"
            :profiles="profiles"
            @chat-with-agent="handleExplorerChat"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { chatWithReport, getReport, getAgentLog } from '../api/report'
import ReportDownloads from './ReportDownloads.vue'
import { interviewAgents, getSimulationProfilesRealtime } from '../api/simulation'
import Step5WorldExplorer from './Step5WorldExplorer.vue'
import { MiniMarkdown } from '../lib/miniMarkdown'

// El texto técnico de un fallo (lo que dice el servidor o axios), para el detalle plegado
const errorDetail = (err) => err?.response?.data?.error || err?.message || String(err || '')

const { t } = useI18n()

const props = defineProps({
  reportId: String,
  simulationId: String
})

const emit = defineEmits(['add-log', 'update-status'])

// State
const activeTab = ref('chat')
const chatTarget = ref('report_agent')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)

// Dropdown teleported positioning
const agentPillRef = ref(null)
const dropdownGlobalStyle = ref({})
const selectedAgentIndex = ref(null)
const showFullProfile = ref(true)
// En móvil la tarjeta de herramientas ocupaba ~400 px de 844 y la conversación se quedaba en ~100: arranca plegada (el chevron la abre)
const showToolsDetail = ref(!(typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 700px)').matches))

// Chat State
const chatInput = ref('')
const chatHistory = ref([])
const chatHistoryCache = ref({}) // 缓存所有对话记录: { 'report_agent': [], 'agent_0': [], 'agent_1': [], ... }
const isSending = ref(false)
const chatMessages = ref(null)
const chatInputRef = ref(null)

// Survey State
const selectedAgents = ref(new Set())
const surveyQuestion = ref('')
const surveyResults = ref([])
const isSurveying = ref(false)
const surveyError = ref('')

// Report Data
const reportLoaded = ref(false)      // la carga terminó (con o sin índice)
const reportLoadError = ref('')      // detalle técnico si falló
const reportOutline = ref(null)
const generatedSections = ref({})
const collapsedSections = ref(new Set())
const currentSectionIndex = ref(null)
const profiles = ref([])

// Helper Methods
const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

// Refs
const leftPanel = ref(null)
const rightPanel = ref(null)

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const toggleSectionCollapse = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const selectChatTarget = (target) => {
  chatTarget.value = target
  if (target === 'report_agent') {
    showAgentDropdown.value = false
  }
}

// 保存当前对话记录到缓存
const saveChatHistory = () => {
  if (chatHistory.value.length === 0) return
  
  if (chatTarget.value === 'report_agent') {
    chatHistoryCache.value['report_agent'] = [...chatHistory.value]
  } else if (selectedAgentIndex.value !== null) {
    chatHistoryCache.value[`agent_${selectedAgentIndex.value}`] = [...chatHistory.value]
  }
}

const selectReportAgentChat = () => {
  // 保存当前对话记录
  saveChatHistory()
  
  activeTab.value = 'chat'
  chatTarget.value = 'report_agent'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
  
  // 恢复 Report Agent 的对话记录
  chatHistory.value = chatHistoryCache.value['report_agent'] || []
}

const selectSurveyTab = () => {
  activeTab.value = 'survey'
  selectedAgent.value = null
  selectedAgentIndex.value = null
  showAgentDropdown.value = false
}

const selectExplorerTab = () => {
  saveChatHistory()
  activeTab.value = 'explorer'
  showAgentDropdown.value = false
}

// Invoked when the Explorer's "Chat with this agent" CTA is clicked.
// Jumps back to chat mode with the chosen agent pre-selected.
const handleExplorerChat = (idx) => {
  const agent = profiles.value[idx]
  if (!agent) return
  selectAgent(agent, idx)
  activeTab.value = 'chat'
}

const closeAgentDropdown = () => {
  showAgentDropdown.value = false
  nextTick(() => agentPillRef.value?.focus())
}

const toggleAgentDropdown = () => {
  showAgentDropdown.value = !showAgentDropdown.value
  if (showAgentDropdown.value) {
    activeTab.value = 'chat'
    // NO se cambia `chatTarget` aquí: abrir el menú no es elegir a alguien. Antes se ponía 'agent' al abrirlo, y
    // `selectAgent` guardaba entonces la conversación del agente de informes en la clave equivocada (o en ninguna)
    // Calcular posición del dropdown en coordenadas del viewport (fixed)
    nextTick(() => {
      if (agentPillRef.value) {
        const rect = agentPillRef.value.getBoundingClientRect()
        dropdownGlobalStyle.value = {
          position: 'fixed',
          top: `${rect.bottom + 6}px`,
          right: `${window.innerWidth - rect.right}px`,
          zIndex: 9999
        }
      }
    })
  }
}

const selectAgent = (agent, idx) => {
  // 保存当前对话记录
  saveChatHistory()
  
  selectedAgent.value = agent
  selectedAgentIndex.value = idx
  chatTarget.value = 'agent'
  showAgentDropdown.value = false
  
  // 恢复该 Agent 的对话记录
  chatHistory.value = chatHistoryCache.value[`agent_${idx}`] || []
  addLog(t('log.selectChatTarget', { name: agent.username }))
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit'
    })
  } catch {
    return ''
  }
}

// El Markdown de las respuestas lo pinta MiniMarkdown (lib/miniMarkdown.js): sin v-html, el texto nunca se interpreta como HTML

// Enter envía; con un método de entrada de texto (chino, japonés, coreano) Enter confirma la palabra que se está
// componiendo y NO debe enviar el mensaje a medias
const onChatEnter = (event) => {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  sendMessage()
}

// Chat Methods
// Cada conversación tiene su clave ('report_agent' o 'agent_<n>'). La respuesta llega segundos después y la persona
// puede haber cambiado de interlocutor entretanto: se escribe en la conversación DE LA PREGUNTA, no en la que esté a la vista.
const currentThreadKey = () => (
  chatTarget.value === 'report_agent' ? 'report_agent'
    : (selectedAgentIndex.value !== null ? `agent_${selectedAgentIndex.value}` : null)
)
const appendToThread = (key, message) => {
  if (key === currentThreadKey()) {
    chatHistory.value.push(message)
  } else if (key) {
    chatHistoryCache.value[key] = [...(chatHistoryCache.value[key] || []), message]
  }
}

const sendMessage = async () => {
  if (!chatInput.value.trim() || isSending.value) return
  
  const message = chatInput.value.trim()
  chatInput.value = ''
  const threadKey = currentThreadKey()
  
  // Add user message
  chatHistory.value.push({
    role: 'user',
    content: message,
    timestamp: new Date().toISOString()
  })
  
  scrollToBottom()
  isSending.value = true
  
  try {
    if (chatTarget.value === 'report_agent') {
      await sendToReportAgent(message, threadKey)
    } else {
      await sendToAgent(message, threadKey)
    }
  } catch (err) {
    addLog(t('log.sendFailed', { error: err.message }))
    // Frase clara para la persona; el texto del servidor va plegado como detalle técnico
    appendToThread(threadKey, {
      role: 'assistant',
      error: true,
      content: t('step5.chatFailed'),
      detail: errorDetail(err),
      timestamp: new Date().toISOString()
    })
  } finally {
    isSending.value = false
    scrollToBottom()
    // 自动保存对话记录到缓存
    saveChatHistory()
  }
}

const sendToReportAgent = async (message, threadKey) => {
  addLog(t('log.sendToReportAgent', { message: message.substring(0, 50) }))
  
  // Build chat history for API
  const historyForApi = chatHistory.value
    .filter(msg => !msg.error)   // los avisos de error no son parte de la conversación
    .filter(msg => msg.role !== 'user' || msg.content !== message)
    .slice(-10) // Keep last 10 messages
    .map(msg => ({
      role: msg.role,
      content: msg.content
    }))
  
  const res = await chatWithReport({
    simulation_id: props.simulationId,
    message: message,
    chat_history: historyForApi
  })
  
  if (res.success && res.data) {
    appendToThread(threadKey, {
      role: 'assistant',
      content: res.data.response || res.data.answer || t('step5.noResponse'),
      timestamp: new Date().toISOString()
    })
    addLog(t('log.reportAgentReplied'))
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const sendToAgent = async (message, threadKey) => {
  if (!selectedAgent.value || selectedAgentIndex.value === null) {
    throw new Error(t('step5.selectAgentFirst'))
  }
  // A quién se preguntó, fijado ahora: tras la espera la persona puede haber elegido a otro
  const agentName = selectedAgent.value.username
  const agentId = selectedAgentIndex.value
  
  addLog(t('log.sendToAgent', { name: agentName, message: message.substring(0, 50) }))
  
  // Build prompt with chat history
  let prompt = message
  if (chatHistory.value.length > 1) {
    const historyContext = chatHistory.value
      .filter(msg => !msg.error && msg.content !== message)
      .slice(-6)
      .map(msg => `${msg.role === 'user' ? 'Entrevistador' : 'Tú'}: ${msg.content}`)
      .join('\n')
    prompt = `A continuación está nuestra conversación anterior:\n${historyContext}\n\nAhora mi nueva pregunta es: ${message}`
  }
  
  const res = await interviewAgents({
    simulation_id: props.simulationId,
    interviews: [{
      agent_id: agentId,
      prompt: prompt
    }]
  })
  
  if (res.success && res.data) {
    // 正确的数据路径: res.data.result.results 是一个对象字典
    // 格式: {"twitter_0": {...}, "reddit_0": {...}} 或单平台 {"reddit_0": {...}}
    const resultData = res.data.result || res.data
    const resultsDict = resultData.results || resultData
    
    // 将对象字典转换为数组，优先获取 reddit 平台的回复
    let responseContent = null
    
    if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
      // 优先使用 reddit 平台回复，其次 twitter
      const redditKey = `reddit_${agentId}`
      const twitterKey = `twitter_${agentId}`
      const agentResult = resultsDict[redditKey] || resultsDict[twitterKey] || Object.values(resultsDict)[0]
      if (agentResult) {
        responseContent = agentResult.response || agentResult.answer
      }
    } else if (Array.isArray(resultsDict) && resultsDict.length > 0) {
      // 兼容数组格式
      responseContent = resultsDict[0].response || resultsDict[0].answer
    }
    
    if (responseContent) {
      appendToThread(threadKey, {
        role: 'assistant',
        content: responseContent,
        timestamp: new Date().toISOString()
      })
      addLog(t('log.agentReplied', { name: agentName }))
    } else {
      throw new Error(t('step5.noResponse'))
    }
  } else {
    throw new Error(res.error || t('step5.requestFailed'))
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// Survey Methods
const toggleAgentSelection = (idx) => {
  const newSet = new Set(selectedAgents.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  selectedAgents.value = newSet
}

const selectAllAgents = () => {
  const newSet = new Set()
  profiles.value.forEach((_, idx) => newSet.add(idx))
  selectedAgents.value = newSet
}

const clearAgentSelection = () => {
  selectedAgents.value = new Set()
}

const submitSurvey = async () => {
  if (selectedAgents.value.size === 0 || !surveyQuestion.value.trim()) return
  
  isSurveying.value = true
  surveyError.value = ''
  addLog(t('log.sendSurvey', { count: selectedAgents.value.size }))
  
  try {
    const interviews = Array.from(selectedAgents.value).map(idx => ({
      agent_id: idx,
      prompt: surveyQuestion.value.trim()
    }))
    
    const res = await interviewAgents({
      simulation_id: props.simulationId,
      interviews: interviews
    })
    
    if (res.success && res.data) {
      // 正确的数据路径: res.data.result.results 是一个对象字典
      // 格式: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
      const resultData = res.data.result || res.data
      const resultsDict = resultData.results || resultData
      
      // 将对象字典转换为数组格式
      const surveyResultsList = []
      
      for (const interview of interviews) {
        const agentIdx = interview.agent_id
        const agent = profiles.value[agentIdx]
        
        // 优先使用 reddit 平台回复，其次 twitter
        let responseContent = t('step5.noResponse')

        if (typeof resultsDict === 'object' && !Array.isArray(resultsDict)) {
          const redditKey = `reddit_${agentIdx}`
          const twitterKey = `twitter_${agentIdx}`
          const agentResult = resultsDict[redditKey] || resultsDict[twitterKey]
          if (agentResult) {
            responseContent = agentResult.response || agentResult.answer || t('step5.noResponse')
          }
        } else if (Array.isArray(resultsDict)) {
          // 兼容数组格式
          const matchedResult = resultsDict.find(r => r.agent_id === agentIdx)
          if (matchedResult) {
            responseContent = matchedResult.response || matchedResult.answer || t('step5.noResponse')
          }
        }
        
        surveyResultsList.push({
          agent_id: agentIdx,
          agent_name: agent?.username || `Agent ${agentIdx}`,
          profession: agent?.profession,
          question: surveyQuestion.value.trim(),
          answer: responseContent
        })
      }
      
      surveyResults.value = surveyResultsList
      addLog(t('log.receivedReplies', { count: surveyResults.value.length }))
    } else {
      throw new Error(res.error || t('step5.requestFailed'))
    }
  } catch (err) {
    addLog(t('log.surveySendFailed', { error: err.message }))
    surveyError.value = errorDetail(err)
  } finally {
    isSurveying.value = false
  }
}

// Load Report Data
const loadReportData = async () => {
  if (!props.reportId) return
  
  reportLoadError.value = ''
  try {
    addLog(t('log.loadReportData', { id: props.reportId }))

    // Get report info
    const reportRes = await getReport(props.reportId)
    if (reportRes.success && reportRes.data) {
      // Load agent logs to get report outline and sections
      await loadAgentLogs()
    }
  } catch (err) {
    addLog(t('log.loadReportFailed', { error: err.message }))
    reportLoadError.value = errorDetail(err)
  } finally {
    reportLoaded.value = true
  }
}

const loadAgentLogs = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, 0)
    if (res.success && res.data) {
      const logs = res.data.logs || []
      
      logs.forEach(log => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          reportOutline.value = log.details.outline
        }
        
        if (log.action === 'section_complete' && log.section_index < 100 && log.details?.content) {
          generatedSections.value[log.section_index] = log.details.content
        }
      })
      
      addLog(t('log.reportDataLoaded'))
    }
  } catch (err) {
    addLog(t('log.loadReportLogFailed', { error: err.message }))
    reportLoadError.value = errorDetail(err)
  }
}

const loadProfiles = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')
    if (res.success && res.data) {
      profiles.value = res.data.profiles || []
      addLog(t('log.loadedProfiles', { count: profiles.value.length }))
    }
  } catch (err) {
    addLog(t('log.loadProfilesFailed', { error: err.message }))
  }
}

// Click outside to close dropdown (incluye el menú teleportado al body)
const handleClickOutside = (e) => {
  const trigger = document.querySelector('.agent-dropdown')
  const menu = document.querySelector('.dropdown-menu-global')
  const clickedInsideTrigger = trigger && trigger.contains(e.target)
  const clickedInsideMenu = menu && menu.contains(e.target)
  if (!clickedInsideTrigger && !clickedInsideMenu) {
    showAgentDropdown.value = false
  }
}

// Lifecycle
onMounted(() => {
  addLog(t('log.step5Init'))
  loadReportData()
  loadProfiles()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    loadReportData()
  }
}, { immediate: true })

watch(() => props.simulationId, (newId) => {
  if (newId) {
    loadProfiles()
  }
}, { immediate: true })
</script>

<style scoped>
.interaction-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--kb-surface-2);
  font-family: var(--kb-font-sans);
  overflow: hidden;
}

/* Utility Classes */
.mono {
  font-family: var(--kb-font-mono);
}

/* Main Split Layout */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Panel - Report Style (与 Step4Report.vue 完全一致) */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: #FFFFFF;
  border-right: 1px solid var(--kb-line);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 30px 50px 60px 50px;
}

.left-panel::-webkit-scrollbar {
  width: 6px;
}

.left-panel::-webkit-scrollbar-track {
  background: transparent;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  border-radius: 3px;
  transition: background 0.3s ease;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* Report Header */
.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: 30px;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 12px;
  margin-bottom: 24px;
}

.report-tag {
  background: var(--kb-text);
  color: #FFFFFF;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.report-id {
  font-size: 12px;
  color: var(--kb-subtle);
  font-weight: 500;
  letter-spacing: 0.02em;
  overflow-wrap: anywhere;
}

.main-title {
  font-family: var(--kb-font-sans);
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 800;
  color: var(--kb-text);
  line-height: 1.15;
  margin: 0 0 16px 0;
  letter-spacing: -0.02em;
  text-wrap: balance;
  /* Un título de 7 líneas ocupaba medio panel: máximo 3 */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.sub-title {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  color: var(--kb-muted);
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 30px 0;
  font-weight: 400;
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
  gap: 32px;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  transition: background-color 0.2s ease;
  padding: 8px 12px;
  margin: -8px -12px;
  border-radius: 8px;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: var(--kb-surface-2);
}

.collapse-btn {
  margin-left: auto;
  flex-shrink: 0;
  align-self: center;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: none;
  border: 0;
  border-radius: 6px;
  color: var(--kb-subtle);
  cursor: pointer;
}

.collapse-btn:hover { color: var(--kb-text); }

.collapse-icon {
  transition: transform 0.3s ease;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

/* Número de sección: --kb-muted también en las pendientes (el #DDD daba 1,36:1) */
.section-number {
  font-family: var(--kb-font-sans);
  font-size: 16px;
  color: var(--kb-muted);
  font-weight: 500;
  transition: color 0.3s ease;
}

.section-title {
  font-family: var(--kb-font-sans);
  font-size: 24px;
  font-weight: 600;
  color: var(--kb-text);
  margin: 0;
  overflow-wrap: anywhere;
  transition: color 0.3s ease;
}

/* States */
.report-section-item.is-pending .section-number {
  color: var(--kb-muted);
}
.report-section-item.is-pending .section-title {
  color: var(--kb-muted);
}

.report-section-item.is-active .section-number,
.report-section-item.is-completed .section-number {
  color: var(--kb-subtle);
}

.report-section-item.is-active .section-title,
.report-section-item.is-completed .section-title {
  color: var(--kb-text);
}

.section-body {
  padding-left: 28px;
  overflow: hidden;
}

/* Generated Content */
.generated-content {
  font-family: var(--kb-font-sans);
  font-size: 14px;
  line-height: 1.8;
  color: var(--kb-text-2);
  overflow-wrap: anywhere;
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: var(--kb-font-sans);
  color: var(--kb-text);
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 700;
}

.generated-content :deep(.md-h2) { font-size: 20px; border-bottom: 1px solid var(--kb-soft); padding-bottom: 8px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: 20px;
  margin-bottom: 1em;
}

.generated-content :deep(.md-li) {
  margin-bottom: 0.5em;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid var(--kb-line);
  padding-left: 16px;
  margin: 1.5em 0;
  color: var(--kb-muted);
  font-style: italic;
  font-family: var(--kb-font-sans);
}

.generated-content :deep(.code-block) {
  background: var(--kb-surface-2);
  padding: 12px;
  border-radius: 6px;
  font-family: var(--kb-font-mono);
  font-size: 12px;
  overflow-x: auto;
  margin: 1em 0;
  border: 1px solid var(--kb-line);
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: var(--kb-text);
}

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--kb-muted);
  font-size: 14px;
  margin-top: 4px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-text {
  font-family: var(--kb-font-sans);
  font-size: 15px;
  color: var(--kb-text-2);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Content Styles Override */
.generated-content :deep(.md-h2) {
  font-family: var(--kb-font-sans);
  font-size: 18px;
  margin-top: 0;
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
  color: var(--kb-subtle);
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
  border: 2px solid var(--kb-line);
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text {
  font-size: 14px;
}

/* Avisos del panel (informe sin cargar, sin contenido, encuesta fallida): frase clara + detalle plegado */
.panel-notice {
  margin: 24px auto 0;
  max-width: 520px;
  padding: 16px 18px;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-radius: 8px;
}
.panel-notice.is-error { border-color: var(--kb-danger-line); border-left-width: 4px; }
.panel-notice-title { margin: 0 0 4px; font-size: 14px; font-weight: 700; color: var(--kb-text); }
.panel-notice-text { margin: 0; font-size: 13px; line-height: 1.5; color: var(--kb-text-2); }
.notice-details { margin-top: 8px; font-size: 12px; color: var(--kb-muted); }
.notice-details summary { cursor: pointer; }
.notice-details code {
  display: block; margin-top: 6px; padding: 8px 10px; white-space: pre-wrap;
  background: var(--kb-surface-2); border: 1px solid var(--kb-line); border-radius: 6px;
  font-family: var(--kb-font-mono); font-size: 12px; color: var(--kb-text-2); overflow-wrap: anywhere;
}
.survey-error { margin: 16px 0 0; max-width: none; }

/* Right Panel - Interaction */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  overflow: hidden;
}

/* Action Bar - Professional Design */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--kb-line);
  background: var(--kb-surface);
  gap: 16px;
  position: relative;
  z-index: 50;
}

.action-bar-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 160px;
}

.action-bar-icon {
  color: var(--kb-text);
  flex-shrink: 0;
}

.action-bar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-bar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
  letter-spacing: -0.01em;
}

.action-bar-subtitle {
  font-size: 12px;
  color: var(--kb-subtle);
}

.action-bar-subtitle.mono {
  font-family: var(--kb-font-mono);
}

.action-bar-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1 1 0;
  min-width: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 6px;
}

/* Pestañas: la elegida en lima claro con filete de tinta (el estado se ve con ≥ 3:1);
   el único relleno en tinta de la vista es la acción (Enviar) */
.tab-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  border: 1px solid transparent;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.tab-pill:hover {
  background: var(--kb-line);
  color: var(--kb-text);
}

.tab-pill.active {
  background: var(--kb-accent-subtle);
  color: var(--kb-text);
  border-color: var(--kb-text);
  font-weight: 600;
}

.tab-pill svg {
  flex-shrink: 0;
}

.tab-divider {
  width: 1px;
  height: 24px;
  background: var(--kb-line);
  margin: 0 6px;
}

.agent-pill {
  width: 200px;
  justify-content: space-between;
}

.agent-pill span {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

/* «Enviar encuesta» es una pestaña más (antes, verde ajeno a la marca): mismo aspecto que las demás */

/* Interaction Header */
.interaction-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--kb-line);
  background: var(--kb-surface-2);
}

.tab-switcher {
  display: flex;
  gap: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-muted);
  background: transparent;
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: var(--kb-surface-2);
  border-color: var(--kb-line-strong);
}

.tab-btn.active {
  background: var(--kb-text);
  color: #FFFFFF;
  border-color: var(--kb-text);
}

.tab-btn svg {
  flex-shrink: 0;
}

/* Chat Container */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Report Agent Tools Card */
/* Fondo liso (el degradado hacia --kb-soft dejaba el texto gris por debajo de 4,5:1 en la esquina) */
.report-agent-tools-card {
  border-bottom: 1px solid var(--kb-line);
  background: var(--kb-surface-2);
}

.tools-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
}

.tools-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: linear-gradient(135deg, var(--kb-text) 0%, var(--kb-text-2) 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.2);
}

.tools-card-info {
  flex: 1;
  min-width: 0;
}

.tools-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--kb-text);
  margin-bottom: 2px;
}

.tools-card-subtitle {
  font-size: 12px;
  color: var(--kb-muted);
}

.tools-card-toggle {
  width: 28px;
  height: 28px;
  background: #FFFFFF;
  border: 1px solid var(--kb-control-line);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--kb-muted);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.tools-card-toggle:hover {
  background: var(--kb-surface-2);
  border-color: var(--kb-line-strong);
}

.tools-card-toggle svg {
  transition: transform 0.3s ease;
}

.tools-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.tools-card-body {
  padding: 0 20px 16px 20px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.tool-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: #FFFFFF;
  border-radius: 10px;
  border: 1px solid var(--kb-line);
  transition: all 0.2s ease;
}

.tool-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tool-icon-wrapper {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* Las cuatro herramientas se distinguen por su icono y su nombre; el color es el de la marca para todas
   (antes, morado/azul/naranja/verde ajenos a la paleta) */
.tool-purple .tool-icon-wrapper,
.tool-blue .tool-icon-wrapper,
.tool-orange .tool-icon-wrapper,
.tool-green .tool-icon-wrapper {
  background: var(--kb-accent-subtle);
  color: var(--kb-accent-text);
}

.tool-content {
  flex: 1;
  min-width: 0;
}

.tool-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text);
  margin-bottom: 4px;
}

.tool-desc {
  font-size: 12px;
  color: var(--kb-muted);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent Profile Card */
.agent-profile-card {
  border-bottom: 1px solid var(--kb-line);
  background: var(--kb-surface-2);
}

.profile-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
}

.profile-card-avatar {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  background: linear-gradient(135deg, var(--kb-text) 0%, var(--kb-text-2) 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(31, 41, 55, 0.2);
}

.profile-card-info {
  flex: 1;
  min-width: 0;
}

.profile-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--kb-text);
  margin-bottom: 2px;
}

.profile-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--kb-muted);
}

.profile-card-handle {
  color: var(--kb-subtle);
}

.profile-card-profession {
  padding: 2px 8px;
  background: var(--kb-soft);
  color: var(--kb-text-on-soft);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.profile-card-toggle {
  width: 28px;
  height: 28px;
  background: #FFFFFF;
  border: 1px solid var(--kb-control-line);
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--kb-muted);
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.profile-card-toggle:hover {
  background: var(--kb-surface-2);
  border-color: var(--kb-line-strong);
}

.profile-card-toggle svg {
  transition: transform 0.3s ease;
}

.profile-card-toggle svg.is-expanded {
  transform: rotate(180deg);
}

.profile-card-body {
  padding: 0 20px 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.profile-card-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.profile-card-bio {
  background: #FFFFFF;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid var(--kb-line);
}

.profile-card-bio p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--kb-text-2);
}

/* Target Selector */
.target-selector {
  padding: 16px 24px;
  border-bottom: 1px solid var(--kb-line);
}

.selector-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 10px;
}

.selector-options {
  display: flex;
  gap: 12px;
}

.target-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--kb-text-2);
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.target-option:hover {
  border-color: var(--kb-line-strong);
}

.target-option.active {
  background: var(--kb-text);
  color: #FFFFFF;
  border-color: var(--kb-text);
}

/* Agent Dropdown */
.agent-dropdown {
  position: relative;
}

.dropdown-arrow {
  margin-left: 4px;
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 260px;
  background: #FFFFFF;
  border: 1px solid var(--kb-line);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12), 0 4px 12px rgba(0, 0, 0, 0.06);
  max-height: 320px;
  overflow-y: auto;
  z-index: 100;
}

.dropdown-header {
  padding: 12px 16px 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--kb-soft);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.15s ease;
  border-left: 3px solid transparent;
}

.dropdown-item:hover {
  background: var(--kb-surface-2);
  border-left-color: var(--kb-text);
}

.dropdown-item:first-of-type {
  margin-top: 4px;
}

.dropdown-item:last-child {
  margin-bottom: 4px;
}

.agent-avatar {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  background: linear-gradient(135deg, var(--kb-text) 0%, var(--kb-text-2) 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(31, 41, 55, 0.1);
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-role {
  font-size: 11px;
  color: var(--kb-subtle);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Chat Messages */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--kb-subtle);
}

.empty-icon {
  opacity: 0.3;
}

.empty-text {
  font-size: 14px;
  text-align: center;
  max-width: 280px;
  line-height: 1.6;
}

.chat-message {
  display: flex;
  gap: 12px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.chat-message.user .message-avatar {
  background: var(--kb-text);
  color: #FFFFFF;
}

.chat-message.assistant .message-avatar {
  background: var(--kb-soft);
  color: var(--kb-text-2);
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat-message.user .message-content {
  align-items: flex-end;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-message.user .message-header {
  flex-direction: row-reverse;
}

.sender-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.message-time {
  font-size: 12px;
  color: var(--kb-subtle);
}

.message-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.message-text.is-plain { white-space: pre-wrap; }

.chat-message.assistant.is-error .message-text {
  background: var(--kb-surface);
  border: 1px solid var(--kb-danger-line);
}

.chat-message.user .message-text {
  background: var(--kb-text);
  color: #FFFFFF;
  border-bottom-right-radius: 4px;
}

.chat-message.assistant .message-text {
  background: var(--kb-soft);
  color: var(--kb-text-2);
  border-bottom-left-radius: 4px;
}

.message-text :deep(.md-p) {
  margin: 0;
}

.message-text :deep(.md-p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(.md-p + .md-p) {
  margin-top: 8px;
}

.message-text :deep(strong) {
  font-weight: 700;
  color: var(--kb-text);
}

.chat-message.user .message-text :deep(strong) {
  color: inherit;
}

/* 修复有序列表编号 - 使用 CSS 计数器让多个 ol 连续编号 */
.message-text {
  counter-reset: list-counter;
}

.message-text :deep(.md-ol) {
  list-style: none;
  padding-left: 0;
  margin: 8px 0;
}

.message-text :deep(.md-oli) {
  counter-increment: list-counter;
  display: flex;
  gap: 8px;
  margin: 4px 0;
}

.message-text :deep(.md-oli)::before {
  content: counter(list-counter) ".";
  font-weight: 600;
  color: var(--kb-text-2);
  min-width: 20px;
  flex-shrink: 0;
}

/* 无序列表样式 */
.message-text :deep(.md-ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-text :deep(.md-li) {
  margin: 4px 0;
}

/* Typing Indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: var(--kb-soft);
  border-radius: 12px;
  border-bottom-left-radius: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--kb-subtle);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) { animation-delay: 0s; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

/* Chat Input: campo y botón con la misma altura (44 px) y el mismo centro;
   borde de control (3,69:1) y foco visible al momento (la transición del borde hacía que, al enfocar, no cambiara nada) */
.chat-input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--kb-line);
  display: flex;
  gap: 12px;
  align-items: center;
}

.chat-input {
  flex: 1;
  box-sizing: border-box;
  height: 44px;
  padding: 10px 16px;
  font-size: 14px;
  border: 1px solid var(--kb-control-line);
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.chat-input:focus {
  border-color: var(--kb-text);
}

.chat-input:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
}

.chat-input:disabled {
  background: var(--kb-surface-2);
  cursor: not-allowed;
}

.send-btn {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  background: var(--kb-text);
  color: #FFFFFF;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.send-btn:hover:not(:disabled) {
  background: var(--kb-text-2);
}

.send-btn:disabled {
  background: var(--kb-line);
  color: var(--kb-subtle);
  cursor: not-allowed;
}

/* Survey Container: todo el panel se desplaza (al llegar los resultados, la rejilla de destinatarios se quedaba en una franja de 20 px) */
.survey-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.explorer-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #FFFFFF;
}

.survey-setup {
  flex: none;
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-bottom: 1px solid var(--kb-line);
}

.setup-section {
  margin-bottom: 24px;
}

.setup-section:first-child {
  display: flex;
  flex-direction: column;
}

.setup-section:last-child {
  margin-bottom: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.setup-section .section-header .section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.selection-count {
  font-size: 12px;
  color: var(--kb-subtle);
}

/* Agents Grid */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
  padding: 4px;
  align-content: start;
}

.agent-checkbox {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.agent-checkbox:hover {
  border-color: var(--kb-control-line);
}

/* Marcado: borde de tinta + casilla rellena con ✓ (forma, no solo color) */
.agent-checkbox.checked {
  background: var(--kb-accent-subtle);
  border-color: var(--kb-text);
}

.agent-checkbox:focus-within {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
}

.agent-checkbox .checkbox-input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: 0;
  pointer-events: none;
}

.checkbox-avatar {
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  background: var(--kb-line);
  color: var(--kb-text-2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.agent-checkbox.checked .checkbox-avatar {
  background: var(--kb-text);
  color: #FFFFFF;
}

.checkbox-info {
  flex: 1;
  min-width: 0;
}

.checkbox-name {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-role {
  display: block;
  font-size: 12px;
  color: var(--kb-subtle);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkbox-indicator {
  width: 20px;
  height: 20px;
  border: 2px solid var(--kb-control-line);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator {
  background: var(--kb-text);
  border-color: var(--kb-text);
  color: #FFFFFF;
}

.checkbox-indicator svg {
  opacity: 0;
  transform: scale(0.5);
  transition: all 0.2s ease;
}

.agent-checkbox.checked .checkbox-indicator svg {
  opacity: 1;
  transform: scale(1);
}

.selection-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

/* 24 px de alto como mínimo (WCAG 2.5.8): antes eran 15 px y estaban pegados */
.action-link {
  min-height: 24px;
  font-family: inherit;
  font-size: 12px;
  color: var(--kb-muted);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0 6px;
}

.action-link:hover {
  color: var(--kb-text);
  text-decoration: underline;
}

.action-divider {
  width: 1px;
  height: 14px;
  background: var(--kb-line-strong);
}

/* Survey Input */
.survey-input {
  width: 100%;
  box-sizing: border-box;
  padding: 14px 16px;
  font-size: 14px;
  border: 1px solid var(--kb-control-line);
  border-radius: 8px;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.survey-input:focus {
  border-color: var(--kb-text);
}

.survey-input:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: 2px;
}

.survey-submit-btn {
  width: 100%;
  padding: 14px 24px;
  font-size: 14px;
  font-weight: 600;
  color: #FFFFFF;
  background: var(--kb-text);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
}

.survey-submit-btn:hover:not(:disabled) {
  background: var(--kb-text-2);
}

.survey-submit-btn:disabled {
  background: var(--kb-line);
  color: var(--kb-subtle);
  cursor: not-allowed;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FFFFFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Survey Results */
.survey-results {
  flex: none;
  padding: 24px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.results-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text);
}

.results-count {
  font-size: 12px;
  color: var(--kb-subtle);
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-card {
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  border-radius: 12px;
  padding: 20px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  background: var(--kb-text);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text);
}

.result-role {
  font-size: 12px;
  color: var(--kb-subtle);
}

.result-question {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: #FFFFFF;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--kb-muted);
}

.result-question svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.result-answer {
  font-size: 14px;
  line-height: 1.7;
  color: var(--kb-text-2);
}

/* Markdown Styles */
:deep(.md-p) {
  margin: 0 0 12px 0;
}

:deep(.md-h2) {
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-text);
  margin: 24px 0 12px 0;
}

:deep(.md-h3) {
  font-size: 16px;
  font-weight: 600;
  color: var(--kb-text-2);
  margin: 20px 0 10px 0;
}

:deep(.md-h4) {
  font-size: 14px;
  font-weight: 600;
  color: var(--kb-text-2);
  margin: 16px 0 8px 0;
}

:deep(.md-h5) {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-muted);
  margin: 12px 0 6px 0;
}

:deep(.md-ul), :deep(.md-ol) {
  margin: 12px 0;
  padding-left: 24px;
}

:deep(.md-li), :deep(.md-oli) {
  margin: 6px 0;
}

/* 聊天/问卷区域的引用样式 */
.chat-messages :deep(.md-quote),
.result-answer :deep(.md-quote) {
  margin: 12px 0;
  padding: 12px 16px;
  background: var(--kb-surface-2);
  border-left: 3px solid var(--kb-text);
  color: var(--kb-text-2);
}

:deep(.code-block) {
  margin: 12px 0;
  padding: 12px 16px;
  background: var(--kb-text);
  border-radius: 6px;
  overflow-x: auto;
}

:deep(.code-block code) {
  font-family: var(--kb-font-mono);
  font-size: 13px;
  color: var(--kb-line);
}

:deep(.inline-code) {
  font-family: var(--kb-font-mono);
  font-size: 13px;
  background: var(--kb-soft);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--kb-text);
}

:deep(.md-hr) {
  border: none;
  border-top: 1px solid var(--kb-line);
  margin: 24px 0;
}

/* Pantallas estrechas: informe arriba y conversación debajo, en una sola columna que se desplaza */
@media (max-width: 900px) {
  .main-split-layout { flex-direction: column; overflow-y: auto; }
  .left-panel.report-style { width: 100%; min-width: 0; flex: none; padding: 22px 18px 32px; border-right: 0; border-bottom: 1px solid var(--kb-line); overflow-y: visible; }
  .right-panel { flex: none; height: 82vh; min-height: 460px; }
}

/* Móvil: la barra de herramientas pasa a columna (título, luego botones en filas) y los separadores, que quedaban sueltos al partir la fila, se quitan */
@media (max-width: 700px) {
  .action-bar { flex-direction: column; align-items: stretch; gap: 10px; padding: 12px 16px; }
  .action-bar-tabs { justify-content: flex-start; flex: none; }
  .tab-divider { display: none; }
}

/* Nombres de agente: los modelos los generan con guiones bajos y sin espacios («marca_que_busca_proyectar_modernidad_…»),
   y una palabra sin huecos no parte nunca: salía por el borde del panel. Parten donde haga falta. */
.agent-name-g,
.profile-card-name,
.profile-card-handle,
.checkbox-name,
.result-name {
  overflow-wrap: anywhere;
  min-width: 0;
}
</style>

<style>
/* English locale: smaller report title */
html[lang="en"] .report-header-block .main-title {
  font-size: 28px;
}

/* ── Dropdown teleportado al body (sin scoped, para escapar overflow:hidden) ── */
.dropdown-menu-global {
  min-width: 260px;
  background: #FFFFFF;
  border: 1px solid var(--kb-line);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.12), 0 4px 12px rgba(0,0,0,0.06);
  max-height: 320px;
  overflow-y: auto;
  font-family: var(--kb-font-sans);
}

.dropdown-header-g {
  padding: 12px 16px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--kb-soft);
}

.dropdown-item-g {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s ease, border-left-color 0.15s ease;
  background: none;
  border: 0;
  border-left: 3px solid transparent;
  font: inherit;
  color: inherit;
  text-align: left;
}

.dropdown-item-g:hover,
.dropdown-item-g:focus-visible {
  background: var(--kb-surface-2);
  border-left-color: var(--kb-text);
}

.dropdown-item-g:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: -2px;
}

.dropdown-item-g:first-of-type { margin-top: 4px; }
.dropdown-item-g:last-child    { margin-bottom: 4px; }

.agent-avatar-g {
  width: 32px;
  height: 32px;
  min-width: 32px;
  background: linear-gradient(135deg, var(--kb-text) 0%, var(--kb-text-2) 100%);
  color: #FFFFFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.agent-info-g {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.agent-name-g {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-role-g {
  font-size: 12px;
  color: var(--kb-subtle);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
