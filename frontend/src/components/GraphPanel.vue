<template>
  <div class="graph-panel" ref="panelEl">
    <!-- Cabecera clara (como el resto de la app): título, estado y herramientas -->
    <header class="gp-head">
      <div class="gp-heading">
        <h2 class="panel-title">{{ $t('graph.panelTitle') }}</h2>
        <div class="gp-status">
          <!-- construyendo / simulando: la memoria del mundo se está escribiendo -->
          <template v-if="isLive">
            <span class="live-chip"><span class="live-dot" aria-hidden="true"></span>{{ $t('graph.live') }}</span>
            <span class="gp-status-text" role="status">{{ isSimulating ? $t('graph.graphMemoryRealtime') : $t('graph.realtimeUpdating') }}</span>
          </template>
          <!-- fin de simulación: aviso descartable -->
          <template v-else-if="showSimulationFinishedHint">
            <span class="gp-status-text finished-hint" role="status">
              <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              {{ $t('graph.pendingContentHint') }}
            </span>
            <button class="hint-close-btn" type="button" @click="dismissFinishedHint" :title="$t('graph.closeHint')" :aria-label="$t('graph.closeHint')">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </template>
          <span v-else-if="hasGraph" class="gp-stats">{{ entitiesText }} · {{ relationsText }}</span>
        </div>
      </div>
      <div class="header-tools">
        <button class="tool-btn" type="button" @click="$emit('refresh')" :disabled="loading" :title="$t('graph.refreshGraph')" :aria-label="$t('graph.refreshGraph')">
          <svg class="icon-refresh" :class="{ spinning: loading }" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" /><polyline points="21 3 21 9 15 9" />
          </svg>
          <span class="btn-text">{{ $t('ui.refresh') }}</span>
        </button>
        <button class="tool-btn icon-only" type="button" @click="$emit('toggle-maximize')" :title="$t('graph.toggleMaximize')" :aria-label="$t('graph.toggleMaximize')">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
      </div>
    </header>

    <!-- Escenario oscuro a sangre: el grafo -->
    <div class="gp-stage" ref="stageEl" :class="{ 'is-live': isLive }">
      <canvas
        ref="canvasEl"
        v-show="hasGraph"
        class="gp-canvas"
        tabindex="0"
        role="img"
        :aria-label="canvasLabel"
        :aria-describedby="`${uid}-help`"
        @keydown="onCanvasKey"
      ></canvas>
      <p :id="`${uid}-help`" class="sr-only">{{ $t('graph.canvasHelp') }}</p>

      <template v-if="hasGraph">
        <!-- Arriba: búsqueda e interruptor de etiquetas de relación -->
        <div class="gp-top" ref="topEl">
          <div class="gp-search">
            <svg class="gp-search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref="searchEl"
              v-model="query"
              class="gp-search-input"
              type="search"
              role="combobox"
              autocomplete="off"
              spellcheck="false"
              aria-autocomplete="list"
              :aria-expanded="searchOpen ? 'true' : 'false'"
              :aria-controls="`${uid}-results`"
              :aria-activedescendant="activeIdx >= 0 && searchOpen && results[activeIdx] ? `${uid}-opt-${activeIdx}` : undefined"
              :aria-label="$t('graph.searchLabel')"
              :placeholder="$t('graph.searchPlaceholder')"
              @focus="searchOpen = true"
              @blur="searchOpen = false; activeIdx = -1"
              @input="searchOpen = true; activeIdx = -1"
              @keydown="onSearchKey"
            />
            <div v-show="searchOpen" class="gp-results">
              <p class="gp-results-head" aria-hidden="true">{{ query.trim() ? $t('graph.searchResults', matchedIds.size) : $t('graph.mainEntities') }}</p>
              <ul :id="`${uid}-results`" role="listbox" :aria-label="$t('graph.searchLabel')">
                <li
                  v-for="(n, i) in results"
                  :key="n.id"
                  :id="`${uid}-opt-${i}`"
                  role="option"
                  :aria-selected="i === activeIdx ? 'true' : 'false'"
                  class="gp-option"
                  :class="{ active: i === activeIdx }"
                  @mousedown.prevent="pickNode(n.id)"
                  @mouseenter="activeIdx = i"
                >
                  <GraphTypeSwatch :type-style="n.style" />
                  <span class="opt-name">{{ n.name }}</span>
                  <span class="opt-type">{{ entityLabel(n.type) }}</span>
                </li>
              </ul>
              <p v-if="query.trim() && !results.length" class="gp-results-empty">{{ $t('graph.searchNoResults', { q: query.trim() }) }}</p>
            </div>
          </div>
          <label class="edge-labels-toggle" :title="$t('graph.showEdgeLabels')">
            <input v-model="showEdgeLabels" type="checkbox" role="switch" class="toggle-input" />
            <span class="slider" aria-hidden="true"></span>
            <span class="toggle-label">{{ $t('graph.showEdgeLabels') }}</span>
          </label>
        </div>

        <!-- Detalle del nodo o de la relación seleccionada -->
        <aside
          v-if="selectedItem"
          ref="detailEl"
          class="detail-panel"
          tabindex="-1"
          :aria-labelledby="`${uid}-detail-title`"
          @keydown.esc.stop="closeDetailPanel(true)"
        >
          <div class="detail-panel-header">
            <div class="detail-head-text">
              <span class="detail-eyebrow">{{ selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship') }}</span>
              <h3 :id="`${uid}-detail-title`" class="detail-title">
                <template v-if="selectedItem.type === 'node'">{{ selectedItem.data.name }}</template>
                <template v-else-if="selectedItem.data.isSelfLoopGroup">{{ selectedItem.data.source_name }}</template>
                <template v-else>{{ relationLabel(selectedItem.data.name || 'RELATED_TO') }}</template>
              </h3>
            </div>
            <button class="detail-close" type="button" @click="closeDetailPanel(true)" :aria-label="$t('graph.closeDetails')" :title="$t('graph.close')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <!-- Nodo -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-type">
              <GraphTypeSwatch v-if="selectedNode" :type-style="selectedNode.style" />
              <span class="detail-type-badge" :title="selectedItem.entityType">{{ entityLabel(selectedItem.entityType) }}</span>
              <span class="detail-degree">{{ $t('graph.relationsCount', selectedNode ? selectedNode.degree + selectedNode.selfLoops : 0) }}</span>
            </div>
            <dl class="detail-rows">
              <div class="detail-row">
                <dt class="detail-label">{{ $t('graph.name') }}</dt>
                <dd class="detail-value">{{ selectedItem.data.name }}</dd>
              </div>
              <div class="detail-row">
                <dt class="detail-label">{{ $t('graph.uuid') }}</dt>
                <dd class="detail-value uuid-text">{{ selectedItem.data.uuid }}</dd>
              </div>
              <div class="detail-row" v-if="nodeCreated">
                <dt class="detail-label">{{ $t('graph.created') }}</dt>
                <dd class="detail-value">{{ formatDateTime(nodeCreated) }}</dd>
              </div>
            </dl>

            <div class="detail-section" v-if="selectedItem.data.summary">
              <h4 class="section-title">{{ $t('graph.summary') }}</h4>
              <p class="summary-text">{{ selectedItem.data.summary }}</p>
            </div>

            <div class="detail-section" v-if="nodeConnections.length">
              <h4 class="section-title">{{ $t('graph.connections') }}</h4>
              <ul class="conn-list">
                <li v-for="c in nodeConnections" :key="c.key">
                  <button type="button" class="conn-item" @click="c.self ? pickEdge(c.edgeId) : pickNode(c.otherId)">
                    <span class="conn-arrow" aria-hidden="true">{{ c.self ? '↻' : c.out ? '→' : '←' }}</span>
                    <span class="conn-rel">{{ c.rel }}</span>
                    <span class="conn-name">{{ c.name }}</span>
                  </button>
                </li>
              </ul>
            </div>

            <div class="detail-section" v-if="nodeProps.length">
              <h4 class="section-title">{{ $t('graph.properties') }}</h4>
              <dl class="properties-list">
                <div v-for="p in nodeProps" :key="p.key" class="property-item">
                  <dt class="property-key">{{ p.label }}</dt>
                  <dd class="property-value">{{ p.value }}</dd>
                </div>
              </dl>
            </div>

            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <h4 class="section-title">{{ $t('graph.labels') }}</h4>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag" :title="label">{{ entityLabel(label) }}</span>
              </div>
            </div>
          </div>

          <!-- Relación -->
          <div v-else class="detail-content">
            <!-- grupo de autobucles -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                <span>{{ selectedItem.data.source_name }} — {{ $t('ui.selfRelations') }}</span>
                <span class="self-loop-count">{{ $t('graph.itemsCount', selectedItem.data.selfLoopCount) }}</span>
              </div>
              <ul class="self-loop-list">
                <li
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges"
                  :key="loop.uuid || idx"
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <button
                    type="button"
                    class="self-loop-item-header"
                    :aria-expanded="expandedSelfLoops.has(loop.uuid || idx) ? 'true' : 'false'"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ relationLabel(loop.name || loop.fact_type || 'RELATED') }}</span>
                    <span class="self-loop-toggle" aria-hidden="true">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </button>
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <dl class="detail-rows">
                      <div class="detail-row" v-if="loop.uuid">
                        <dt class="detail-label">{{ $t('graph.uuid') }}</dt>
                        <dd class="detail-value uuid-text">{{ loop.uuid }}</dd>
                      </div>
                      <div class="detail-row" v-if="loop.fact">
                        <dt class="detail-label">{{ $t('graph.fact') }}</dt>
                        <dd class="detail-value fact-text">{{ loop.fact }}</dd>
                      </div>
                      <div class="detail-row" v-if="loop.fact_type">
                        <dt class="detail-label">{{ $t('graph.type') }}</dt>
                        <dd class="detail-value">{{ loop.fact_type }}</dd>
                      </div>
                      <div class="detail-row" v-if="loop.created_at">
                        <dt class="detail-label">{{ $t('graph.created') }}</dt>
                        <dd class="detail-value">{{ formatDateTime(loop.created_at) }}</dd>
                      </div>
                    </dl>
                    <div v-if="episodesOf(loop).length" class="self-loop-episodes">
                      <span class="detail-label">{{ $t('graph.episodes') }}</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in episodesOf(loop)" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </li>
              </ul>
            </template>

            <!-- arista normal -->
            <template v-else>
              <div class="edge-relation-header">
                <button type="button" class="edge-end" @click="pickNode(selectedItem.data.source_node_uuid)">{{ selectedItem.data.source_name }}</button>
                <span class="edge-mid"><span aria-hidden="true">→</span> {{ relationLabel(selectedItem.data.name || 'RELATED_TO') }} <span aria-hidden="true">→</span></span>
                <button type="button" class="edge-end" @click="pickNode(selectedItem.data.target_node_uuid)">{{ selectedItem.data.target_name }}</button>
              </div>
              <dl class="detail-rows">
                <div class="detail-row" v-if="selectedItem.data.fact">
                  <dt class="detail-label">{{ $t('graph.fact') }}</dt>
                  <dd class="detail-value fact-text">{{ selectedItem.data.fact }}</dd>
                </div>
                <div class="detail-row">
                  <dt class="detail-label">{{ $t('graph.label') }}</dt>
                  <dd class="detail-value mono">{{ selectedItem.data.name || 'RELATED_TO' }}</dd>
                </div>
                <div class="detail-row">
                  <dt class="detail-label">{{ $t('graph.type') }}</dt>
                  <dd class="detail-value mono">{{ selectedItem.data.fact_type || $t('graph.unknown') }}</dd>
                </div>
                <div class="detail-row">
                  <dt class="detail-label">{{ $t('graph.uuid') }}</dt>
                  <dd class="detail-value uuid-text">{{ selectedItem.data.uuid }}</dd>
                </div>
                <div class="detail-row" v-if="selectedItem.data.created_at">
                  <dt class="detail-label">{{ $t('graph.created') }}</dt>
                  <dd class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</dd>
                </div>
                <div class="detail-row" v-if="edgeValidAt">
                  <dt class="detail-label">{{ $t('graph.validFrom') }}</dt>
                  <dd class="detail-value">{{ formatDateTime(edgeValidAt) }}</dd>
                </div>
              </dl>
              <div class="detail-section" v-if="episodesOf(selectedItem.data).length">
                <h4 class="section-title">{{ $t('graph.episodes') }}</h4>
                <div class="episodes-list">
                  <span v-for="ep in episodesOf(selectedItem.data)" :key="ep" class="episode-tag">{{ ep }}</span>
                </div>
              </div>
            </template>
          </div>
        </aside>

        <!-- Abajo: leyenda (forma + tono) y zoom -->
        <div class="gp-bottom" ref="bottomEl">
          <div v-if="legendTypes.length" class="graph-legend" :class="{ open: legendOpen }">
            <button type="button" class="legend-title" :aria-expanded="legendOpen ? 'true' : 'false'" :aria-controls="`${uid}-legend`" @click="legendOpen = !legendOpen">
              {{ $t('graph.entityTypes') }}
              <span class="legend-total">{{ legendTypes.length }}</span>
              <svg class="legend-chevron" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 15 12 9 18 15" /></svg>
            </button>
            <ul v-show="legendOpen" :id="`${uid}-legend`" class="legend-items">
              <li v-for="ty in legendTypes" :key="ty.key">
                <button
                  type="button"
                  class="legend-item"
                  :aria-pressed="pinnedType === ty.key ? 'true' : 'false'"
                  :title="ty.title"
                  @mouseenter="previewType = ty.key"
                  @mouseleave="previewType = null"
                  @focus="previewType = ty.key"
                  @blur="previewType = null"
                  @click="pinnedType = pinnedType === ty.key ? null : ty.key"
                >
                  <GraphTypeSwatch :type-style="ty.style" />
                  <span class="legend-label">{{ ty.label }}</span>
                  <span class="legend-num">{{ ty.count }}</span>
                </button>
              </li>
            </ul>
          </div>
          <div class="gp-zoom" role="group">
            <button type="button" @click="zoomIn" :aria-label="$t('graph.zoomIn')" :title="$t('graph.zoomIn')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
            </button>
            <button type="button" @click="zoomOut" :aria-label="$t('graph.zoomOut')" :title="$t('graph.zoomOut')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12" /></svg>
            </button>
            <button type="button" @click="fitView" :aria-label="$t('graph.fit')" :title="$t('graph.fit')">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" /><circle cx="12" cy="12" r="2.5" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Para lectores de pantalla (y teclado): las entidades principales. Visible solo cuando recibe el foco. -->
        <nav class="gp-sr-list" :aria-label="$t('graph.mainEntities')">
          <h3 class="gp-sr-title">{{ $t('graph.mainEntities') }}</h3>
          <ul>
            <li v-for="n in mainEntities" :key="n.id">
              <button type="button" @click="pickNode(n.id)">
                {{ $t('graph.entityOption', { name: n.name, type: entityLabel(n.type), relations: $t('graph.relationsCount', n.degree + n.selfLoops) }) }}
              </button>
            </li>
          </ul>
          <p v-if="moreEntities > 0" class="gp-sr-more">{{ $t('graph.mainEntitiesMore', { n: moreEntities }) }}</p>
        </nav>
      </template>

      <!-- Cargando -->
      <div v-else-if="loading" class="graph-state" role="status">
        <div class="state-art" aria-hidden="true">
          <span class="orbit orbit-a"><i></i></span>
          <span class="orbit orbit-b"><i></i></span>
          <BiankaAvatar :look="{ ears: 'up', head: 'hardhat' }" bucket="undecided" :pixel="4" talking />
        </div>
        <p class="state-title">{{ $t('graph.graphDataLoading') }}</p>
        <p class="state-hint">{{ $t('graph.loadingHint') }}</p>
      </div>

      <!-- Esperando la ontología -->
      <div v-else class="graph-state">
        <div class="state-art" aria-hidden="true">
          <svg class="ghost" viewBox="0 0 240 150">
            <path d="M40 40 L92 70 L150 34 L204 62 M92 70 L120 116 L186 110 M150 34 L186 110" />
            <circle cx="40" cy="40" r="5" /><circle cx="150" cy="34" r="6" /><circle cx="204" cy="62" r="4" />
            <circle cx="120" cy="116" r="5" /><circle cx="186" cy="110" r="4" /><circle class="ghost-hub" cx="92" cy="70" r="7" />
          </svg>
          <BiankaAvatar :look="{ ears: 'classic', face: 'glasses' }" bucket="undecided" :pixel="4" />
        </div>
        <p class="state-title">{{ $t('graph.waitingOntology') }}</p>
        <p class="state-hint">{{ $t('graph.emptyHint') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { ref, shallowRef, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import BiankaAvatar from './BiankaAvatar.vue'
import GraphTypeSwatch from './GraphTypeSwatch.vue'
import { GraphRenderer, buildGraphModel, OTHER_KEY } from '../lib/graphRender'
import { entityLabel, relationLabel, typeLabelsVersion } from '../lib/typeLabels'

const { t, locale } = useI18n()

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const uid = `gp-${Math.random().toString(36).slice(2, 8)}`
const panelEl = ref(null)
const stageEl = ref(null)
const canvasEl = ref(null)
const topEl = ref(null)
const bottomEl = ref(null)
const detailEl = ref(null)
const searchEl = ref(null)

const selectedItem = ref(null)
const showEdgeLabels = ref(true) // 默认显示边标签
const expandedSelfLoops = ref(new Set()) // 展开的自环项
const showSimulationFinishedHint = ref(false) // 模拟结束后的提示
const wasSimulating = ref(false)

const model = shallowRef(null)
const styleMemory = new Map() // tipo → estilo, estable entre refrescos
let renderer = null

const query = ref('')
const searchOpen = ref(false)
const activeIdx = ref(-1)
const previewType = ref(null)
const pinnedType = ref(null)
const narrow = ref(false)
const legendOpen = ref(true)

const hasGraph = computed(() => !!model.value && model.value.nodes.length > 0)
const isLive = computed(() => hasGraph.value && (props.currentPhase === 1 || !!props.isSimulating))

// ── Avisos ────────────────────────────────────────────────────────────────
const dismissFinishedHint = () => { showSimulationFinishedHint.value = false }

watch(() => props.isSimulating, (newValue) => {
  if (wasSimulating.value && !newValue) showSimulationFinishedHint.value = true
  wasSimulating.value = newValue
}, { immediate: true })

const toggleSelfLoop = (id) => {
  const next = new Set(expandedSelfLoops.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedSelfLoops.value = next
}

// ── Textos derivados ──────────────────────────────────────────────────────
const entitiesText = computed(() => t('graph.entitiesCount', model.value?.nodes.length || 0))
const relationsText = computed(() => t('graph.relationsCount', model.value?.relationCount || 0))
const typeLabel = (ty) => (ty.key === OTHER_KEY ? t('graph.otherTypes') : entityLabel(ty.name))

const legendTypes = computed(() => (model.value?.types || []).map(ty => ({
  ...ty,
  label: typeLabel(ty),
  title: ty.key === OTHER_KEY ? t('graph.otherTypesList', { list: ty.members.map(entityLabel).join(', ') }) : t('graph.highlightType', { type: entityLabel(ty.name) }),
})))

const canvasLabel = computed(() => {
  const m = model.value
  if (!m) return t('graph.panelTitle')
  const types = m.types.map(ty => `${ty.key === OTHER_KEY ? ty.members.map(entityLabel).join(', ') : entityLabel(ty.name)} (${ty.count})`).join(', ')
  return t('graph.canvasLabel', { entities: entitiesText.value, relations: relationsText.value, types })
})

const MAIN_LIMIT = 30
const mainEntities = computed(() => (model.value?.byPriority || []).slice(0, MAIN_LIMIT))
const moreEntities = computed(() => Math.max(0, (model.value?.nodes.length || 0) - MAIN_LIMIT))

// ── Búsqueda ──────────────────────────────────────────────────────────────
const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const matches = computed(() => {
  const m = model.value
  const q = norm(query.value.trim())
  if (!m || !q) return []
  const out = []
  for (const n of m.byPriority) {
    const nn = n._norm || (n._norm = norm(n.name))
    const i = nn.indexOf(q)
    if (i === 0) out.push([0, n])
    else if (i > 0) out.push([nn.includes(` ${q}`) ? 1 : 2, n])
    else if (norm(n.type).includes(q) || norm(entityLabel(n.type)).includes(q)) out.push([3, n])
  }
  return out.sort((a, b) => a[0] - b[0]).map(x => x[1])
})
const matchedIds = computed(() => new Set(matches.value.map(n => n.id)))
const results = computed(() => (query.value.trim() ? matches.value : (model.value?.byPriority || [])).slice(0, 8))

const onSearchKey = (e) => {
  const n = results.value.length
  if (e.key === 'ArrowDown') { e.preventDefault(); searchOpen.value = true; if (n) activeIdx.value = (activeIdx.value + 1) % n }
  else if (e.key === 'ArrowUp') { e.preventDefault(); searchOpen.value = true; if (n) activeIdx.value = activeIdx.value <= 0 ? n - 1 : activeIdx.value - 1 }
  else if (e.key === 'Enter') {
    const pick = results.value[activeIdx.value >= 0 ? activeIdx.value : 0]
    if (pick) { e.preventDefault(); pickNode(pick.id) }
  } else if (e.key === 'Escape') {
    if (query.value) { e.preventDefault(); query.value = ''; activeIdx.value = -1 }
    else if (searchOpen.value) { e.preventDefault(); searchOpen.value = false }
  }
}

// ── Selección ─────────────────────────────────────────────────────────────
const selectedNode = computed(() => (selectedItem.value?.type === 'node' ? model.value?.nodeById.get(selectedItem.value.id) || null : null))

const openNode = (id) => {
  const n = model.value?.nodeById.get(id)
  if (!n) return false
  selectedItem.value = { type: 'node', id, data: n.raw, entityType: n.type, color: `var(${n.style.stroke || n.style.fill})` }
  expandedSelfLoops.value = new Set()
  renderer?.setSelected({ kind: 'node', id })
  return true
}
const openEdge = (id) => {
  const e = model.value?.edgeById.get(id)
  if (!e) return false
  selectedItem.value = { type: 'edge', id, data: e.raw }
  expandedSelfLoops.value = new Set()
  renderer?.setSelected({ kind: 'edge', id })
  return true
}
const closeDetailPanel = (restoreFocus = false) => {
  const had = !!selectedItem.value
  selectedItem.value = null
  expandedSelfLoops.value = new Set() // 重置展开状态
  renderer?.setSelected(null)
  if (had && restoreFocus === true) nextTick(() => canvasEl.value?.focus({ preventScroll: true }))
}

// desde la búsqueda, la lista accesible o una conexión del panel: abre, centra y lleva el foco al detalle
const pickNode = (id) => {
  if (!openNode(id)) return
  query.value = ''
  searchOpen.value = false
  activeIdx.value = -1
  nextTick(() => {
    updateInsets()
    renderer?.centerOn(id)
    detailEl.value?.focus({ preventScroll: true })
  })
}
const pickEdge = (id) => {
  if (!openEdge(id)) return
  nextTick(() => detailEl.value?.focus({ preventScroll: true }))
}

const onRendererSelect = (sel) => {
  if (!sel) return closeDetailPanel()
  if (sel.kind === 'node') {
    if (openNode(sel.id)) nextTick(() => { updateInsets(); renderer?.ensureVisible(sel.id, { minK: narrow.value ? 1 : 0 }) })
  } else openEdge(sel.id)
}

const nodeCreated = computed(() => selectedItem.value?.data?.created_at || selectedItem.value?.data?.attributes?.created_at || null)
const edgeValidAt = computed(() => selectedItem.value?.data?.valid_at || selectedItem.value?.data?.attributes?.valid_at || null)
const episodesOf = (d) => {
  if (!d) return []
  if (Array.isArray(d.episodes) && d.episodes.length) return d.episodes
  return Array.isArray(d.attributes?.episodes) ? d.attributes.episodes : []
}

// Propiedades sin ruido: fuera los vectores de embedding (768 números) y lo que ya se muestra arriba
const HIDDEN_ATTR = /(^|_)embedding$|^(labels|created_at|name|uuid|summary)$/
const fmtValue = (v) => {
  if (v == null || v === '') return t('graph.noValue')
  if (Array.isArray(v)) return v.length ? v.join(', ') : t('graph.noValue')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
const nodeProps = computed(() => {
  const attrs = selectedItem.value?.type === 'node' ? selectedItem.value.data?.attributes : null
  if (!attrs) return []
  return Object.entries(attrs)
    .filter(([k]) => !HIDDEN_ATTR.test(k))
    .map(([k, v]) => ({ key: k, label: k.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()), value: fmtValue(v) }))
})

const nodeConnections = computed(() => {
  const n = selectedNode.value
  const m = model.value
  if (!n || !m) return []
  return n.links.slice(0, 40).map(e => {
    if (e.self) return { key: e.id, self: true, edgeId: e.id, rel: t('ui.selfRelations'), name: `(${e.count})` }
    const out = e.sid === n.id
    const other = m.nodeById.get(out ? e.tid : e.sid)
    return { key: e.id, self: false, out, otherId: other?.id, rel: relationLabel(e.name), name: other?.name || '—' }
  })
})

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  // Graphiti devuelve nanosegundos («…03.058450000+00:00»): se recortan a milisegundos para que Date lo entienda
  const date = new Date(String(dateStr).replace(/(\.\d{3})\d+/, '$1'))
  if (Number.isNaN(date.getTime())) return String(dateStr)
  try {
    return date.toLocaleString(locale.value || undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
  } catch {
    return date.toISOString()
  }
}

// ── Vista ─────────────────────────────────────────────────────────────────
const fitView = () => renderer?.fit(true)
const zoomIn = () => renderer?.zoomBy(1.4)
const zoomOut = () => renderer?.zoomBy(1 / 1.4)

const onCanvasKey = (e) => {
  if (!renderer) return
  const step = e.shiftKey ? 180 : 60
  const keys = {
    ArrowLeft: () => renderer.panBy(step, 0), ArrowRight: () => renderer.panBy(-step, 0),
    ArrowUp: () => renderer.panBy(0, step), ArrowDown: () => renderer.panBy(0, -step),
    '+': () => renderer.zoomBy(1.3), '=': () => renderer.zoomBy(1.3), '-': () => renderer.zoomBy(1 / 1.3), _: () => renderer.zoomBy(1 / 1.3),
    0: () => renderer.fit(true), Escape: () => { if (selectedItem.value) closeDetailPanel(); else { pinnedType.value = null; query.value = '' } },
  }
  const fn = keys[e.key]
  if (fn) { e.preventDefault(); fn() }
}

// Lo que tapan los controles del escenario: el encuadre y el centrado los esquivan
const updateInsets = () => {
  if (!renderer || !stageEl.value) return
  const top = topEl.value ? topEl.value.offsetTop + topEl.value.offsetHeight + 8 : 0
  // la leyenda abierta y ancha ocupa la franja de abajo: el grafo se encuadra por encima
  const bottomH = bottomEl.value ? bottomEl.value.offsetHeight : 0
  const legendW = bottomEl.value?.querySelector('.graph-legend')?.offsetWidth || 0
  const wide = legendW > (stageEl.value.clientWidth || 1) * 0.4
  let right = 0, bottom = (wide && legendOpen.value ? bottomH : Math.min(bottomH, 48)) + 12
  if (selectedItem.value && detailEl.value) {
    if (narrow.value) bottom = Math.max(bottom, detailEl.value.offsetHeight + 16)
    else right = detailEl.value.offsetWidth + 24
  }
  renderer.setInsets({ top, right, bottom, left: 0 })
}

// ── Datos ─────────────────────────────────────────────────────────────────
const rebuild = () => {
  const gd = props.graphData
  const m = gd ? buildGraphModel(gd, styleMemory) : null
  model.value = m
  if (!m || !m.nodes.length) {
    renderer?.setModel(null)
    closeDetailPanel()
    return
  }
  // la selección sobrevive al refresco si la entidad sigue ahí (con sus datos al día)
  const sel = selectedItem.value
  if (sel) {
    const ok = sel.type === 'node' ? m.nodeById.has(sel.id) : m.edgeById.has(sel.id)
    if (!ok) closeDetailPanel()
    else if (sel.type === 'node') { const n = m.nodeById.get(sel.id); selectedItem.value = { ...sel, data: n.raw, entityType: n.type } }
    else selectedItem.value = { ...sel, data: m.edgeById.get(sel.id).raw }
  }
  if (pinnedType.value && !m.types.some(ty => ty.key === pinnedType.value)) pinnedType.value = null
  nextTick(() => {
    if (!renderer) return
    measure()
    updateInsets()
    renderer.setModel(m)
    renderer.setHighlight(highlightSet.value)
  })
}

watch(() => [props.graphData, props.graphData?.nodes?.length, props.graphData?.edges?.length], rebuild)

const highlightSet = computed(() => {
  const m = model.value
  if (!m) return null
  const key = previewType.value || pinnedType.value
  if (key) return new Set(m.nodes.filter(n => n.legend === key).map(n => n.id))
  if (query.value.trim()) return matchedIds.value
  return null
})
watch(highlightSet, (s) => renderer?.setHighlight(s))
watch(() => (searchOpen.value && activeIdx.value >= 0 ? results.value[activeIdx.value]?.id : null), (id) => renderer?.setPreview(id))
watch(showEdgeLabels, (v) => renderer?.setShowEdgeLabels(v))
watch(isLive, (v) => renderer?.setLive(v))
watch(selectedItem, () => nextTick(updateInsets))
// Las etiquetas de las relaciones sobre el lienzo siguen al idioma y a las traducciones que llegan del servidor
const rendererStrings = () => ({ selfLoop: (n) => `${t('ui.selfRelations')} (${n})`, relation: relationLabel })
watch([locale, typeLabelsVersion], () => renderer?.setStrings(rendererStrings()))
watch(narrow, (v) => { legendOpen.value = !v; nextTick(updateInsets) })
watch(legendOpen, () => nextTick(updateInsets))

// ── Ciclo de vida ─────────────────────────────────────────────────────────
let ro = null, io = null, mq = null
const measure = () => {
  const el = stageEl.value
  if (!el || !renderer) return
  renderer.resize(el.clientWidth, el.clientHeight)
}
const onVisibility = () => renderer?.setHidden(document.hidden)
const onMotion = () => renderer?.setReducedMotion(!!mq?.matches)

onMounted(() => {
  renderer = new GraphRenderer(canvasEl.value, { onSelect: onRendererSelect })
  if (import.meta.env.DEV) canvasEl.value.__graph = renderer
  mq = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null
  renderer.setReducedMotion(!!mq?.matches)
  mq?.addEventListener?.('change', onMotion)
  renderer.setStrings(rendererStrings())
  renderer.setShowEdgeLabels(showEdgeLabels.value)
  narrow.value = (panelEl.value?.clientWidth || 9999) < 560
  legendOpen.value = !narrow.value

  ro = new ResizeObserver(() => {
    narrow.value = (panelEl.value?.clientWidth || 9999) < 560
    updateInsets()
    measure()
  })
  ro.observe(stageEl.value)
  ro.observe(panelEl.value)
  // fuera de pantalla (o con el panel plegado a 0 en «Mesa de trabajo»): el bucle se para
  io = new IntersectionObserver(([entry]) => renderer?.setVisible(entry.isIntersecting && entry.intersectionRect.width > 0))
  io.observe(stageEl.value)
  document.addEventListener('visibilitychange', onVisibility)
  measure()
  if (props.graphData) rebuild()
  renderer.setLive(isLive.value)
})

onUnmounted(() => {
  ro?.disconnect()
  io?.disconnect()
  document.removeEventListener('visibilitychange', onVisibility)
  mq?.removeEventListener?.('change', onMotion)
  renderer?.destroy()
  renderer = null
})

defineExpose({ fit: fitView })
</script>

<style scoped>
/* Panel: cabecera clara + escenario oscuro. Solo tokens de marca (koolbrand.css). */
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--ink-950);
  font-family: var(--kb-font-sans);
  container-type: inline-size;
}

/* ── Cabecera ── */
.gp-head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 64px;
  padding: 10px 16px 10px 20px;
  background: var(--kb-surface);
  border-bottom: 1px solid var(--ink-950);
}
.gp-heading { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.01em;
  color: var(--kb-text);
}
.gp-status {
  /* flujo de texto: en paneles estrechos el estado empieza junto al chip y parte en dos líneas, no en tres */
  display: block;
  min-height: 20px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--kb-muted);
}
.gp-stats { font-family: var(--kb-font-mono); font-size: 12px; letter-spacing: 0.02em; color: var(--kb-muted); }
.gp-status-text { color: var(--kb-text-2); }
.live-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
  vertical-align: 1px;
  padding: 1px 8px 1px 7px;
  border-radius: 999px;
  background: var(--ink-950);
  color: var(--lime-500);
  font: 600 12px/18px var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--lime-500);
  animation: live-ping 1.6s ease-out infinite;
}
@keyframes live-ping {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--lime-500) 70%, transparent); }
  75%, 100% { box-shadow: 0 0 0 6px color-mix(in srgb, var(--lime-500) 0%, transparent); }
}
.finished-hint { display: inline-flex; align-items: flex-start; gap: 6px; flex: 1 1 0; min-width: 0; }
.gp-status:has(.finished-hint) { display: flex; flex-wrap: nowrap; align-items: flex-start; gap: 8px; }
.hint-icon { width: 15px; height: 15px; flex: none; margin-top: 1px; color: var(--kb-accent-text); }
.hint-close-btn {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--kb-control-line);
  border-radius: 6px;
  background: var(--kb-surface);
  color: var(--kb-text-2);
  cursor: pointer;
}
.hint-close-btn:hover { background: var(--kb-soft); }

