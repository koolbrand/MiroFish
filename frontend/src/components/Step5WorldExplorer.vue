<template>
  <div class="world-explorer">
    <!-- Header with search + filters -->
    <div class="explorer-header">
      <div class="search-wrapper">
        <svg class="search-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input
          type="text"
          v-model="filters.query"
          :placeholder="$t('step5.explorerSearchPlaceholder')"
          :aria-label="$t('step5.explorerSearchPlaceholder')"
        />
      </div>
      <div class="filter-chips">
        <button
          v-for="opt in platformOptions"
          :key="opt.key"
          class="chip"
          :class="{ active: filters.platform === opt.key }"
          @click="filters.platform = opt.key"
        >
          {{ opt.label }}
        </button>
      </div>
      <select v-model="filters.sort" class="sort-select" :aria-label="$t('step2.sortDefault')">
        <option value="default">{{ $t('step2.sortDefault') }}</option>
        <option value="name">{{ $t('step2.sortByName') }}</option>
        <option value="profession">{{ $t('step2.sortByProfession') }}</option>
        <option value="activity">{{ $t('step5.sortByActivity') }}</option>
      </select>
    </div>

    <div class="explorer-body">
      <!-- Left: agent list -->
      <aside class="agents-column">
        <div class="agents-column-header">
          <span class="col-label">{{ $t('step5.agentsColumn') }}</span>
          <span class="col-count mono">{{ filteredAgents.length }}/{{ profiles.length }}</span>
        </div>

        <div v-if="filteredAgents.length === 0" class="empty-list">
          {{ $t('step2.noProfilesMatch') }}
        </div>

        <ul v-else class="agent-list">
          <li
            v-for="item in filteredAgents"
            :key="item.__idx"
            class="agent-row"
            :class="{ active: selectedIdx === item.__idx }"
            @click="selectAgent(item.__idx)"
          >
            <div class="agent-avatar">{{ (item.username || 'A')[0] }}</div>
            <div class="agent-meta">
              <span class="agent-name">{{ item.username || `agent_${item.__idx}` }}</span>
              <span class="agent-sub">
                {{ item.profession || $t('step2.unknownProfession') }}
                <template v-if="item.age">· {{ item.age }}</template>
              </span>
            </div>
            <span v-if="activityCounts[item.__idx]" class="agent-badge mono">
              {{ activityCounts[item.__idx] }}
            </span>
          </li>
        </ul>
      </aside>

      <!-- Right: selected agent detail -->
      <section class="detail-column">
        <div v-if="!selectedAgent" class="detail-empty">
          <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="8" r="4"></circle>
            <path d="M4 20c0-4 4-7 8-7s8 3 8 7"></path>
          </svg>
          <p>{{ $t('step5.explorerPickAgent') }}</p>
        </div>

        <template v-else>
          <header class="detail-header">
            <div class="detail-avatar">{{ (selectedAgent.username || 'A')[0] }}</div>
            <div class="detail-id">
              <h3 class="detail-name">{{ selectedAgent.username || `agent_${selectedIdx}` }}</h3>
              <div class="detail-meta-row">
                <span v-if="selectedAgent.name" class="detail-handle">@{{ selectedAgent.name }}</span>
                <span class="detail-profession">{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                <span v-if="selectedAgent.age" class="detail-age">· {{ selectedAgent.age }}</span>
                <span v-if="selectedAgent.gender" class="detail-gender">· {{ selectedAgent.gender }}</span>
              </div>
            </div>
            <button class="chat-cta" @click="$emit('chat-with-agent', selectedIdx)">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              {{ $t('step5.chatWithThisAgent') }}
            </button>
          </header>

          <div v-if="selectedAgent.bio" class="detail-bio">
            <div class="block-label">{{ $t('step5.profileBio') }}</div>
            <p>{{ selectedAgent.bio }}</p>
          </div>

          <!-- Stats strip -->
          <div class="stats-strip">
            <div class="stat-cell">
              <span class="stat-num mono">{{ agentStats.total }}</span>
              <span class="stat-lbl">{{ $t('step5.statTotalActions') }}</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num mono">{{ agentStats.posts }}</span>
              <span class="stat-lbl">{{ $t('step5.statPosts') }}</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num mono">{{ agentStats.interactions }}</span>
              <span class="stat-lbl">{{ $t('step5.statInteractions') }}</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num mono">{{ agentStats.comments }}</span>
              <span class="stat-lbl">{{ $t('step5.statComments') }}</span>
            </div>
          </div>

          <!-- Activity timeline -->
          <div class="activity-section">
            <div class="block-label">{{ $t('step5.activityTimeline') }}</div>

            <div v-if="activityLoading" class="activity-loading">
              <span class="loading-spinner"></span>
              {{ $t('step5.loadingActivity') }}
            </div>

            <div v-else-if="activityError" class="activity-error">
              {{ activityError }}
            </div>

            <div v-else-if="agentActions.length === 0" class="activity-empty">
              {{ $t('step5.noActivity') }}
            </div>

            <ul v-else class="activity-list">
              <li
                v-for="(act, i) in agentActions"
                :key="act._k || i"
                class="activity-item"
                :class="act.platform"
              >
                <div class="act-meta-col">
                  <span class="act-round mono">R{{ act.round_num }}</span>
                  <span class="act-time mono">{{ formatTime(act.timestamp) }}</span>
                  <span class="act-platform" :class="act.platform">{{ platformShort(act.platform) }}</span>
                </div>
                <div class="act-body">
                  <span class="act-badge" :class="actionClass(act.action_type)">
                    {{ actionLabel(act.action_type) }}
                  </span>
                  <div class="act-content">{{ describeAction(act) }}</div>
                </div>
              </li>
            </ul>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getSimulationActions } from '../api/simulation'

