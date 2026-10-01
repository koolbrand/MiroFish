<template>
  <div class="simulation-panel">
    <!-- Top Control Bar -->
    <div class="control-bar" data-tour="run-control-bar">
      <div class="status-group">
        <!-- Twitter 平台进度 -->
        <div class="platform-status twitter" :class="{ active: runStatus.twitter_running, completed: runStatus.twitter_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            <span class="platform-name">{{ $t('step3.platformTwitter') }}</span>
            <span v-if="runStatus.twitter_completed" class="status-badge" role="img" :aria-label="$t('common.completed')" :title="$t('common.completed')">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statRound') }}</span>
              <span class="stat-value mono">{{ runStatus.twitter_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statTime') }}</span>
              <span class="stat-value mono">{{ twitterElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statActs') }}</span>
              <span class="stat-value mono">{{ runStatus.twitter_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- 可用动作提示 -->
          <div class="actions-tooltip">
            <div class="tooltip-title">{{ $t('ui.availableActions') }}</div>
            <div class="tooltip-actions">
              <span v-for="a in ['CREATE_POST', 'LIKE_POST', 'REPOST', 'QUOTE_POST', 'FOLLOW', 'DO_NOTHING']" :key="a" class="tooltip-action">{{ getActionTypeLabel(a) }}</span>
            </div>
          </div>
        </div>

        <!-- Reddit 平台进度 -->
        <div class="platform-status reddit" :class="{ active: runStatus.reddit_running, completed: runStatus.reddit_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            <span class="platform-name">{{ $t('step3.platformReddit') }}</span>
            <span v-if="runStatus.reddit_completed" class="status-badge" role="img" :aria-label="$t('common.completed')" :title="$t('common.completed')">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statRound') }}</span>
              <span class="stat-value mono">{{ runStatus.reddit_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statTime') }}</span>
              <span class="stat-value mono">{{ redditElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">{{ $t('step3.statActs') }}</span>
              <span class="stat-value mono">{{ runStatus.reddit_actions_count || 0 }}</span>
            </span>
          </div>
          <!-- 可用动作提示 -->
          <div class="actions-tooltip">
            <div class="tooltip-title">{{ $t('ui.availableActions') }}</div>
            <div class="tooltip-actions">
              <span v-for="a in ['CREATE_POST', 'CREATE_COMMENT', 'LIKE_POST', 'DOWNVOTE_POST', 'SEARCH_POSTS', 'TREND', 'FOLLOW', 'MUTE', 'REFRESH', 'DO_NOTHING']" :key="a" class="tooltip-action">{{ getActionTypeLabel(a) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="action-controls" data-tour="run-actions">
        <!-- Stop button — compact icon-only while simulation is running -->
        <button
          v-if="phase === 1 && !autoRunning"
          class="action-btn danger icon-only"
          :disabled="isStopping"
          :title="isStopping ? $t('common.processing') : $t('step3.stopSimulation')"
          :aria-label="$t('step3.stopSimulation')"
          @click="handleStopSimulation"
        >
          <span v-if="isStopping" class="loading-spinner-small"></span>
          <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="1"></rect>
          </svg>
        </button>

        <!-- Restart button — solo visible cuando la simulación ya terminó.
             Reemplaza el reinicio automático que antes ocurría al navegar a Step3. -->
        <button
          v-if="phase === 2 && !hasReport && !autoRunning"
          class="action-btn secondary icon-only"
          :disabled="isStarting"
          :title="$t('step3.restartSimulation', 'Restart simulation')"
          :aria-label="$t('step3.restartSimulation', 'Restart simulation')"
          @click="handleRestartSimulation"
        >
          <span v-if="isStarting" class="loading-spinner-small"></span>
          <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
        </button>

        <!-- Con informe ya hecho se abre (no se regenera); en automático lo genera el servidor -->
        <button
          v-if="hasReport"
          class="action-btn primary"
          @click="openReport"
        >
          {{ $t('step3.viewReportBtn') }} <span class="arrow-icon">→</span>
        </button>
        <span v-else-if="autoRunning" class="auto-chip">{{ $t('auto.step3Note') }}</span>
        <button
          v-else
          class="action-btn primary"
          :disabled="phase !== 2 || isGeneratingReport"
          @click="handleNextStep"
        >
          <span v-if="isGeneratingReport" class="loading-spinner-small"></span>
          {{ isGeneratingReport ? $t('step3.generatingReportBtn') : $t('step3.startGenerateReportBtn') }}
          <span v-if="!isGeneratingReport" class="arrow-icon">→</span>
        </button>
      </div>
    </div>

    <!-- Main Content: Dual Timeline -->
    <div class="main-content-area" ref="scrollContainer" data-tour="run-timeline">
      <!-- Timeline Header -->
      <div class="timeline-header" v-if="allActions.length > 0">
        <div class="timeline-stats">
          <span class="total-count">
            {{ $t('step3.totalEvents') }}:
            <span class="mono">{{ filteredActionsCount }}</span>
            <span v-if="hasActiveFilters" class="stats-total-hint">/ {{ allActions.length }}</span>
          </span>
          <span class="platform-breakdown">
            <span class="breakdown-item twitter" :title="$t('step3.platformTwitter')">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
              <span class="sr-only">{{ $t('step3.platformTwitter') }}:</span>
              <span class="mono">{{ twitterActionsCount }}</span>
            </span>
            <span class="breakdown-divider" aria-hidden="true"></span>
            <span class="breakdown-item reddit" :title="$t('step3.platformReddit')">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
              <span class="sr-only">{{ $t('step3.platformReddit') }}:</span>
              <span class="mono">{{ redditActionsCount }}</span>
            </span>
          </span>
        </div>
      </div>

      <!-- Feed Filters -->
      <div class="feed-filters" v-if="allActions.length > 0">
        <div class="filter-group">
          <span class="filter-label">{{ $t('step3.filterPlatform') }}</span>
          <button
            v-for="opt in [
              { key: 'all', label: $t('step3.filterAll') },
              { key: 'twitter', label: $t('step3.platformTwitter') },
              { key: 'reddit', label: $t('step3.platformReddit') }
            ]"
            :key="opt.key"
            type="button"
            class="filter-chip"
            :class="{ active: feedFilters.platform === opt.key }"
            :aria-pressed="feedFilters.platform === opt.key"
            @click="feedFilters.platform = opt.key"
          >
            {{ opt.label }}
          </button>
        </div>

        <div class="filter-group">
          <span class="filter-label">{{ $t('step3.filterActionType') }}</span>
          <button
            v-for="opt in [
              { key: 'all', label: $t('step3.filterAll') },
              { key: 'posts', label: $t('step3.filterGroupPosts') },
              { key: 'interactions', label: $t('step3.filterGroupInteractions') },
              { key: 'comments', label: $t('step3.filterGroupComments') }
            ]"
            :key="opt.key"
            type="button"
            class="filter-chip"
            :class="{ active: feedFilters.actionGroup === opt.key }"
            :aria-pressed="feedFilters.actionGroup === opt.key"
            @click="feedFilters.actionGroup = opt.key"
          >
            {{ opt.label }}
          </button>
        </div>

        <div class="filter-search">
          <svg class="search-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input
            type="text"
            v-model="feedFilters.query"
            :placeholder="$t('step3.searchFeedPlaceholder')"
            :aria-label="$t('step3.searchFeedPlaceholder')"
          />
          <button
            v-if="hasActiveFilters"
            type="button"
            class="clear-filters-btn"
            @click="clearFeedFilters"
            :title="$t('step3.clearFilters')"
          >
            {{ $t('step3.clearFilters') }}
          </button>
        </div>
      </div>
      
      <!-- Si falla el arranque o la ejecución: una frase clara y el detalle técnico plegado (no tapa lo ya simulado) -->
      <div v-if="startError" class="feed-error" role="alert">
        <p class="feed-error-title">{{ phase === 2 ? $t('step3.runFailedTitle') : $t('step3.startFailedTitle') }}</p>
        <p class="feed-error-text">{{ allActions.length ? $t('step3.runFailedBody') : $t('step3.startFailedBody') }}</p>
        <details class="feed-error-details">
          <summary>{{ $t('main.failDetails') }}</summary>
          <code>{{ startError }}</code>
        </details>
      </div>

      <!-- Timeline Feed -->
      <div class="timeline-feed">
        <div class="timeline-axis"></div>
        
        <TransitionGroup name="timeline-item">
          <div 
            v-for="action in chronologicalActions" 
            :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`" 
            class="timeline-item"
            :class="action.platform"
          >
            <div class="timeline-marker">
              <div class="marker-dot"></div>
            </div>
            
            <div class="timeline-card">
              <div class="card-header">
                <div class="agent-info">
                  <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                  <span class="agent-name">{{ action.agent_name }}</span>
                </div>
                
                <div class="header-meta">
                  <div class="platform-indicator" :title="platformName(action.platform)">
                    <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                    <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span class="sr-only">{{ platformName(action.platform) }}</span>
                  </div>
                  <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                    {{ getActionTypeLabel(action.action_type) }}
                  </div>
                </div>
              </div>

              <div class="card-body">
                <!-- CREATE_POST: 发布帖子 -->
                <MiniMarkdown v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text" :text="action.action_args.content" />

                <!-- QUOTE_POST: 引用帖子 -->
                <template v-if="action.action_type === 'QUOTE_POST'">
                  <MiniMarkdown v-if="action.action_args?.quote_content" class="content-text" :text="action.action_args.quote_content" />
                  <div v-if="action.action_args?.original_content" class="quoted-block">
                    <div class="quote-header">
                      <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                      <span class="quote-label">@{{ action.action_args.original_author_name || $t('step3.someone') }}</span>
                    </div>
                    <div class="quote-text">
                      {{ truncateContent(action.action_args.original_content, 150) }}
                    </div>
                  </div>
                </template>

                <!-- REPOST: 转发帖子 -->
                <template v-if="action.action_type === 'REPOST'">
                  <div class="repost-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>
                    <span class="repost-label">{{ $t('step3.repostedFrom', { name: atName(action.action_args?.original_author_name) }) }}</span>
                  </div>
                  <div v-if="action.action_args?.original_content" class="repost-content">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </div>
                </template>

                <!-- LIKE_POST: 点赞帖子 -->
                <template v-if="action.action_type === 'LIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <span class="like-label">{{ $t('step3.likedPost', { name: atName(action.action_args?.post_author_name) }) }}</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- CREATE_COMMENT: 发表评论 -->
                <template v-if="action.action_type === 'CREATE_COMMENT'">
                  <MiniMarkdown v-if="action.action_args?.content" class="content-text" :text="action.action_args.content" />
                  <div v-if="action.action_args?.post_id" class="comment-context">
                    <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span>{{ $t('step3.replyToPost', { id: action.action_args.post_id }) }}</span>
                  </div>
                </template>

                <!-- SEARCH_POSTS: 搜索帖子 -->
                <template v-if="action.action_type === 'SEARCH_POSTS'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">{{ $t('step3.searchQuery') }}</span>
                    <span class="search-query">"{{ action.action_args?.query || '' }}"</span>
                  </div>
                </template>

                <!-- FOLLOW: 关注用户 -->
                <template v-if="action.action_type === 'FOLLOW'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                    <span class="follow-label">{{ $t('step3.followed', { name: atName(action.action_args?.target_user || action.action_args?.user_id) }) }}</span>
                  </div>
                </template>

                <!-- UPVOTE / DOWNVOTE -->
                <template v-if="action.action_type === 'UPVOTE_POST' || action.action_type === 'DOWNVOTE_POST'">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'UPVOTE_POST'" class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span class="vote-label">{{ action.action_type === 'UPVOTE_POST' ? $t('step3.upvotedPost') : $t('step3.downvotedPost') }}</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="voted-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- DO_NOTHING: 无操作（静默） -->
                <template v-if="action.action_type === 'DO_NOTHING'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span class="idle-label">{{ $t('step5.actionSkipped') }}</span>
                  </div>
                </template>

                <!-- 通用回退：未知类型或有 content 但未被上述处理 -->
                <MiniMarkdown v-if="!['CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'CREATE_COMMENT', 'SEARCH_POSTS', 'FOLLOW', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING'].includes(action.action_type) && action.action_args?.content" class="content-text" :text="action.action_args.content" />
              </div>

              <div class="card-footer">
                <span class="time-tag">{{ $t('step3.roundShort', { n: action.round_num }) }} · {{ formatActionTime(action.timestamp) }}</span>
                <!-- Platform tag removed as it is in header now -->
              </div>
            </div>
          </div>
        </TransitionGroup>

        <div v-if="allActions.length === 0 && !startError" class="waiting-state" role="status">
          <div class="pulse-ring"></div>
          <span>{{ $t('step3.waitingForActions') }}</span>
        </div>
        <div
          v-else-if="filteredActionsCount === 0 && hasActiveFilters"
          class="feed-empty"
          role="status"
        >
          <span>{{ $t('step3.noMatchingActions') }}</span>
          <button type="button" class="clear-filters-btn inline" @click="clearFeedFilters">
            {{ $t('step3.clearFilters') }}
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
        <span class="log-id tech-only">{{ simulationId || 'NO_SIMULATION' }}</span>
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  startSimulation,
  stopSimulation,
  getRunStatus,
  getRunStatusDetail
} from '../api/simulation'
import { generateReport, checkReportForSimulation } from '../api/report'
import { usePipeline } from '../composables/usePipeline'
import { MiniMarkdown, stripMarkdown } from '../lib/miniMarkdown'

const { t, te } = useI18n()

const props = defineProps({
  simulationId: String,
  maxRounds: Number, // 从Step2传入的最大轮数
  minutesPerRound: {
    type: Number,
    default: 30 // 默认每轮30分钟
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})
const { showTech, toggleTech } = useTechDetails()
const lastLog = computed(() => {
  const logs = props.systemLogs || []
  const last = logs[logs.length - 1]
  return last ? String(last.msg || '') : ''
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

// Modo lectura: con un informe ya hecho, este paso lleva a él en vez de regenerarlo, y no se reinicia
const existingReport = ref(null)   // { report_id, status }
const hasReport = computed(() => !!existingReport.value?.report_id && existingReport.value.status !== 'failed')
const { isRunning: autoRunning, state: pipelineState, refresh: refreshPipeline } = usePipeline(() => props.projectData?.project_id)
const loadExistingReport = async () => {
  if (!props.simulationId) return
  try {
    const res = await checkReportForSimulation(props.simulationId)
    const d = res?.data
    existingReport.value = d?.has_report ? { report_id: d.report_id, status: d.report_status } : null
  } catch (e) {
    existingReport.value = null
  }
}
const openReport = () => {
  if (existingReport.value?.report_id) router.push({ name: 'Report', params: { reportId: existingReport.value.report_id } })
}

const router = useRouter()

// State
const isGeneratingReport = ref(false)
const phase = ref(0) // 0: 未开始, 1: 运行中, 2: 已完成
const isStarting = ref(false)
const isStopping = ref(false)
const startError = ref(null)
const runStatus = ref({})
const allActions = ref([]) // 所有动作（增量累积）
const actionIds = ref(new Set()) // 用于去重的动作ID集合
const scrollContainer = ref(null)

// Feed filters (platform / action-type group / free-text search)
const feedFilters = ref({
  platform: 'all',     // 'all' | 'twitter' | 'reddit'
  actionGroup: 'all',  // 'all' | 'posts' | 'interactions' | 'comments'
  query: ''
})

const ACTION_GROUPS = {
  posts: new Set(['CREATE_POST', 'QUOTE_POST', 'REPOST']),
  interactions: new Set(['LIKE_POST', 'LIKE_COMMENT', 'UPVOTE_POST', 'DOWNVOTE_POST', 'FOLLOW', 'SEARCH_POSTS']),
  comments: new Set(['CREATE_COMMENT'])
}

const matchesQuery = (action, q) => {
  if (!q) return true
  const needle = q.toLowerCase()
  const args = action.action_args || {}
  const haystacks = [
    action.agent_name,
    action.action_type,
    args.content,
    args.quote_content,
    args.original_content,
    args.post_content,
    args.query,
    args.original_author_name,
    args.post_author_name,
    args.target_user
  ]
  return haystacks.some(v => v && String(v).toLowerCase().includes(needle))
}

// Computed
// 按时间顺序显示动作（最新的在最后面，即底部）
const chronologicalActions = computed(() => {
  const { platform, actionGroup, query } = feedFilters.value
  const group = ACTION_GROUPS[actionGroup]
  const q = query.trim()

  if (platform === 'all' && !group && !q) {
    return allActions.value
  }

  return allActions.value.filter(action => {
    if (platform !== 'all' && action.platform !== platform) return false
    if (group && !group.has(action.action_type)) return false
    if (q && !matchesQuery(action, q)) return false
    return true
  })
})

// 各平台动作计数
const twitterActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'twitter').length
})

const redditActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'reddit').length
})

// 当过滤器生效时，显示的数量
const filteredActionsCount = computed(() => chronologicalActions.value.length)
const hasActiveFilters = computed(() => {
  const { platform, actionGroup, query } = feedFilters.value
  return platform !== 'all' || actionGroup !== 'all' || query.trim() !== ''
})

const clearFeedFilters = () => {
  feedFilters.value = { platform: 'all', actionGroup: 'all', query: '' }
}

// 格式化模拟流逝时间（根据轮次和每轮分钟数计算）
const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h 0m'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

// Twitter平台的模拟流逝时间
const twitterElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.twitter_current_round || 0)
})

// Reddit平台的模拟流逝时间
const redditElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.reddit_current_round || 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// 重置所有状态（用于重新启动模拟）
const resetAllState = () => {
  phase.value = 0
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  startError.value = null
  isStarting.value = false
  isStopping.value = false
  stopPolling()  // 停止之前可能存在的轮询
}

// 启动模拟
//
// `force=true` mata el proceso anterior y borra `actions.jsonl`. SOLO se debe
// usar cuando el usuario pide explícitamente reiniciar (botón Restart en el
// header). En montaje normal del componente (ej. al volver al Step desde el
// stepper) se debe llamar con `force=false` o usar `initSimulationView()` que
// reconecta a una run en curso o carga la run completada existente sin
// reiniciar nada.
const doStartSimulation = async ({ force = false } = {}) => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  // Solo limpiamos el estado local cuando vamos a reiniciar; en arranque
  // normal el estado ya está vacío y un reset prematuro borraría una run
  // recién reconectada.
  if (force) {
    resetAllState()
  }

  isStarting.value = true
  startError.value = null
  addLog(force ? t('log.restartingDualSim', 'Reiniciando simulación...') : t('log.startingDualSim'))
  emit('update-status', 'processing')

  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      force,
      enable_graph_memory_update: true  // 开启动态图谱更新
    }
    
    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
      addLog(t('log.setMaxRounds', { rounds: props.maxRounds }))
    }
    
    addLog(t('log.graphMemoryUpdateEnabled'))
    
    const res = await startSimulation(params)
    
    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog(t('log.oldSimCleared'))
      }
      addLog(t('log.engineStarted'))
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      
      phase.value = 1
      runStatus.value = res.data
      
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = res.error || t('step3.startFailed', { error: t('common.unknownError') })
      addLog(t('log.startFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    // Extract the actual server error message (axios wraps the HTTP error;
    // the real message is in err.response.data.error, not err.message).
    const serverError = err?.response?.data?.error || err.message || String(err)

    // If the backend reports the simulation is already running (race condition on
    // page reload / force-restart), reconnect to the running instance instead of
    // showing an error.  The backend message key is 'api.simAlreadyRunning'.
    const isAlreadyRunning =
      err?.response?.status === 400 &&
      (serverError.toLowerCase().includes('already running') ||
       serverError.toLowerCase().includes('ya en ejecución') ||
       serverError.toLowerCase().includes('ya está en ejecución') ||
       serverError.toLowerCase().includes('en ejecución'))

    if (isAlreadyRunning) {
      addLog(`⚠ ${t('log.simAlreadyRunning', 'Simulación ya en ejecución — reconectando...')}`)
      phase.value = 1
      emit('update-status', 'processing')
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = serverError
      addLog(t('log.startException', { error: serverError }))
      emit('update-status', 'error')
    }
  } finally {
    isStarting.value = false
  }
}

// 停止模拟
const handleStopSimulation = async () => {
  if (!props.simulationId) return
  
  isStopping.value = true
  addLog(t('log.stoppingSim'))
  
  try {
    const res = await stopSimulation({ simulation_id: props.simulationId })
    
    if (res.success) {
      addLog(t('log.simStoppedSuccess'))
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(t('log.stopFailed', { error: res.error || t('common.unknownError') }))
    }
  } catch (err) {
    addLog(t('log.stopException', { error: err.message }))
  } finally {
    isStopping.value = false
  }
}

// 轮询状态
let statusTimer = null
let detailTimer = null

const startStatusPolling = () => {
  statusTimer = setInterval(fetchRunStatus, 2000)
}

const startDetailPolling = () => {
  detailTimer = setInterval(fetchRunStatusDetail, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

// 追踪各平台的上一次轮次，用于检测变化并输出日志
const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)

const fetchRunStatus = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatus(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data
      
      runStatus.value = data
      
      // 分别检测各平台的轮次变化并输出日志
      if (data.twitter_current_round > prevTwitterRound.value) {
        addLog(`[Plaza] R${data.twitter_current_round}/${data.total_rounds} | T:${data.twitter_simulated_hours || 0}h | A:${data.twitter_actions_count}`)
        prevTwitterRound.value = data.twitter_current_round
      }
      
      if (data.reddit_current_round > prevRedditRound.value) {
        addLog(`[Community] R${data.reddit_current_round}/${data.total_rounds} | T:${data.reddit_simulated_hours || 0}h | A:${data.reddit_actions_count}`)
        prevRedditRound.value = data.reddit_current_round
      }
      
      // 首先检测是否失败（需要在 completed 判断之前，避免误报）
      const isFailed = data.runner_status === 'failed' || data.status === 'failed'
      if (isFailed) {
        const errText = data.error || data.runner_error || t('common.unknownError')
        addLog(t('log.simulationFailed', { error: errText }))
        phase.value = 2
        stopPolling()
        emit('update-status', 'error')
        return
      }

      // 检测模拟是否已完成（通过 runner_status 或平台完成状态判断）
      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped'

      // 额外检查：如果后端还没来得及更新 runner_status，但平台已经报告完成
      // 通过检测 twitter_completed 和 reddit_completed 状态判断
      const platformsCompleted = checkPlatformsCompleted(data)

      if (isCompleted || platformsCompleted) {
        if (platformsCompleted && !isCompleted) {
          addLog(t('log.allPlatformsCompleted'))
        }
        addLog(t('log.simCompleted'))
        phase.value = 2
        stopPolling()
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Error al obtener el estado de ejecución:', err)
  }
}

// 检查所有启用的平台是否已完成
const checkPlatformsCompleted = (data) => {
  // 如果没有任何平台数据，返回 false
  if (!data) return false
  
  // 检查各平台的完成状态
  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true
  
  // 如果至少有一个平台完成了，检查是否所有启用的平台都完成了
  // 通过 actions_count 判断平台是否被启用（如果 count > 0 或 running 曾为 true）
  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted
  
  // 如果没有任何平台被启用，返回 false
  if (!twitterEnabled && !redditEnabled) return false
  
  // 检查所有启用的平台是否都已完成
  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false
  
  return true
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatusDetail(props.simulationId)
    
    if (res.success && res.data) {
      // 使用 all_actions 获取完整的动作列表
      const serverActions = res.data.all_actions || []
      
      // 增量添加新动作（去重）
      let newActionsAdded = 0
      serverActions.forEach(action => {
        // 生成唯一ID
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`
        
        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
          newActionsAdded++
        }
      })
      
      // 不自动滚动，让用户自由查看时间轴
      // 新动作会在底部追加
    }
  } catch (err) {
    console.warn('Error al obtener el estado detallado:', err)
  }
}

// Helpers
// Rótulo corto de cada acción (step3.actions.*); lo que el motor añada sin traducir se enseña tal cual
const getActionTypeLabel = (type) => {
  const key = `step3.actions.${type}`
  return type && te(key) ? t(key) : (type || t('common.unknown'))
}
// «@nombre» si hay autor; si no, «alguien» (la @ va aquí: en vue-i18n es un carácter especial)
const atName = (n) => (n ? '@' + n : t('step3.someone'))
const platformName = (p) => (p === 'twitter' ? t('step3.platformTwitter') : p === 'reddit' ? t('step3.platformReddit') : (p || ''))

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DO_NOTHING': 'badge-idle'
  }
  return classes[type] || 'badge-default'
}

// Recortes: primero fuera las marcas de Markdown (recortar antes dejaría «**» sueltos a la vista)
const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  const plain = stripMarkdown(content).replace(/\s+/g, ' ').trim()
  if (plain.length > maxLength) return plain.substring(0, maxLength) + '…'
  return plain
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

// Pull the most informative message out of an axios error: prefer the
// backend's localized `error` field, then other common shapes, and only
// fall back to the generic axios message as a last resort.
const extractApiError = (err) => {
  const data = err?.response?.data
  if (data) {
    if (typeof data === 'string') return data
    return data.error || data.message || err.message
  }
  return err?.message || t('common.unknownError')
}

const doGenerateReport = async ({ force = false } = {}) => {
  try {
    const res = await generateReport({
      simulation_id: props.simulationId,
      force_regenerate: true,
      force,
    })

    if (res.success && res.data) {
      const reportId = res.data.report_id
      addLog(t('log.reportGenTaskStarted', { reportId }))
      router.push({ name: 'Report', params: { reportId } })
      return true
    }
    addLog(t('log.reportGenFailed', { error: res.error || t('common.unknownError') }))
    return false
  } catch (err) {
    const status = err?.response?.status
    const data = err?.response?.data || {}

    // Recoverable 409: the sim failed but there is usable partial data.
    // Offer the user a chance to generate the report anyway instead of
    // leaving them stuck looking at an opaque error.
    if (status === 409 && data.recoverable && !force) {
      const partial = data.partial_data || {}
      const totalActions = partial.total_actions ?? 0
      const platformsDone = []
      if (partial.reddit_completed) platformsDone.push(t('step3.platformReddit'))
      if (partial.twitter_completed) platformsDone.push(t('step3.platformTwitter'))
      const platformsText = platformsDone.length
        ? platformsDone.join(', ')
        : t('step3.platformNone')

      addLog(t('log.reportGenPartialAvailable', {
        actions: totalActions,
        platforms: platformsText,
      }))

      const confirmed = window.confirm(t('step3.partialReportConfirm', {
        actions: totalActions,
        platforms: platformsText,
      }))

      if (confirmed) {
        addLog(t('log.reportGenForced'))
        return doGenerateReport({ force: true })
      }
      addLog(t('log.reportGenCancelled'))
      return false
    }

    addLog(t('log.reportGenException', { error: extractApiError(err) }))
    return false
  }
}

const handleNextStep = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    return
  }

  if (isGeneratingReport.value) {
    addLog(t('log.reportRequestSent'))
    return
  }

  isGeneratingReport.value = true
  addLog(t('log.startingReportGen'))

  const ok = await doGenerateReport({ force: false })
  if (!ok) {
    isGeneratingReport.value = false
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

// Decide qué hacer al montar Step3:
// - simulación en curso → reconectar al polling sin reset ni force
// - simulación completada/parada → cargar las acciones existentes, NO relanzar
// - estado inicial → primer arranque con force=false
//
// Reemplaza al `doStartSimulation()` directo del montaje, que disparaba un
// reinicio con `force: true` cada vez que el usuario navegaba a Step 3 desde
// el stepper, perdiendo los datos del run anterior.
const initSimulationView = async () => {
  if (!props.simulationId) return

  try {
    const res = await getRunStatus(props.simulationId)
    if (res?.success && res.data) {
      const data = res.data
      const hasFailed = data.runner_status === 'failed' || data.status === 'failed'
      const isCompleted =
        data.runner_status === 'completed' ||
        data.runner_status === 'stopped' ||
        checkPlatformsCompleted(data)
      const isRunning =
        !isCompleted && !hasFailed &&
        (data.runner_status === 'running' || data.twitter_running || data.reddit_running)

      if (isRunning) {
        addLog(t('log.reconnectingToRunning', 'Reconectando a la simulación en curso...'))
        phase.value = 1
        runStatus.value = data
        prevTwitterRound.value = data.twitter_current_round || 0
        prevRedditRound.value = data.reddit_current_round || 0
        emit('update-status', 'processing')
        await fetchRunStatusDetail()
        startStatusPolling()
        startDetailPolling()
        return
      }

      if (isCompleted) {
        addLog(t('log.loadingPreviousRun', 'Cargando resultados de la simulación anterior...'))
        phase.value = 2
        runStatus.value = data
        emit('update-status', 'completed')
        await fetchRunStatusDetail()
        return
      }

      if (hasFailed) {
        startError.value = data.error || data.runner_error || t('common.unknownError')
        addLog(t('log.simulationFailed', { error: startError.value }))
        runStatus.value = data
        phase.value = 2
        emit('update-status', 'error')
        return
      }
    }
  } catch (err) {
    // 404 / no previous status → primer arranque, seguimos al fallback
    console.warn('No previous simulation status, starting fresh:', err)
  }

  // En automático la lanza el servidor: esperar a que arranque en vez de lanzarla desde aquí
  // (el proyecto llega un poco después que la simulación: se espera hasta 5 s para saber el modo)
  for (let i = 0; i < 25 && !props.projectData?.project_id && !unmounted; i++) await new Promise(r => setTimeout(r, 200))
  if (unmounted) return
  if (props.projectData?.project_id) await refreshPipeline().catch(() => {})
  if (autoRunning.value) {
    if (!unmounted) waitTimer = setTimeout(initSimulationView, 3000)
    return
  }

  // Primer arranque normal — el backend rechaza si ya hay una corriendo,
  // y `doStartSimulation` ya maneja ese caso reconectando.
  doStartSimulation({ force: false })
}

// Restart explícito por click del usuario. Único punto donde mandamos
// `force: true` al backend.
const handleRestartSimulation = async () => {
  if (!props.simulationId || isStarting.value) return
  const confirmed = window.confirm(t('step3.restartConfirm', '¿Reiniciar la simulación? Se perderán los datos del run actual.'))
  if (!confirmed) return
  addLog(t('log.userRequestedRestart', 'Reinicio solicitado por el usuario.'))
  await doStartSimulation({ force: true })
}

let unmounted = false
let waitTimer = null

onMounted(() => {
  addLog(t('log.step3Init'))
  loadExistingReport()
  initSimulationView()
})
// al terminar la ejecución (o si el automático ya pidió el informe) se mira si hay informe
watch(phase, (p) => { if (p === 2) loadExistingReport() })
watch(() => pipelineState.value?.report_id, (rid) => { if (rid) loadExistingReport() })

onUnmounted(() => {
  unmounted = true
  clearTimeout(waitTimer)
  stopPolling()
})
</script>

<style scoped>
.auto-chip {
  font-size: 12px;
  color: var(--kb-text-2);
  max-width: 260px;
  line-height: 1.35;
}
.simulation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  font-family: var(--kb-font-sans);
  overflow: hidden;
}

/* --- Control Bar --- */
.control-bar {
  background: #FFF;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--kb-line);
  z-index: 10;
  height: 64px;
}

.status-group {
  display: flex;
  gap: 12px;
}

/* Platform Status Cards
   Antes, la tarjeta en espera iba al 70 % de opacidad: apagaba también el texto (los rótulos grises caían por debajo de 4,5:1).
   Ahora el estado se lee por el borde (discontinuo en espera) y por el icono ✓ al terminar, no por transparencia ni solo por color. */
.platform-status {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 4px;
  background: var(--kb-surface-2);
  border: 1px dashed var(--kb-control-line);
  transition: border-color 0.3s, background-color 0.3s;
  min-width: 140px;
  position: relative;
  cursor: default;
}

.platform-status.active {
  border-style: solid;
  border-color: var(--kb-text-2);
  background: #FFF;
}

.platform-status.completed {
  border-style: solid;
  border-color: var(--kb-ok-line);
  background: var(--kb-ok-bg);
}

/* Actions Tooltip */
.actions-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  padding: 10px 14px;
  background: var(--kb-text);
  color: #FFF;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 100;
  min-width: 180px;
  pointer-events: none;
}