.header-tools { flex: none; display: flex; gap: 8px; align-items: center; }
.tool-btn {
  height: 34px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--kb-control-line);
  border-radius: 8px;
  background: var(--kb-surface);
  color: var(--kb-text-2);
  font: 500 13px var(--kb-font-sans);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.tool-btn.icon-only { width: 34px; padding: 0; }
.tool-btn:hover:not(:disabled) { background: var(--kb-accent-solid); border-color: var(--ink-950); color: var(--kb-accent-on); }
.tool-btn:disabled { cursor: default; color: var(--kb-muted); }
.icon-refresh.spinning { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ── Escenario ── */
.gp-stage {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  /* el brillo del escenario (en CSS: en el canvas costaría ~10 ms por fotograma sin aceleración gráfica) */
  background:
    radial-gradient(ellipse 42% 38% at 50% 46%, color-mix(in srgb, var(--lime-500) 5%, transparent), transparent),
    radial-gradient(ellipse 72% 64% at 50% 46%, color-mix(in srgb, var(--ink-800) 85%, transparent), color-mix(in srgb, var(--ink-800) 20%, transparent) 60%, transparent),
    var(--ink-950);
}
.gp-stage.is-live {
  background:
    radial-gradient(ellipse 42% 38% at 50% 46%, color-mix(in srgb, var(--lime-500) 8%, transparent), transparent),
    radial-gradient(ellipse 72% 64% at 50% 46%, color-mix(in srgb, var(--ink-800) 85%, transparent), color-mix(in srgb, var(--ink-800) 20%, transparent) 60%, transparent),
    var(--ink-950);
}
.gp-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; outline: none; }
.gp-canvas:active { cursor: grabbing; }
.gp-canvas:focus-visible { outline: 2px solid var(--lime-500); outline-offset: -3px; }

