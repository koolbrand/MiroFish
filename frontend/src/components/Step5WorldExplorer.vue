<template>
  <div class="world-explorer">
    <!-- Header with search + filters -->
    <div class="explorer-header">
      <div class="search-wrapper">
        <svg class="search-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
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
          type="button"
          class="chip"
          :class="{ active: filters.platform === opt.key }"
          :aria-pressed="filters.platform === opt.key"
          @click="filters.platform = opt.key"
        >
          {{ opt.label }}
        </button>
      </div>
      <select v-model="filters.sort" class="sort-select" :aria-label="$t('step2.sortLabel')">
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

        <div v-if="filteredAgents.length === 0" class="empty-list" role="status">
          {{ $t('step2.noProfilesMatch') }}
        </div>

        <ul v-else class="agent-list">
          <!-- cada fila es un botón: se recorre con Tab y se elige con Intro (antes, un <li> con clic) -->
          <li v-for="item in filteredAgents" :key="item.__idx">
            <button
              type="button"
              class="agent-row"
              :class="{ active: selectedIdx === item.__idx }"
              :aria-pressed="selectedIdx === item.__idx"
              @click="selectAgent(item.__idx)"
            >
              <span class="agent-avatar" aria-hidden="true">{{ (item.username || 'A')[0] }}</span>
              <span class="agent-meta">
                <span class="agent-name">{{ item.username || `agent_${item.__idx}` }}</span>
                <span class="agent-sub">
                  {{ item.profession || $t('step2.unknownProfession') }}
                  <template v-if="item.age">· {{ item.age }}</template>
                </span>
              </span>
              <span v-if="activityCounts[item.__idx]" class="agent-badge mono" :title="$t('step5.statTotalActions')">
                {{ activityCounts[item.__idx] }}
              </span>
            </button>
          </li>
        </ul>
      </aside>

      <!-- Right: selected agent detail -->
      <section class="detail-column">
        <div v-if="!selectedAgent" class="detail-empty">
          <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <circle cx="12" cy="8" r="4"></circle>
            <path d="M4 20c0-4 4-7 8-7s8 3 8 7"></path>
          </svg>
          <p>{{ $t('step5.explorerPickAgent') }}</p>
        </div>

        <template v-else>
          <header class="detail-header">
            <div class="detail-avatar" aria-hidden="true">{{ (selectedAgent.username || 'A')[0] }}</div>
            <div class="detail-id">
              <h3 class="detail-name">{{ selectedAgent.username || `agent_${selectedIdx}` }}</h3>
              <div class="detail-meta-row">
                <span v-if="selectedAgent.name" class="detail-handle">@{{ selectedAgent.name }}</span>
                <span class="detail-profession">{{ selectedAgent.profession || $t('step2.unknownProfession') }}</span>
                <span v-if="selectedAgent.age" class="detail-age">· {{ selectedAgent.age }}</span>
                <span v-if="selectedAgent.gender" class="detail-gender">· {{ genderLabel(selectedAgent.gender) }}</span>
              </div>
            </div>
            <button type="button" class="chat-cta" @click="$emit('chat-with-agent', selectedIdx)">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              {{ $t('step5.chatWithThisAgent') }}
            </button>
          </header>

          <div v-if="selectedAgent.bio" class="detail-bio">
            <div class="block-label">{{ $t('step5.profileBio') }}</div>
            <MiniMarkdown class="bio-text" :text="selectedAgent.bio" />
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

            <div v-if="activityLoading" class="activity-loading" role="status">
              <span class="loading-spinner" aria-hidden="true"></span>
              {{ $t('step5.loadingActivity') }}
            </div>

            <!-- error: frase clara y el texto técnico plegado -->
            <div v-else-if="activityError" class="activity-error" role="alert">
              <p class="activity-error-title">{{ $t('step5.activityFailed') }}</p>
              <details class="notice-details">
                <summary>{{ $t('main.failDetails') }}</summary>
                <code>{{ activityError }}</code>
              </details>
            </div>

            <div v-else-if="agentActions.length === 0" class="activity-empty" role="status">
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
                  <span class="act-round mono">{{ $t('step3.roundShort', { n: act.round_num }) }}</span>
                  <span class="act-time mono">{{ formatTime(act.timestamp) }}</span>
                  <span class="act-platform" :class="act.platform" :title="platformLong(act.platform)">{{ platformShort(act.platform) }}</span>
                </div>
                <div class="act-body">
                  <span class="act-badge" :class="actionClass(act.action_type)">
                    {{ actionLabel(act.action_type) }}
                  </span>
                  <MiniMarkdown v-if="hasOwnText(act)" class="act-content" :text="describeAction(act)" />
                  <div v-else class="act-content">{{ describeAction(act) }}</div>
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
import { MiniMarkdown, stripMarkdown } from '../lib/miniMarkdown'