.actions-tooltip::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 6px solid var(--kb-text);
}

.platform-status:hover .actions-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-muted-on-dark);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.tooltip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-action {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  background: var(--kb-text-2);
  border-radius: 2px;
  color: #FFF;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.platform-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--kb-text);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.platform-status.twitter .platform-icon { color: var(--kb-text); }
.platform-status.reddit .platform-icon { color: var(--kb-text); }

.platform-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 10px;
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 4px;
  white-space: nowrap;
}

.stat-label {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--kb-text-2);
}

.stat-total, .stat-unit {
  font-size: 12px;
  color: var(--kb-subtle);
  font-weight: 400;
}

.status-badge {
  margin-left: auto;
  color: var(--kb-ok-text);
  display: flex;
  align-items: center;
}

/* Action Button */
.action-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  height: 38px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  box-sizing: border-box;
}

.action-btn.primary {
  background: var(--kb-text);
  color: #FFF;
}

.action-btn.primary:hover:not(:disabled) {
  background: var(--kb-text-2);
}

/* «Detener» y «Reiniciar»: contorno, nunca relleno — el único botón relleno de la barra es el principal */
.action-btn.danger {
  background: transparent;
  color: var(--kb-danger-text);
  border: 1px solid var(--kb-danger-line);
}

.action-btn.danger:hover:not(:disabled) {
  background: var(--kb-surface-2);
}