/* Controles sobre el escenario: anillo de foco doble (tinta + lima) que se ve sobre claro y sobre oscuro */
.gp-top :focus-visible,
.gp-zoom :focus-visible,
.legend-title:focus-visible {
  outline: 2px solid var(--ink-950);
  outline-offset: 0;
  box-shadow: 0 0 0 4px var(--lime-500);
}

.gp-top {
  position: absolute;
  top: 12px;
  left: 12px;
  right: 12px;
  z-index: 6;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}
.gp-top > * { pointer-events: auto; }

.gp-search { position: relative; flex: 0 1 300px; min-width: 0; }
.gp-search-icon { position: absolute; left: 11px; top: 10px; color: var(--kb-muted); pointer-events: none; }
.gp-search-input {
  width: 100%;
  height: 36px;
  padding: 0 12px 0 34px;
  border: 1px solid var(--ink-950);
  border-radius: 8px;
  background: var(--kb-surface);
  color: var(--kb-text);
  font: 500 13px var(--kb-font-sans);
  -webkit-appearance: none;
  appearance: none;
}
.gp-search-input::placeholder { color: var(--gray-600); }
.gp-search-input::-webkit-search-cancel-button { cursor: pointer; }
.gp-results {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  width: max(100%, 280px);
  max-width: calc(100cqw - 24px);
  padding: 6px;
  background: var(--kb-surface);
  border: 1px solid var(--ink-950);
  border-radius: 10px;
  box-shadow: 4px 4px 0 var(--lime-500);
}
.gp-results-head,
.gp-results-empty {
  margin: 0;
  padding: 6px 8px 4px;
  font: 500 12px var(--kb-font-mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--gray-600);
}
.gp-results-empty { text-transform: none; letter-spacing: 0; font-family: var(--kb-font-sans); padding: 8px; }
.gp-results ul { list-style: none; margin: 0; padding: 0; }
.gp-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.gp-option.active { background: var(--lime-50); box-shadow: inset 0 0 0 1px var(--lime-800); }
.opt-name { flex: 1 1 auto; min-width: 0; font-size: 13px; font-weight: 500; color: var(--kb-text); line-height: 1.3; }
.opt-type { flex: none; max-width: 40%; font: 500 12px var(--kb-font-mono); color: var(--gray-600); overflow-wrap: anywhere; text-align: right; }

