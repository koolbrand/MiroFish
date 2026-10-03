// Ejecuta el script real de la vista con APIs falsas y eventos de ciclo de vida
// controlados: no se necesita DOM, un proveedor LLM ni una base de datos.
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
const script = readFileSync(new URL('../src/components/Step2EnvSetup.vue', import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(overrides = {}) {
  let mounted, unmounted
  const calls = { prepare: 0, intervals: 0 }
  const ok = data => Promise.resolve({ success: true, data })
  const bindings = {
    ref, computed, watch: () => {}, nextTick: fn => Promise.resolve().then(fn),
    onMounted: fn => { mounted = fn }, onUnmounted: fn => { unmounted = fn },
    defineProps: () => ({ simulationId: 'sim_test', projectData: { project_id: 'proj_test' }, systemLogs: [] }), defineEmits: () => () => {},
    useI18n: () => ({ t: key => key, te: () => false }), useTechDetails: () => ({ showTech: ref(false), toggleTech: () => {} }),
    usePipeline: () => ({ isRunning: ref(false), state: ref(null) }),
    rememberedRounds: () => 40, MANUAL_MAX_ROUNDS: 72, SERVER_MAX_ROUNDS: 100, roundsMinutes: n => n,
    entityLabel: n => n, reasoningSections: () => [],
    prepareSimulation: () => { calls.prepare++; return ok({ task_id: 'task_test' }) },
    getRunStatus: () => ok({ runner_status: 'idle' }), getPoblacionEstado: () => ok({ disponible: false }),
    getPrepareStatus: () => ok({}), getSimulation: () => ok({ status: 'ready' }),
    getSimulationProfilesRealtime: () => ok({ profiles: [] }),
    getSimulationConfigRealtime: () => ok({ config_generated: true, config: { generation_version: 2 } }),
    getSimulationConfig: () => ok({}), getPoblacionSimulacion: () => ok(null), getAlcanceSimulacion: () => ok(null),
    document: { addEventListener() {}, removeEventListener() {} },
    setInterval: () => { calls.intervals++; return calls.intervals }, clearInterval: () => {},
    ...overrides
  }
  new Function(...Object.keys(bindings), script)(...Object.values(bindings))
  return { mount: () => mounted(), unmount: () => unmounted(), calls }
}
test('cerrar mientras carga datos poblacionales no inicia preparación', async () => {
  const request = deferred()
  const v = view({ getPoblacionEstado: () => request.promise })
  const mount = v.mount()
  await Promise.resolve(); await Promise.resolve()
  v.unmount()
  request.resolve({ success: true, data: { disponible: false } })
  await mount
  assert.equal(v.calls.prepare, 0)
  assert.equal(v.calls.intervals, 0)
})
test('una preparación que responde tarde no resucita los sondeos', async () => {
  const request = deferred()
  const v = view({ prepareSimulation: () => { v.calls.prepare++; return request.promise } })
  await v.mount()
  assert.equal(v.calls.prepare, 1)
  v.unmount()
  request.resolve({ success: true, data: { task_id: 'task_test' } })
  await Promise.resolve(); await Promise.resolve()
  assert.equal(v.calls.intervals, 0)
})
test('abrir una simulación ejecutada solo lee los datos preparados', async () => {
  const v = view({ getRunStatus: () => Promise.resolve({ success: true, data: { runner_status: 'completed', total_rounds: 15 } }) })
  await v.mount()
  assert.equal(v.calls.prepare, 0)
  assert.equal(v.calls.intervals, 0)
  v.unmount()
})
test('fallo al comprobar el estado no dispara preparación', async () => {
  const v = view({ getRunStatus: () => Promise.reject(new Error('network unavailable')) })
  await v.mount()
  assert.equal(v.calls.prepare, 0)
  assert.equal(v.calls.intervals, 0)
  v.unmount()
})