const { t } = useI18n()

const props = defineProps({
  simulationId: { type: String, default: null },
  profiles: { type: Array, default: () => [] }
})

const emit = defineEmits(['chat-with-agent'])

const filters = reactive({
  query: '',
  platform: 'all',
  sort: 'default'
})

const selectedIdx = ref(null)
const agentActions = ref([])
const activityLoading = ref(false)
const activityError = ref(null)
const actionsCache = ref({})       // idx -> actions[]
const activityCounts = ref({})     // idx -> total count (for list badge)

const platformOptions = computed(() => ([
  { key: 'all', label: t('step3.filterAll') },
  { key: 'twitter', label: t('step3.platformTwitter') },
  { key: 'reddit', label: t('step3.platformReddit') }
]))

const indexedProfiles = computed(() =>
  props.profiles.map((p, idx) => ({ ...p, __idx: idx }))
)

const filteredAgents = computed(() => {
  const q = filters.query.trim().toLowerCase()
  let list = indexedProfiles.value

  if (q) {
    list = list.filter(p =>
      (p.username && p.username.toLowerCase().includes(q)) ||
      (p.name && p.name.toLowerCase().includes(q)) ||
      (p.profession && p.profession.toLowerCase().includes(q)) ||
      (p.bio && p.bio.toLowerCase().includes(q))
    )
  }

  if (filters.platform !== 'all') {
    list = list.filter(p => {
      const plat = (p.platform || '').toLowerCase()
      return plat === filters.platform
    })
  }

  if (filters.sort === 'name') {
    list = [...list].sort((a, b) => (a.username || '').localeCompare(b.username || ''))
  } else if (filters.sort === 'profession') {
    list = [...list].sort((a, b) => (a.profession || '').localeCompare(b.profession || ''))
  } else if (filters.sort === 'activity') {
    list = [...list].sort(
      (a, b) => (activityCounts.value[b.__idx] || 0) - (activityCounts.value[a.__idx] || 0)
    )
  }

  return list
})

const selectedAgent = computed(() => {
  if (selectedIdx.value === null) return null
  return indexedProfiles.value[selectedIdx.value] || null
})

const POST_TYPES = ['CREATE_POST', 'QUOTE_POST', 'REPOST']
const INTERACTION_TYPES = ['LIKE_POST', 'LIKE_COMMENT', 'UPVOTE_POST', 'DOWNVOTE_POST', 'FOLLOW', 'SEARCH_POSTS']
const COMMENT_TYPES = ['CREATE_COMMENT']

const agentStats = computed(() => {
  const stats = { total: agentActions.value.length, posts: 0, interactions: 0, comments: 0 }
  for (const a of agentActions.value) {
    if (POST_TYPES.includes(a.action_type)) stats.posts++
    else if (INTERACTION_TYPES.includes(a.action_type)) stats.interactions++
    else if (COMMENT_TYPES.includes(a.action_type)) stats.comments++
  }
  return stats
})

const selectAgent = async (idx) => {
  selectedIdx.value = idx
  await loadAgentActions(idx)
}