.action-btn.secondary {
  background: transparent;
  color: var(--kb-text);
  border: 1px solid var(--kb-control-line);
}

.action-btn.secondary:hover:not(:disabled) {
  border-color: var(--kb-text);
  background: var(--kb-surface-2);
}

/* Compact icon-only variant (used for Stop button) */
.action-btn.icon-only {
  width: 38px;
  padding: 0;
  gap: 0;
}

.action-btn.icon-only svg {
  display: block;
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* --- Main Content Area --- */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  position: relative;
  background: #FFF;
}

/* Timeline Header */
.timeline-header {
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  padding: 12px 24px;
  border-bottom: 1px solid var(--kb-line);
  z-index: 5;
  display: flex;
  justify-content: center;
}

.timeline-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--kb-text-on-soft);
  background: var(--kb-soft);
  padding: 4px 12px;
  border-radius: 20px;
}

.total-count {
  font-weight: 600;
  color: var(--kb-text-2);
}

.platform-breakdown {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* separador: un filete, no un «/» de texto gris (1,32:1) */
.breakdown-divider { width: 1px; height: 12px; background: var(--kb-control-line); }
.breakdown-item.twitter { color: var(--kb-text); }
.breakdown-item.reddit { color: var(--kb-text); }

.stats-total-hint {
  color: var(--kb-text-on-soft);
  margin-left: 4px;
  font-weight: 400;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

/* --- Feed Filters --- */
.feed-filters {
  position: sticky;
  top: 44px;
  z-index: 4;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--kb-line);
}

.filter-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--kb-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-right: 2px;
}