.edge-labels-toggle {
  flex: none;
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px 0 8px;
  border-radius: 999px;
  background: var(--kb-surface);
  color: var(--kb-text-2);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
}
.toggle-input { position: absolute; inset: 0; opacity: 0; margin: 0; cursor: pointer; }
.edge-labels-toggle:has(.toggle-input:focus-visible) { outline: 2px solid var(--ink-950); box-shadow: 0 0 0 4px var(--lime-500); }
.slider {
  position: relative;
  flex: none;
  width: 34px;
  height: 20px;
  border-radius: 999px;
  background: var(--gray-200);
  border: 1px solid var(--kb-control-line);
  transition: background 0.2s ease, border-color 0.2s ease;
}
.slider::before {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--ink-950);
  transition: transform 0.2s ease;
}
.toggle-input:checked + .slider { background: var(--lime-500); border-color: var(--ink-950); }
.toggle-input:checked + .slider::before { transform: translateX(14px); }

/* ── Detalle ── */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 12px;
  z-index: 8;
  width: 344px;
  max-width: calc(100% - 24px);
  max-height: calc(100% - 72px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--kb-surface);
  border: 1px solid var(--ink-950);
  border-radius: 12px;
  box-shadow: 5px 5px 0 var(--lime-500);
  color: var(--kb-text-2);
  font-size: 13px;
  outline: none;
}
.detail-panel:focus-visible { box-shadow: 5px 5px 0 var(--lime-500), 0 0 0 3px var(--lime-800); }
.detail-panel-header {
  flex: none;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 14px 12px 16px;
  border-bottom: 1px solid var(--ink-950);
  background: var(--cream-100);
}
.detail-head-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.detail-eyebrow { font: 500 12px var(--kb-font-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-600); }
.detail-title { margin: 0; font-size: 17px; font-weight: 700; line-height: 1.25; letter-spacing: -0.01em; color: var(--kb-text); overflow-wrap: anywhere; }
.detail-close {
  flex: none;
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 1px solid var(--kb-control-line);
  border-radius: 8px;
  background: var(--kb-surface);
  color: var(--kb-text);
  cursor: pointer;
}
.detail-close:hover { background: var(--kb-accent-solid); border-color: var(--ink-950); }

