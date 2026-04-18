<template>
  <div class="projects-container">
    <!-- Navbar -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand"><BrandLogo /></router-link>
      <div class="nav-links">
        <LanguageSwitcher />
        <router-link to="/" class="nav-link">{{ $t('projects.backToHome') }}</router-link>
      </div>
    </nav>

    <div class="main-content">
      <!-- Header -->
      <header class="page-header">
        <div class="header-left">
          <span class="page-tag">ADMIN</span>
          <h1 class="page-title">{{ $t('projects.title') }}</h1>
          <p class="page-subtitle">{{ $t('projects.subtitle') }}</p>
        </div>
        <div class="header-right">
          <button class="icon-btn" @click="refresh" :disabled="loading" :title="$t('projects.refresh')">
            <span :class="{ spinning: loading }">⟳</span>
          </button>
        </div>
      </header>

      <!-- Toolbar -->
      <div class="toolbar">
        <div class="filters">
          <button
            v-for="f in filters"
            :key="f.value"
            class="filter-btn"
            :class="{ active: statusFilter === f.value }"
            @click="statusFilter = f.value"
          >
            {{ f.label }}
            <span class="count">{{ counts[f.value] || 0 }}</span>
          </button>
        </div>
        <div class="actions">
          <label class="select-all">
            <input
              type="checkbox"
              :checked="allSelected"
              :indeterminate.prop="someSelected && !allSelected"
              @change="toggleAll"
              :disabled="filteredProjects.length === 0"
            />
            <span>{{ $t('projects.selectAll') }}</span>
          </label>
          <button
            class="delete-btn"
            :disabled="selectedIds.size === 0 || deleting"
            @click="confirmBulkDelete"
          >
            {{ $t('projects.deleteSelected', { count: selectedIds.size }) }}
          </button>
        </div>
      </div>

      <!-- Loading / empty / error -->
      <div v-if="loading && projects.length === 0" class="state-box">
        <span class="spinner"></span>
        <span>{{ $t('projects.loading') }}</span>
      </div>
      <div v-else-if="errorMsg" class="state-box error">
        <span>⚠ {{ errorMsg }}</span>
      </div>
      <div v-else-if="filteredProjects.length === 0" class="state-box">
        <span>{{ $t('projects.empty') }}</span>
      </div>

      <!-- Table -->
      <div v-else class="projects-table">
        <div class="table-head">
          <div class="col col-check"></div>
          <div class="col col-id">{{ $t('projects.colId') }}</div>
          <div class="col col-name">{{ $t('projects.colName') }}</div>
          <div class="col col-status">{{ $t('projects.colStatus') }}</div>
          <div class="col col-date">{{ $t('projects.colCreated') }}</div>
          <div class="col col-info">{{ $t('projects.colInfo') }}</div>
          <div class="col col-actions">{{ $t('projects.colActions') }}</div>
        </div>

        <div
          v-for="p in filteredProjects"
          :key="p.project_id"
          class="table-row"
          :class="{ selected: selectedIds.has(p.project_id) }"
        >
          <div class="col col-check">
            <input
              type="checkbox"
              :checked="selectedIds.has(p.project_id)"
              @change="toggleOne(p.project_id)"
            />
          </div>
          <div class="col col-id">
            <span class="mono">{{ shortId(p.project_id) }}</span>
          </div>
          <div class="col col-name" :title="p.name">
            <span>{{ p.name || $t('projects.unnamed') }}</span>
            <span v-if="p.files && p.files.length" class="sub mono">{{ p.files.length }} {{ $t('projects.files') }}</span>
          </div>
          <div class="col col-status">
            <span class="status-badge" :class="statusClass(p.status)">
              {{ statusLabel(p.status) }}
            </span>
          </div>
          <div class="col col-date mono">{{ formatDate(p.created_at) }}</div>
          <div class="col col-info">
            <span v-if="p.error" class="error-text mono" :title="p.error">
              {{ truncate(p.error, 60) }}
            </span>
            <span v-else-if="p.graph_id" class="mono">
              {{ shortId(p.graph_id) }}
            </span>
            <span v-else class="sub mono">—</span>
          </div>
          <div class="col col-actions">
            <button
              v-if="p.status === 'graph_completed' && p.graph_id"
              class="row-btn"
              @click="openProject(p.project_id)"
            >
              {{ $t('projects.open') }}
            </button>
            <button class="row-btn danger" @click="confirmSingleDelete(p)">
              {{ $t('projects.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="confirmState" class="modal-overlay" @click.self="cancelConfirm">
          <div class="modal-content">
            <div class="modal-header">
              <h2>{{ $t('projects.confirmTitle') }}</h2>
              <button class="modal-close" @click="cancelConfirm">×</button>
            </div>
            <div class="modal-body">
              <p>{{ confirmState.message }}</p>
              <ul v-if="confirmState.ids.length <= 10" class="id-list">
                <li v-for="id in confirmState.ids" :key="id" class="mono">{{ shortId(id) }}</li>
              </ul>
              <p class="warning mono">{{ $t('projects.confirmWarning') }}</p>
            </div>
            <div class="modal-actions">
              <button class="modal-btn" @click="cancelConfirm">
                {{ $t('projects.cancel') }}
              </button>
              <button class="modal-btn danger" @click="runConfirm" :disabled="deleting">
                {{ deleting ? $t('projects.deleting') : $t('projects.confirm') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listProjects, deleteProject } from '../api/graph'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import BrandLogo from '../components/BrandLogo.vue'

const router = useRouter()
const { t } = useI18n()

const projects = ref([])
const loading = ref(false)
const errorMsg = ref('')
const deleting = ref(false)
const statusFilter = ref('all')
const selectedIds = ref(new Set())
const confirmState = ref(null) // { ids: [], message: '' }

const filters = computed(() => [
  { value: 'all', label: t('projects.filterAll') },
  { value: 'graph_completed', label: t('projects.filterCompleted') },
  { value: 'graph_building', label: t('projects.filterBuilding') },
  { value: 'ontology_generated', label: t('projects.filterOntology') },
  { value: 'created', label: t('projects.filterCreated') },
  { value: 'failed', label: t('projects.filterFailed') }
])

const counts = computed(() => {
  const c = { all: projects.value.length }
  for (const p of projects.value) {
    c[p.status] = (c[p.status] || 0) + 1
  }
  return c
})

const filteredProjects = computed(() => {
  if (statusFilter.value === 'all') return projects.value
  return projects.value.filter(p => p.status === statusFilter.value)
})

const allSelected = computed(() =>
  filteredProjects.value.length > 0 &&
  filteredProjects.value.every(p => selectedIds.value.has(p.project_id))
)

const someSelected = computed(() =>
  filteredProjects.value.some(p => selectedIds.value.has(p.project_id))
)

const refresh = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await listProjects(100)
    if (res.success) {
      projects.value = res.data || []
      // drop selections that no longer exist
      const existing = new Set(projects.value.map(p => p.project_id))
      const next = new Set()
      for (const id of selectedIds.value) if (existing.has(id)) next.add(id)
      selectedIds.value = next
    } else {
      errorMsg.value = res.error || t('common.unknownError')
    }
  } catch (e) {
    errorMsg.value = e.message || t('common.unknownError')
  } finally {
    loading.value = false
  }
}

const toggleOne = (id) => {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

const toggleAll = () => {
  const next = new Set(selectedIds.value)
  if (allSelected.value) {
    for (const p of filteredProjects.value) next.delete(p.project_id)
  } else {
    for (const p of filteredProjects.value) next.add(p.project_id)
  }
  selectedIds.value = next
}

const confirmSingleDelete = (p) => {
  confirmState.value = {
    ids: [p.project_id],
    message: t('projects.confirmSingleMsg', { id: shortId(p.project_id) })
  }
}

const confirmBulkDelete = () => {
  if (selectedIds.value.size === 0) return
  confirmState.value = {
    ids: Array.from(selectedIds.value),
    message: t('projects.confirmBulkMsg', { count: selectedIds.value.size })
  }
}

const cancelConfirm = () => {
  if (deleting.value) return
  confirmState.value = null
}

const runConfirm = async () => {
  if (!confirmState.value || deleting.value) return
  deleting.value = true
  const ids = confirmState.value.ids
  let failed = []
  for (const id of ids) {
    try {
      const res = await deleteProject(id)
      if (!res.success) failed.push(id)
    } catch (e) {
      failed.push(id)
    }
  }
  deleting.value = false
  confirmState.value = null
  if (failed.length > 0) {
    errorMsg.value = t('projects.deleteFailed', { count: failed.length })
  }
  await refresh()
}

const openProject = (id) => {
  router.push({ name: 'Process', params: { projectId: id } })
}

// --- helpers ---
const shortId = (id) => {
  if (!id) return '—'
  const parts = id.split('_')
  return parts.length > 1 ? parts[parts.length - 1].slice(0, 8) : id.slice(0, 12)
}

const truncate = (txt, max) => {
  if (!txt) return ''
  return txt.length > max ? txt.slice(0, max - 1) + '…' : txt
}

const formatDate = (iso) => {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    const p = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  } catch {
    return iso.slice(0, 16)
  }
}

const statusClass = (s) => ({
  graph_completed: 'ok',
  graph_building: 'busy',
  ontology_generated: 'pending',
  created: 'pending',
  failed: 'fail'
}[s] || 'neutral')

const statusLabel = (s) => {
  const key = 'projects.status_' + s
  return t(key)
}

onMounted(refresh)
</script>

<style scoped>
.projects-container {
  min-height: 100vh;
  background: #fff;
  color: #111827;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.mono { font-family: 'JetBrains Mono', 'SF Mono', monospace; }

/* Navbar */
.navbar {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}
.nav-brand {
  font-size: 24px;
  color: #fff;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  transition: opacity 0.15s ease;
}
.nav-brand:hover {
  opacity: 0.7;
}
.nav-links { display: flex; align-items: center; gap: 16px; }
.nav-link {
  color: #fff;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}
.nav-link:hover { opacity: 0.8; }

/* Layout */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 40px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e5e7eb;
}
.page-tag {
  display: inline-block;
  background: #FF4500;
  color: #fff;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 3px 8px;
  margin-bottom: 12px;
}
.page-title {
  font-size: 2.2rem;
  font-weight: 500;
  margin: 0 0 4px 0;
  letter-spacing: -0.5px;
}
.page-subtitle { color: #6b7280; margin: 0; font-size: 0.95rem; }

.icon-btn {
  background: transparent;
  border: 1px solid #e5e7eb;
  width: 40px;
  height: 40px;
  font-size: 1.3rem;
  cursor: pointer;
  color: #6b7280;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.icon-btn:hover:not(:disabled) { border-color: #000; color: #000; }
.icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.spinning { animation: spin 0.9s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Toolbar */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
}
.filters { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-btn {
  background: transparent;
  border: 1px solid #e5e7eb;
  padding: 6px 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: #6b7280;
  cursor: pointer;
  letter-spacing: 0.3px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.filter-btn:hover { border-color: #9ca3af; color: #111827; }
.filter-btn.active {
  background: #000;
  color: #fff;
  border-color: #000;
}
.filter-btn .count {
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.15);
  color: inherit;
  padding: 1px 6px;
  border-radius: 2px;
}
.filter-btn:not(.active) .count {
  background: #f3f4f6;
  color: #6b7280;
}

.actions { display: flex; align-items: center; gap: 16px; }
.select-all {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  color: #6b7280;
  cursor: pointer;
}
.delete-btn {
  background: #fff;
  border: 1px solid #dc2626;
  color: #dc2626;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.5px;
}
.delete-btn:hover:not(:disabled) { background: #dc2626; color: #fff; }
.delete-btn:disabled { border-color: #e5e7eb; color: #9ca3af; cursor: not-allowed; }

/* State */
.state-box {
  border: 1px dashed #e5e7eb;
  padding: 60px 24px;
  text-align: center;
  color: #6b7280;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
}
.state-box.error { border-color: #fca5a5; color: #dc2626; }
.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e7eb;
  border-top-color: #6b7280;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Table */
.projects-table {
  border: 1px solid #e5e7eb;
}
.table-head,
.table-row {
  display: grid;
  grid-template-columns: 40px 100px 1.5fr 130px 140px 1.5fr 160px;
  gap: 12px;
  padding: 12px 16px;
  align-items: center;
}
.table-head {
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: #6b7280;
  letter-spacing: 1px;
  text-transform: uppercase;
}
.table-row {
  border-bottom: 1px solid #f3f4f6;
  font-size: 0.9rem;
  transition: background 0.15s;
}
.table-row:last-child { border-bottom: none; }
.table-row:hover { background: #fafafa; }
.table-row.selected { background: #eff6ff; }

.col { min-width: 0; }
.col-name { display: flex; flex-direction: column; gap: 2px; overflow: hidden; }
.col-name > span:first-child {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.col-name .sub { font-size: 0.7rem; color: #9ca3af; }
.col-date { font-size: 0.78rem; color: #6b7280; }
.col-info { overflow: hidden; }
.col-info .sub { color: #9ca3af; }
.error-text {
  color: #dc2626;
  font-size: 0.72rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  max-width: 100%;
}

.col-actions { display: flex; gap: 6px; justify-content: flex-end; }

.status-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 2px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.3px;
}
.status-badge.ok { background: rgba(16, 185, 129, 0.1); color: #059669; }
.status-badge.busy { background: rgba(245, 158, 11, 0.1); color: #d97706; }
.status-badge.pending { background: #f3f4f6; color: #6b7280; }
.status-badge.fail { background: rgba(220, 38, 38, 0.1); color: #dc2626; }
.status-badge.neutral { background: #f3f4f6; color: #6b7280; }

.row-btn {
  background: #fff;
  border: 1px solid #e5e7eb;
  padding: 4px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.72rem;
  cursor: pointer;
  color: #374151;
}
.row-btn:hover { border-color: #000; color: #000; }
.row-btn.danger { border-color: #fecaca; color: #dc2626; }
.row-btn.danger:hover { background: #dc2626; color: #fff; border-color: #dc2626; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.modal-content {
  background: #fff;
  width: 480px;
  max-width: 90vw;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #f3f4f6;
}
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.modal-close {
  background: transparent;
  border: none;
  font-size: 1.6rem;
  color: #9ca3af;
  cursor: pointer;
  line-height: 1;
}
.modal-body { padding: 20px 24px; }
.modal-body p { margin: 0 0 12px 0; color: #374151; }
.modal-body .warning {
  margin-top: 12px;
  padding: 10px 12px;
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
  font-size: 0.75rem;
  border-left: 3px solid #dc2626;
}
.id-list {
  max-height: 160px;
  overflow-y: auto;
  margin: 8px 0;
  padding: 8px 16px;
  background: #f9fafb;
  border: 1px solid #f3f4f6;
  list-style: none;
  font-size: 0.8rem;
}
.id-list li { padding: 2px 0; color: #6b7280; }
.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid #f3f4f6;
}
.modal-btn {
  background: #fff;
  border: 1px solid #e5e7eb;
  padding: 8px 20px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  cursor: pointer;
  color: #374151;
}
.modal-btn:hover { border-color: #000; color: #000; }
.modal-btn.danger { border-color: #dc2626; color: #dc2626; }
.modal-btn.danger:hover:not(:disabled) { background: #dc2626; color: #fff; }
.modal-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-active .modal-content { transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.modal-enter-from .modal-content { transform: scale(0.95) translateY(6px); }

@media (max-width: 900px) {
  .table-head, .table-row {
    grid-template-columns: 32px 80px 1fr 110px 110px 110px;
  }
  .col-info { display: none; }
}
</style>