/* Chips de filtro: son controles, así que el borde es --kb-control-line (3,69:1), no el filete --kb-line (1,36:1) */
.filter-chip {
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  min-height: 24px;
  padding: 3px 10px;
  border: 1px solid var(--kb-control-line);
  background: #FFF;
  color: var(--kb-muted);
  border-radius: 999px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.filter-chip:hover {
  border-color: var(--kb-text);
  color: var(--kb-text);
}

.filter-chip.active {
  background: var(--kb-text);
  color: #FFF;
  border-color: var(--kb-text);
}

.filter-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex: 1 1 220px;
  max-width: 360px;
  min-height: 32px;
  box-sizing: border-box;
  padding: 3px 4px 3px 12px;
  border: 1px solid var(--kb-control-line);
  border-radius: 999px;
  background: #FFF;
}

.filter-search:focus-within {
  border-color: var(--kb-text);
  box-shadow: 0 0 0 1px var(--kb-text);
}

.filter-search .search-icon {
  color: var(--kb-subtle);
  flex-shrink: 0;
}

.filter-search input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  font-size: 12px;
  color: var(--kb-text);
  padding: 2px 0;
}

.filter-search input::placeholder {
  color: var(--kb-subtle);
}

.clear-filters-btn {
  font-family: inherit;
  font-size: 12px;
  font-weight: 600;
  min-height: 24px;
  padding: 3px 10px;
  background: transparent;
  color: var(--kb-muted);
  border: 1px solid var(--kb-control-line);
  border-radius: 999px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  transition: all 0.15s ease;
}