const loadAgentActions = async (idx) => {
  if (!props.simulationId) {
    agentActions.value = []
    return
  }
  if (actionsCache.value[idx]) {
    agentActions.value = actionsCache.value[idx]
    return
  }

  activityLoading.value = true
  activityError.value = null
  agentActions.value = []

  try {
    const res = await getSimulationActions(props.simulationId, { agent_id: idx, limit: 500 })
    const raw = Array.isArray(res?.data?.actions) ? res.data.actions : (Array.isArray(res?.data) ? res.data : [])
    const actions = raw.map((a, i) => ({
      ...a,
      _k: a.id || `${a.timestamp || i}-${a.action_type || 'x'}-${i}`
    }))
    // most recent first
    actions.sort((a, b) => (b.round_num || 0) - (a.round_num || 0))
    actionsCache.value[idx] = actions
    activityCounts.value[idx] = actions.length
    agentActions.value = actions
  } catch (err) {
    activityError.value = err?.response?.data?.error || err.message || t('common.unknownError')
  } finally {
    activityLoading.value = false
  }
}

// When profiles change (fresh load), reset selection
watch(() => props.profiles.length, () => {
  selectedIdx.value = null
  agentActions.value = []
  actionsCache.value = {}
  activityCounts.value = {}
})

// ── Helpers ────────────────────────────────────────────────────────
const formatTime = (ts) => {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const platformShort = (p) => {
  if (p === 'twitter') return 'TW'
  if (p === 'reddit') return 'RD'
  return (p || '??').toUpperCase().slice(0, 2)
}

const ACTION_LABELS = {
  CREATE_POST: 'POST',
  QUOTE_POST: 'QUOTE',
  REPOST: 'REPOST',
  LIKE_POST: 'LIKE',
  LIKE_COMMENT: 'LIKE',
  UPVOTE_POST: 'UPVOTE',
  DOWNVOTE_POST: 'DOWNVOTE',
  CREATE_COMMENT: 'COMMENT',
  FOLLOW: 'FOLLOW',
  SEARCH_POSTS: 'SEARCH',
  DO_NOTHING: 'IDLE'
}

const actionLabel = (type) => ACTION_LABELS[type] || (type || 'UNKNOWN')

const actionClass = (type) => {
  if (POST_TYPES.includes(type)) return 'badge-post'
  if (COMMENT_TYPES.includes(type)) return 'badge-comment'
  if (type === 'DO_NOTHING') return 'badge-idle'
  return 'badge-action'
}

const describeAction = (act) => {
  const args = act.action_args || {}
  switch (act.action_type) {
    case 'CREATE_POST':
      return args.content || t('step5.noContent')
    case 'QUOTE_POST':
      return args.quote_content || args.content || args.original_content || t('step5.noContent')
    case 'REPOST':
      return `↻ @${args.original_author_name || '?'}: ${truncate(args.original_content || '', 160)}`
    case 'LIKE_POST':
      return `♥ @${args.post_author_name || '?'} — "${truncate(args.post_content || '', 120)}"`
    case 'LIKE_COMMENT':
      return `♥ ${truncate(args.comment_content || '', 120)}`
    case 'UPVOTE_POST':
    case 'DOWNVOTE_POST':
      return `"${truncate(args.post_content || '', 120)}"`
    case 'CREATE_COMMENT':
      return args.content || t('step5.noContent')
    case 'FOLLOW':
      return `@${args.target_user || args.user_id || '?'}`
    case 'SEARCH_POSTS':
      return `"${args.query || ''}"`
    case 'DO_NOTHING':
      return t('step5.actionSkipped')
    default:
      return args.content || act.result || ''
  }
}

const truncate = (s, n) => {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

defineExpose({ selectAgent })
</script>

<style scoped>
.world-explorer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  overflow: hidden;
  font-family: 'Inter', 'Noto Sans SC', system-ui, sans-serif;
}

.mono {
  font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Consolas', monospace;
}

/* Header */
.explorer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid #EAEAEA;
  flex-wrap: wrap;
  background: #FAFAFA;
}

.search-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #E5E7EB;
  border-radius: 999px;
  background: #FFF;
  flex: 1 1 180px;
  min-width: 160px;
}

.search-wrapper:focus-within {
  border-color: #000;
}

.search-wrapper .search-icon {
  color: #9CA3AF;
}

.search-wrapper input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font: inherit;
  font-size: 12px;
  color: #111;
  min-width: 0;
}

.search-wrapper input::placeholder {
  color: #AAA;
}

.filter-chips {
  display: flex;
  gap: 4px;
}

