import { ref, computed, watch, onUnmounted } from 'vue'
import { getPipeline, cancelPipeline, resumePipeline } from '../api/pipeline'

/**
 * Estado del modo automático de un proyecto, compartido por todo lo que hay en pantalla
 * (indicador de etapas, aviso y la etapa abierta): una sola consulta por proyecto,
 * que se repite cada pocos segundos solo mientras el automático está en marcha.
 */

const POLL_MS = 4000
const stores = new Map()

function storeFor(projectId) {
  if (!stores.has(projectId)) {
    stores.set(projectId, { state: ref(null), subscribers: 0, timer: null, loading: null })
  }
  return stores.get(projectId)
}

async function load(projectId) {
  const store = storeFor(projectId)
  if (store.loading) return store.loading
  store.loading = (async () => {
    try {
      const res = await getPipeline(projectId)
      store.state.value = res?.data || { mode: 'manual' }
    } catch (e) {
      // sin automático (404 de un backend antiguo, proyecto sin estado) o sin red: se sigue paso a paso
      if (!store.state.value) store.state.value = { mode: 'manual' }
    } finally {
      store.loading = null
      schedule(projectId)
    }
  })()
  return store.loading
}

function schedule(projectId) {
  const store = storeFor(projectId)
  clearTimeout(store.timer)
  store.timer = null
  const s = store.state.value
  if (store.subscribers > 0 && s?.mode === 'auto' && s.status === 'running') {
    store.timer = setTimeout(() => load(projectId), POLL_MS)
  }
}

export function usePipeline(projectIdSource) {
  const projectId = computed(() => (typeof projectIdSource === 'function' ? projectIdSource() : projectIdSource?.value) || null)
  const state = ref(null)
  let current = null
  let stopMirror = null

  const attach = (pid) => {
    if (current) {
      const prev = storeFor(current)
      prev.subscribers--
      schedule(current)
      stopMirror?.()
    }
    current = pid
    state.value = null
    if (!pid) return
    const store = storeFor(pid)
    store.subscribers++
    stopMirror = watch(store.state, v => { state.value = v }, { immediate: true })
    load(pid)
  }

  watch(projectId, attach, { immediate: true })
  onUnmounted(() => attach(null))

  const isAuto = computed(() => state.value?.mode === 'auto')
  const isRunning = computed(() => isAuto.value && state.value?.status === 'running')

  const setState = (data) => {
    if (!current || !data) return
    storeFor(current).state.value = data
    schedule(current)
  }

  return {
    state,
    isAuto,
    isRunning,
    refresh: () => (current ? load(current) : Promise.resolve()),
    cancel: async () => { if (current) setState((await cancelPipeline(current))?.data) },
    resume: async () => { if (current) setState((await resumePipeline(current))?.data) },
  }
}