.clear-filters-btn:hover {
  border-color: var(--kb-text);
  color: var(--kb-text);
}

.clear-filters-btn.inline {
  margin-top: 12px;
}

/* Sin resultados: en el flujo, arriba del todo (centrado en absoluto quedaba fuera de la vista mientras salían las tarjetas) */
.feed-empty {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin: 24px auto 0;
  padding: 20px 24px;
  max-width: 420px;
  background: #FFF;
  border: 1px solid var(--kb-line);
  border-radius: 4px;
  color: var(--kb-muted);
  font-size: 13px;
  text-align: center;
}

/* Error de arranque o de ejecución: franja clara encima del feed; el detalle técnico, plegado */
.feed-error {
  margin: 16px 24px 0;
  padding: 14px 16px;
  background: #FFF;
  border: 1px solid var(--kb-danger-line);
  border-left-width: 4px;
  border-radius: 4px;
}
.feed-error-title { margin: 0 0 4px; font-size: 14px; font-weight: 700; color: var(--kb-text); }
.feed-error-text { margin: 0; font-size: 13px; line-height: 1.5; color: var(--kb-text-2); }
.feed-error-details { margin-top: 8px; font-size: 12px; color: var(--kb-muted); }
.feed-error-details summary { cursor: pointer; }
.feed-error-details code {
  display: block; margin-top: 6px; padding: 8px 10px;
  background: var(--kb-surface-2); border: 1px solid var(--kb-line); border-radius: 4px;
  font-family: var(--kb-font-mono); font-size: 12px; color: var(--kb-text-2); overflow-wrap: anywhere;
}