.chip {
  font: inherit;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 10px;
  border: 1px solid #E5E7EB;
  background: #FFF;
  color: #6B7280;
  border-radius: 999px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chip:hover {
  color: #000;
  border-color: #CCC;
}

.chip.active {
  background: #000;
  color: #FFF;
  border-color: #000;
}

.sort-select {
  font: inherit;
  font-size: 11px;
  padding: 4px 8px;
  border: 1px solid #E5E7EB;
  border-radius: 4px;
  background: #FFF;
  color: #374151;
  cursor: pointer;
}

/* Body - two columns */
.explorer-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.agents-column {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid #EAEAEA;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
}

.agents-column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px 6px;
  border-bottom: 1px solid #F3F4F6;
}

.col-label {
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.col-count {
  font-size: 10px;
  color: #9CA3AF;
}

.empty-list {
  padding: 24px 16px;
  color: #9CA3AF;
  font-size: 12px;
  text-align: center;
}

.agent-list {
  list-style: none;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
  flex: 1;
}

.agent-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.agent-row:hover {
  background: #F3F4F6;
}

.agent-row.active {
  background: #111;
  color: #FFF;
}

.agent-row.active .agent-sub {
  color: #D1D5DB;
}

.agent-row.active .agent-badge {
  background: rgba(255,255,255,0.15);
  color: #FFF;
  border-color: transparent;
}

.agent-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #E5E7EB;
  color: #374151;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-row.active .agent-avatar {
  background: #FFF;
  color: #000;
}

.agent-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.agent-name {
  font-size: 12px;
  font-weight: 600;
  color: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-sub {
  font-size: 10px;
  color: #6B7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-badge {
  font-size: 10px;
  padding: 2px 6px;
  border: 1px solid #E5E7EB;
  border-radius: 999px;
  color: #6B7280;
}

/* Detail */
.detail-column {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px 40px;
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
  color: #9CA3AF;
  font-size: 13px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid #EAEAEA;
  margin-bottom: 18px;
}

.detail-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #111;
  color: #FFF;
  font-weight: 700;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.detail-id {
  flex: 1;
  min-width: 0;
}

.detail-name {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: #111;
}

.detail-meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6B7280;
}

.detail-handle {
  font-family: 'JetBrains Mono', monospace;
  color: #374151;
}

.chat-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  padding: 7px 12px;
  background: #111;
  color: #FFF;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chat-cta:hover {
  background: #000;
}

.block-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6B7280;
  margin-bottom: 6px;
}

.detail-bio {
  margin-bottom: 18px;
}

.detail-bio p {
  font-size: 13px;
  color: #374151;
  line-height: 1.55;
  margin: 0;
  white-space: pre-wrap;
}

/* Stats */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 14px 0 20px;
}

.stat-cell {
  border: 1px solid #EAEAEA;
  padding: 10px 12px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: #FAFAFA;
}

.stat-num {
  font-size: 20px;
  font-weight: 700;
  color: #111;
}

.stat-lbl {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6B7280;
}

/* Activity */
.activity-section {
  margin-top: 12px;
}

.activity-loading,
.activity-empty,
.activity-error {
  padding: 20px 10px;
  text-align: center;
  color: #9CA3AF;
  font-size: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

.activity-error {
  color: #B91C1C;
}

.loading-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #E5E7EB;
  border-top-color: #111;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.activity-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.activity-item {
  display: flex;
  gap: 14px;
  padding: 10px 12px;
  border: 1px solid #EAEAEA;
  border-radius: 4px;
  background: #FFF;
  transition: border-color 0.15s ease;
}

.activity-item:hover {
  border-color: #D1D5DB;
}

.activity-item.twitter {
  border-left: 3px solid #000;
}

.activity-item.reddit {
  border-left: 3px solid #6B7280;
}

.act-meta-col {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
  min-width: 56px;
}

.act-round {
  font-size: 11px;
  font-weight: 700;
  color: #111;
}

.act-time {
  font-size: 9px;
  color: #9CA3AF;
}

.act-platform {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}

.act-platform.twitter {
  background: #111;
  color: #FFF;
}

.act-platform.reddit {
  background: #6B7280;
  color: #FFF;
}

.act-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.act-badge {
  align-self: flex-start;
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.06em;
}

.badge-post { background: #FEF3C7; color: #92400E; }
.badge-comment { background: #DBEAFE; color: #1E40AF; }
.badge-action { background: #F3F4F6; color: #374151; }
.badge-idle { background: #F9FAFB; color: #9CA3AF; }

.act-content {
  font-size: 12px;
  color: #374151;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Responsive: narrow list when container is small */
@media (max-width: 820px) {
  .agents-column {
    width: 210px;
  }
  .stats-strip {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