const { t, te } = useI18n()

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
    // se guarda el texto técnico para el detalle plegado; la frase que se ve es step5.activityFailed
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

// Plataforma con el nombre que usa la app («Plaza», «Comunidad»), no «TW»/«RD»
const platformShort = (p) => {
  if (p === 'twitter') return t('step5.platformShortTwitter')
  if (p === 'reddit') return t('step5.platformShortReddit')
  return (p || '??').toUpperCase().slice(0, 2)
}
const platformLong = (p) => (p === 'twitter' ? t('step3.platformTwitter') : p === 'reddit' ? t('step3.platformReddit') : (p || ''))

// Mismos rótulos que el paso 3 (step3.actions.*)
const actionLabel = (type) => (type && te(`step3.actions.${type}`) ? t(`step3.actions.${type}`) : (type || t('common.unknown')))

const genderLabel = (g) => ({ male: t('step2.genderMale'), female: t('step2.genderFemale'), other: t('step2.genderOther') }[String(g || '').toLowerCase()] || g)

// Lo que escribió la propia persona (post, comentario, cita) se pinta con Markdown; el resto es una frase hecha
const hasOwnText = (act) => ['CREATE_POST', 'QUOTE_POST', 'CREATE_COMMENT'].includes(act.action_type)

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

// sin marcas de Markdown antes de recortar (si no, quedan «**» sueltos)
const truncate = (s, n) => {
  if (!s) return ''
  const plain = stripMarkdown(s).replace(/\s+/g, ' ').trim()
  return plain.length > n ? plain.slice(0, n) + '…' : plain
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
  font-family: var(--kb-font-sans);
}

.mono {
  font-family: var(--kb-font-mono);
}

/* Header */
.explorer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--kb-line);
  flex-wrap: wrap;
  background: var(--kb-surface-2);
}

.search-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  box-sizing: border-box;
  padding: 4px 10px;
  border: 1px solid var(--kb-control-line);
  border-radius: 999px;
  background: #FFF;
  flex: 1 1 180px;
  min-width: 160px;
}

.search-wrapper:focus-within {
  border-color: var(--kb-text);
  box-shadow: 0 0 0 1px var(--kb-text);
}

.search-wrapper .search-icon {
  color: var(--kb-subtle);
}

.search-wrapper input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font: inherit;
  font-size: 12px;
  color: var(--kb-text);
  min-width: 0;
}

.search-wrapper input::placeholder {
  color: var(--kb-subtle);
}

.filter-chips {
  display: flex;
  gap: 4px;
}

.chip {
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  min-height: 24px;
  padding: 3px 10px;
  white-space: nowrap;
  border: 1px solid var(--kb-control-line);
  background: #FFF;
  color: var(--kb-muted);
  border-radius: 999px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chip:hover {
  color: var(--kb-text);
  border-color: var(--kb-text);
}

.chip.active {
  background: var(--kb-text);
  color: #FFF;
  border-color: var(--kb-text);
}

.sort-select {
  font: inherit;
  font-size: 12px;
  min-height: 30px;
  padding: 4px 8px;
  border: 1px solid var(--kb-control-line);
  border-radius: 4px;
  background: #FFF;
  color: var(--kb-text-2);
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
  border-right: 1px solid var(--kb-line);
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
}

.agents-column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px 6px;
  border-bottom: 1px solid var(--kb-soft);
}

.col-label {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--kb-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.col-count {
  font-size: 11px;
  color: var(--kb-subtle);
}

.empty-list {
  padding: 24px 16px;
  color: var(--kb-subtle);
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
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 4px;
  background: none;
  font: inherit;
  color: var(--kb-text);
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
}

.agent-row:focus-visible {
  outline: 2px solid var(--kb-text);
  outline-offset: -2px;
}

.agent-row:hover {
  background: var(--kb-soft);
}

.agent-row.active {
  background: var(--kb-text);
  color: #FFF;
}

.agent-row.active .agent-sub {
  color: var(--kb-line-strong);
}

.agent-row.active .agent-badge {
  background: var(--kb-text-2);
  color: #FFF;
  border-color: transparent;
}

.agent-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--kb-line);
  color: var(--kb-text-2);
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-row.active .agent-avatar {
  background: #FFF;
  color: var(--kb-text);
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
  font-size: 12px;
  color: var(--kb-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-badge {
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--kb-line);
  border-radius: 999px;
  color: var(--kb-muted);
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
  color: var(--kb-subtle);
  font-size: 13px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--kb-line);
  margin-bottom: 18px;
}