.detail-content { flex: 1; min-height: 0; overflow-y: auto; padding: 14px 16px 16px; }
.detail-type { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.detail-type-badge {
  padding: 2px 8px;
  border: 1px solid var(--ink-950);
  border-radius: 4px;
  background: var(--lime-50);
  font: 500 12px/18px var(--kb-font-mono);
  color: var(--kb-text);
  overflow-wrap: anywhere;
}
.detail-degree { font-size: 12px; color: var(--gray-600); }

.detail-rows { margin: 0; display: grid; gap: 8px; }
.detail-row { display: grid; grid-template-columns: 92px 1fr; gap: 10px; align-items: baseline; }
.detail-label { font-size: 12px; font-weight: 500; color: var(--gray-600); }
.detail-value { margin: 0; color: var(--kb-text-2); overflow-wrap: anywhere; line-height: 1.45; }
.detail-value.mono { font: 500 12px var(--kb-font-mono); }
.detail-value.uuid-text { font: 400 12px var(--kb-font-mono); color: var(--gray-600); }
.detail-value.fact-text { line-height: 1.5; color: var(--kb-text); }

.detail-section { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--kb-line); }
.section-title { margin: 0 0 8px; font: 500 12px var(--kb-font-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-600); }
.summary-text { margin: 0; font-size: 13px; line-height: 1.55; color: var(--kb-text-2); }