/* --- Timeline Feed --- */
.timeline-feed {
  padding: 24px 0;
  position: relative;
  min-height: 100%;
  max-width: 900px;
  margin: 0 auto;
}

.timeline-axis {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--kb-line); /* Cleaner line */
  transform: translateX(-50%);
}

.timeline-item {
  display: flex;
  justify-content: center;
  margin-bottom: 32px;
  position: relative;
  width: 100%;
}

.timeline-marker {
  position: absolute;
  left: 50%;
  top: 24px;
  width: 10px;
  height: 10px;
  background: #FFF;
  border: 1px solid var(--kb-line-strong);
  border-radius: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-dot {
  width: 4px;
  height: 4px;
  background: var(--kb-line-strong);
  border-radius: 50%;
}

.timeline-item.twitter .marker-dot { background: var(--kb-text); }
.timeline-item.reddit .marker-dot { background: var(--kb-text); }
.timeline-item.twitter .timeline-marker { border-color: var(--kb-text); }
.timeline-item.reddit .timeline-marker { border-color: var(--kb-text); }

/* Card Layout */
.timeline-card {
  width: calc(100% - 48px);
  background: #FFF;
  border-radius: 2px;
  padding: 16px 20px;
  border: 1px solid var(--kb-line);
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  position: relative;
  transition: all 0.2s;
}

.timeline-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  border-color: var(--kb-line-strong);
}