.detail-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--kb-text);
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
  color: var(--kb-text);
}

.detail-meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--kb-muted);
}

.detail-handle {
  font-family: var(--kb-font-mono);
  color: var(--kb-text-2);
}

.chat-cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  padding: 7px 12px;
  background: var(--kb-text);
  color: #FFF;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chat-cta:hover {
  background: var(--kb-text-2);
}

.block-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--kb-muted);
  margin-bottom: 6px;
}

.detail-bio {
  margin-bottom: 18px;
}

.bio-text {
  font-size: 13px;
  color: var(--kb-text-2);
  line-height: 1.55;
}
.bio-text :deep(.md-p) { margin: 0 0 6px; }
.bio-text :deep(.md-p:last-child) { margin-bottom: 0; }
.bio-text :deep(strong), .act-content :deep(strong) { font-weight: 700; color: var(--kb-text); }
.act-content :deep(.md-p) { margin: 0 0 6px; }
.act-content :deep(.md-p:last-child) { margin-bottom: 0; }
.act-content :deep(.md-ul), .act-content :deep(.md-ol) { margin: 0 0 6px; padding-left: 18px; }
.act-content :deep(.md-quote) { margin: 0 0 6px; padding-left: 10px; border-left: 2px solid var(--kb-line-strong); }

/* Stats */
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 14px 0 20px;
}

.stat-cell {
  border: 1px solid var(--kb-line);
  padding: 10px 12px;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--kb-surface-2);
}

.stat-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--kb-text);
}

.stat-lbl {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--kb-muted);
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
  color: var(--kb-subtle);
  font-size: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

.activity-error {
  display: block;
  margin-top: 4px;
  padding: 12px 14px;
  text-align: left;
  color: var(--kb-text-2);
  background: var(--kb-surface);
  border: 1px solid var(--kb-danger-line);
  border-left-width: 4px;
  border-radius: 4px;
}
.activity-error-title { margin: 0; font-size: 13px; font-weight: 600; color: var(--kb-text); }
.notice-details { margin-top: 6px; font-size: 12px; color: var(--kb-muted); }
.notice-details summary { cursor: pointer; }
.notice-details code {
  display: block; margin-top: 6px; padding: 8px 10px; white-space: pre-wrap;
  background: var(--kb-surface-2); border: 1px solid var(--kb-line); border-radius: 4px;
  font-family: var(--kb-font-mono); font-size: 12px; color: var(--kb-text-2); overflow-wrap: anywhere;
}

.loading-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--kb-line);
  border-top-color: var(--kb-text);
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
  border: 1px solid var(--kb-line);
  border-radius: 4px;
  background: #FFF;
  transition: border-color 0.15s ease;
}

.activity-item:hover {
  border-color: var(--kb-line-strong);
}

.activity-item.twitter {
  border-left: 3px solid var(--kb-text);
}

.activity-item.reddit {
  border-left: 3px solid var(--kb-muted);
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
  color: var(--kb-text);
}

.act-time {
  font-size: 11px;
  color: var(--kb-subtle);
}

.act-platform {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  text-transform: uppercase;
  padding: 1px 5px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}

.act-platform.twitter {
  background: var(--kb-text);
  color: #FFF;
}

.act-platform.reddit {
  background: var(--kb-muted);
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
  font-family: var(--kb-font-mono);
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.06em;
}

/* Tipos de acción: el rótulo dice cuál es; el fondo, de la marca (antes ámbar y azul ajenos) */
.badge-post { background: var(--kb-accent-subtle); color: var(--kb-accent-text); }
.badge-comment { background: var(--kb-soft); color: var(--kb-text-on-soft); }
.badge-action { background: var(--kb-surface-2); color: var(--kb-text-2); }
.badge-idle { background: var(--kb-surface-2); color: var(--kb-subtle); }

.act-content {
  font-size: 12px;
  color: var(--kb-text-2);
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