.conn-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.conn-item {
  width: 100%;
  display: grid;
  grid-template-columns: 16px minmax(0, auto) minmax(0, 1fr);
  align-items: baseline;
  gap: 8px;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
}
.conn-item:hover { background: var(--cream-100); border-color: var(--kb-line); }
.conn-item:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 0; }
.conn-arrow { font-family: var(--kb-font-mono); color: var(--gray-600); }
.conn-rel { font: 500 12px var(--kb-font-mono); color: var(--gray-600); overflow-wrap: anywhere; }
.conn-name { font-weight: 600; color: var(--kb-text); overflow-wrap: anywhere; }

.properties-list { margin: 0; display: grid; gap: 6px; }
.property-item { display: grid; grid-template-columns: 112px 1fr; gap: 10px; }
.property-key { font-size: 12px; font-weight: 500; color: var(--gray-600); overflow-wrap: anywhere; }
.property-value { margin: 0; color: var(--kb-text-2); overflow-wrap: anywhere; }

.labels-list, .episodes-list { display: flex; flex-wrap: wrap; gap: 6px; }
.label-tag, .episode-tag {
  display: inline-block;
  padding: 2px 8px;
  border: 1px solid var(--kb-line-strong);
  border-radius: 4px;
  background: var(--cream-100);
  font: 400 12px/18px var(--kb-font-mono);
  color: var(--kb-text-2);
  overflow-wrap: anywhere;
}
.episodes-list { flex-direction: column; align-items: flex-start; }
.episodes-list.compact { flex-direction: row; }