/* Left side (Twitter) */
.timeline-item.twitter {
  justify-content: flex-start;
  padding-right: 50%;
}
.timeline-item.twitter .timeline-card {
  margin-left: auto;
  margin-right: 32px; /* Gap from axis */
}

/* Right side (Reddit) */
.timeline-item.reddit {
  justify-content: flex-end;
  padding-left: 50%;
}
.timeline-item.reddit .timeline-card {
  margin-right: auto;
  margin-left: 32px; /* Gap from axis */
}

/* Card Content Styles */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--kb-soft);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-placeholder {
  width: 24px;
  height: 24px;
  background: var(--kb-text);
  color: #FFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--kb-text);
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-indicator {
  color: var(--kb-subtle);
  display: flex;
  align-items: center;
}

.action-badge {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 2px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
  border: 1px solid transparent;
}

/* Monochromatic Badges (sobre --kb-soft, el texto va en --kb-text-on-soft: el gris daba 4,32:1) */
.badge-post { background: var(--kb-soft); color: var(--kb-text-on-soft); border-color: var(--kb-line); }
.badge-comment { background: var(--kb-soft); color: var(--kb-text-on-soft); border-color: var(--kb-line); }
.badge-action { background: #FFF; color: var(--kb-muted); border: 1px solid var(--kb-line); }
.badge-meta { background: var(--kb-surface-2); color: var(--kb-subtle); border: 1px dashed var(--kb-line-strong); }
.badge-idle { background: #FFF; color: var(--kb-muted); border: 1px dashed var(--kb-line-strong); }

.content-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--kb-text-2);
  margin-bottom: 10px;
  overflow-wrap: anywhere;
}

.content-text.main-text {
  font-size: 14px;
  color: var(--kb-text);
}

/* Markdown de los posts (MiniMarkdown) */
.content-text :deep(.md-p) { margin: 0 0 8px; }
.content-text :deep(.md-p:last-child),
.content-text :deep(.md-ul:last-child),
.content-text :deep(.md-ol:last-child) { margin-bottom: 0; }
.content-text :deep(.md-ul),
.content-text :deep(.md-ol) { margin: 0 0 8px; padding-left: 20px; }
.content-text :deep(.md-li),
.content-text :deep(.md-oli) { margin: 2px 0; }
.content-text :deep(strong) { font-weight: 700; color: var(--kb-text); }
.content-text :deep(.md-quote) { margin: 0 0 8px; padding-left: 10px; border-left: 2px solid var(--kb-line-strong); color: var(--kb-text-2); }
.content-text :deep(.inline-code) { font-family: var(--kb-font-mono); font-size: 12px; background: var(--kb-soft); padding: 0 4px; border-radius: 2px; }
.content-text :deep(.code-block) { margin: 0 0 8px; padding: 8px 10px; background: var(--kb-surface-2); border: 1px solid var(--kb-line); font-family: var(--kb-font-mono); font-size: 12px; white-space: pre-wrap; }
.content-text :deep(.md-hr) { border: 0; border-top: 1px solid var(--kb-line); margin: 8px 0; }

/* Info Blocks (Quote, Repost, etc) */
.quoted-block, .repost-content {
  background: var(--kb-surface-2);
  border: 1px solid var(--kb-line);
  padding: 10px 12px;
  border-radius: 2px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--kb-text-2);
}