.edge-relation-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid var(--ink-950);
  border-radius: 8px;
  background: var(--cream-100);
  font-weight: 600;
  line-height: 1.45;
  color: var(--kb-text);
}
.edge-end {
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  color: var(--kb-text);
  text-decoration: underline;
  text-decoration-color: var(--lime-600);
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
  cursor: pointer;
  text-align: left;
  overflow-wrap: anywhere;
}
.edge-end:hover { text-decoration-color: var(--ink-950); }
.edge-mid { font: 500 12px var(--kb-font-mono); color: var(--gray-600); }

.self-loop-header { justify-content: space-between; }
.self-loop-count { font: 500 12px var(--kb-font-mono); color: var(--gray-600); }
.self-loop-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.self-loop-item { border: 1px solid var(--kb-line-strong); border-radius: 8px; overflow: hidden; }
.self-loop-item-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border: 0;
  background: var(--cream-50);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.self-loop-item-header:hover, .self-loop-item.expanded .self-loop-item-header { background: var(--cream-100); }
.self-loop-index { font: 500 12px var(--kb-font-mono); color: var(--gray-600); }
.self-loop-name { flex: 1; font-size: 13px; font-weight: 500; color: var(--kb-text); }
.self-loop-toggle { width: 20px; text-align: center; font: 600 14px var(--kb-font-mono); color: var(--kb-text-2); }
.self-loop-item-content { padding: 10px; border-top: 1px solid var(--kb-line); }
.self-loop-episodes { margin-top: 8px; display: grid; gap: 6px; }

/* ── Leyenda y zoom ── */
.gp-bottom {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  z-index: 5;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}
.gp-bottom > * { pointer-events: auto; }
.graph-legend {
  min-width: 0;
  max-width: min(400px, calc(100% - 52px));
  padding: 8px 10px;
  background: var(--cream-100);
  border: 1px solid var(--ink-950);
  border-radius: 10px;
}
.legend-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;   /* objetivo táctil mínimo (WCAG 2.5.8) */
  padding: 2px 2px;
  border: 0;
  border-radius: 4px;
  background: none;
  font: 500 12px var(--kb-font-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--kb-text);
  cursor: pointer;
}
.legend-total { color: var(--gray-600); }
.legend-chevron { transition: transform 0.2s ease; transform: rotate(180deg); }
.graph-legend.open .legend-chevron { transform: none; }
.legend-items { list-style: none; margin: 6px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 2px 4px; }
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px 3px 3px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  font: 500 12px var(--kb-font-sans);
  color: var(--kb-text-2);
  cursor: pointer;
}
.legend-item:hover { background: var(--kb-surface); border-color: var(--kb-control-line); }
.legend-item[aria-pressed="true"] { background: var(--kb-surface); border-color: var(--ink-950); }
.legend-item:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 0; }
.legend-label { overflow-wrap: anywhere; text-align: left; }
.legend-num { font: 500 12px var(--kb-font-mono); color: var(--gray-600); }

.gp-zoom {
  flex: none;
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  background: var(--kb-surface);
}
.gp-zoom button {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  background: none;
  color: var(--ink-950);
  cursor: pointer;
}
.gp-zoom button + button { border-top: 1px solid var(--kb-line); }
.gp-zoom button:first-child { border-radius: 10px 10px 0 0; }
.gp-zoom button:last-child { border-radius: 0 0 10px 10px; }
.gp-zoom button:hover { background: var(--lime-500); }

/* ── Lista accesible: oculta hasta que recibe el foco del teclado ── */
.gp-sr-list:not(:focus-within) {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}
.gp-sr-list:focus-within {
  position: absolute;
  top: 60px;
  left: 12px;
  z-index: 9;
  width: min(320px, calc(100% - 24px));
  max-height: calc(100% - 72px);
  overflow: auto;
  padding: 10px;
  background: var(--kb-surface);
  border: 1px solid var(--ink-950);
  border-radius: 12px;
  box-shadow: 4px 4px 0 var(--lime-500);
}
.gp-sr-title { margin: 2px 4px 8px; font: 500 12px var(--kb-font-mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--gray-600); }
.gp-sr-list ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.gp-sr-list button {
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: none;
  text-align: left;
  font: 500 13px var(--kb-font-sans);
  color: var(--kb-text);
  cursor: pointer;
}
.gp-sr-list button:hover { background: var(--cream-100); }
.gp-sr-list button:focus-visible { outline: 2px solid var(--kb-accent-text); outline-offset: 0; }
.gp-sr-more { margin: 8px 4px 2px; font-size: 12px; color: var(--gray-600); }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

/* ── Vacío y carga ── */
.graph-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 24px;
  text-align: center;
  background:
    radial-gradient(circle at 50% 44%, color-mix(in srgb, var(--lime-500) 7%, transparent) 0, transparent 40%),
    radial-gradient(circle at 50% 46%, color-mix(in srgb, var(--ink-800) 80%, transparent) 0, transparent 70%),
    var(--ink-950);
}
.state-art { position: relative; width: 240px; height: 150px; display: grid; place-items: center; margin-bottom: 10px; }
.state-art :deep(.bianka-avatar) { position: relative; z-index: 1; }
.state-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--cream-100); }
.state-hint { margin: 0; max-width: 340px; font-size: 13px; line-height: 1.5; color: var(--gray-300); } /* 9,2:1 sobre el centro del escenario (gray-500 daba 4,2) */
.ghost { position: absolute; inset: 0; width: 100%; height: 100%; }
.ghost path { fill: none; stroke: color-mix(in srgb, var(--gray-600) 55%, transparent); stroke-width: 1.2; stroke-dasharray: 3 5; }
.ghost circle { fill: color-mix(in srgb, var(--gray-600) 70%, transparent); }
.ghost .ghost-hub { fill: var(--lime-800); animation: ghost-breathe 2.4s ease-in-out infinite; }
@keyframes ghost-breathe { 50% { fill: var(--lime-600); } }
.orbit { position: absolute; left: 50%; top: 50%; width: 150px; height: 150px; margin: -75px 0 0 -75px; border-radius: 50%; border: 1px dashed color-mix(in srgb, var(--gray-600) 70%, transparent); animation: spin 3.2s linear infinite; }
.orbit-b { width: 104px; height: 104px; margin: -52px 0 0 -52px; animation-duration: 2.1s; animation-direction: reverse; }
.orbit i { position: absolute; top: -4px; left: 50%; width: 8px; height: 8px; margin-left: -4px; border-radius: 50%; background: var(--lime-500); box-shadow: 0 0 12px var(--lime-500); }
.orbit-b i { width: 6px; height: 6px; margin-left: -3px; top: -3px; background: var(--cream-100); box-shadow: none; }

/* ── Paneles estrechos (móvil, o el panel en «Dividido» en pantallas pequeñas) ── */
@container (max-width: 560px) {
  .gp-head { padding: 10px 12px; }
  .btn-text { display: none; }
  .tool-btn { width: 34px; padding: 0; }
  .edge-labels-toggle { padding: 0 8px; }
  .toggle-label {
    position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
  }
  .gp-search { flex: 1 1 auto; }
  .detail-panel {
    top: auto;
    left: 8px;
    right: 8px;
    bottom: 8px;
    width: auto;
    max-width: none;
    max-height: 64%;
    box-shadow: 0 -4px 0 var(--lime-500);
  }
  .graph-legend { max-width: calc(100% - 52px); }
}

@media (prefers-reduced-motion: reduce) {
  .live-dot, .icon-refresh.spinning, .orbit, .ghost .ghost-hub { animation: none; }
  .slider, .slider::before, .legend-chevron, .tool-btn { transition: none; }
}
</style>