.quote-header, .repost-info, .like-info, .search-info, .follow-info, .vote-info, .idle-info, .comment-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--kb-muted);
}

/* el texto citado de un «me gusta» o un voto heredaba 16 px: más grande que el propio post */
.liked-content, .voted-content {
  font-size: 13px;
  line-height: 1.55;
  color: var(--kb-text-2);
}

.icon-small {
  color: var(--kb-subtle);
}
.icon-small.filled {
  color: var(--kb-subtle); /* Keep icons neutral unless highlighted */
}

.search-query {
  font-family: var(--kb-font-mono);
  background: var(--kb-soft);
  padding: 0 4px;
  border-radius: 2px;
}

/* Ronda y hora: metadato, en --kb-muted (5,1:1); el #BBB de antes daba 1,92:1 */
.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  font-size: 12px;
  color: var(--kb-muted);
  font-family: var(--kb-font-mono);
}

/* Waiting State */
.waiting-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: var(--kb-muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-align: center;
}

.pulse-ring {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--kb-line);
  animation: ripple 2s infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 1; border-color: var(--kb-line-strong); }
  100% { transform: scale(2.5); opacity: 0; border-color: var(--kb-line); }
}

/* Animation */
.timeline-item-enter-active,
.timeline-item-leave-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.timeline-item-leave-to {
  opacity: 0;
}

/* Logs */
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
  align-items: center;
  border-bottom: 1px solid var(--kb-text-2);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--kb-muted-on-dark);
}

/* Sobre tinta, el gris de texto da 3,7:1: el rótulo va en --kb-muted-on-dark (5,5:1) */
.log-title { color: var(--kb-muted-on-dark); font-size: 12px; flex-shrink: 0; }
/* el botón global medía 22 px de alto: el mínimo táctil es 24 (WCAG 2.5.8) */
.log-toggle { min-height: 24px; }

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: var(--kb-text-2); border-radius: 2px; }

.log-line {
  font-size: 12px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time { color: var(--kb-muted-on-dark); min-width: 75px; }
.log-msg { color: var(--kb-line-strong); word-break: break-all; }
.mono { font-family: var(--kb-font-mono); }

/* Loading spinner for button */
.loading-spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
}

/* Pantallas estrechas: la barra de control y las tarjetas de plataforma se reparten en filas */
@media (max-width: 900px) {
  .control-bar { height: auto; flex-wrap: wrap; gap: 8px 12px; padding: 10px 14px; }
  .status-group { flex-wrap: wrap; width: 100%; }
  .platform-status { flex: 1 1 150px; min-width: 0; }
}
/* Móvil: cada plataforma a todo el ancho, con sus tres cifras en una línea (a media anchura se partían en 3 filas) */
@media (max-width: 700px) {
  .status-group { gap: 8px; }
  .platform-status { flex: 1 1 100%; }
  .action-controls { width: 100%; }
  .action-controls .action-btn.primary { flex: 1; }
}

/* Panel estrecho (móvil, o «Dividido» en un portátil pequeño): una sola columna.
   A dos columnas, cada tarjeta se quedaba en ~170 px y el texto iba palabra a palabra.
   La plataforma se sigue leyendo en el icono y su nombre de cada tarjeta. */
.main-content-area { container-type: inline-size; }
@container (max-width: 700px) {
  .timeline-header { padding: 10px 14px; }
  .timeline-stats { flex-wrap: wrap; justify-content: center; row-gap: 2px; }
  .feed-filters { position: static; padding: 10px 14px; gap: 10px; }
  .filter-search { margin-left: 0; max-width: none; flex-basis: 100%; }
  .feed-error { margin: 12px 14px 0; }
  .timeline-axis { left: 22px; transform: none; }
  .timeline-marker { left: 22px; }
  .timeline-item.twitter,
  .timeline-item.reddit { justify-content: stretch; padding: 0 14px 0 44px; margin-bottom: 20px; }
  .timeline-item.twitter .timeline-card,
  .timeline-item.reddit .timeline-card { width: 100%; margin: 0; padding: 14px 16px; }
  .card-header { gap: 8px; }
  .agent-info { min-width: 0; }
  .header-meta { flex-shrink: 0; }
}
</style>