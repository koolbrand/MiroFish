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
  const state = new Function(...Object.keys(bindings), script + '\nreturn { phase, profiles, simulationConfig, prepareError, taskId, selectedProfile, regenerarPublico, fetchConfigRealtime, fetchProfilesRealtime, pollPrepareStatus, alreadyRun, runnerStatus };')(...Object.values(bindings))
  return { mount: () => mounted(), unmount: () => unmounted(), calls, state }
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
  await v.state.regenerarPublico()
  assert.equal(v.calls.prepare, 0) // runner desconocido: tampoco force mediante Reintentar
  v.unmount()
})

test('ready → regenerar → failed borra configuración antigua y rechaza respuestas tardías', async () => {
  const lateConfig = deferred()
  let configReads = 0
  const v = view({
    getSimulationConfigRealtime: () => { configReads++; return lateConfig.promise },
    prepareSimulation: () => { v.calls.prepare++; return Promise.reject(new Error('proveedor caído')) }
  })
  v.state.runnerStatus.value = 'idle'
  v.state.phase.value = 4
  v.state.profiles.value = [{ name: 'autor anterior' }]
  v.state.simulationConfig.value = { initial_posts: [{ content: 'semilla antigua' }] }
  v.state.selectedProfile.value = v.state.profiles.value[0]
  const oldRead = v.state.fetchConfigRealtime()
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  assert.equal(configReads, 1)
  await v.state.regenerarPublico()
  assert.equal(v.calls.prepare, 1)
  assert.equal(v.state.simulationConfig.value, null)
  assert.equal(v.state.selectedProfile.value, null)
  assert.equal(v.state.taskId.value, null)
  assert.equal(v.state.phase.value, 1)
  assert.match(v.state.prepareError.value, /proveedor caído/)
  lateConfig.resolve({ success: true, data: { config_generated: true, config: { initial_posts: ['antigua'] } } })
  await oldRead
  assert.equal(v.state.simulationConfig.value, null)
  assert.equal(v.state.phase.value, 1)
  v.unmount()
})
test('reabrir failed con runner idle no prepara automáticamente; Reintentar sí', async () => {
  let retryParams
  const v = view({
    getSimulation: () => Promise.resolve({ success: true, data: { status: 'failed', error: 'fallo anterior' } }),
    getPoblacionEstado: () => Promise.resolve({ success: true, data: { disponible: true, por_defecto: false } }),
    getPoblacionSimulacion: () => Promise.resolve({ success: true, data: { pais: 'ES', pais_decidido_por: 'pedido', sin_datos: false } }),
    getAlcanceSimulacion: () => Promise.resolve({ success: true, data: { nivel: 'nacional', origen: 'pedido' } }),
    prepareSimulation: params => { retryParams = params; v.calls.prepare++; return Promise.resolve({ success: true, data: { task_id: 'retry_task' } }) }
  })
  await v.mount()
  assert.equal(v.calls.prepare, 0)
  assert.equal(v.calls.intervals, 0)
  assert.equal(v.state.prepareError.value, 'fallo anterior')
  assert.equal(v.state.simulationConfig.value, null)
  await v.state.regenerarPublico()
  assert.equal(v.calls.prepare, 1)
  assert.equal(v.state.prepareError.value, '')
  assert.equal(retryParams.poblacion_datos, true)
  assert.equal(retryParams.poblacion_pais, 'ES')
  assert.equal(retryParams.alcance, 'nacional')
  v.unmount()
})
test('reabrir preparación activa conserva el reenganche', async () => {
  const v = view({ getSimulation: () => Promise.resolve({ success: true, data: { status: 'preparing' } }) })
  await v.mount()
  await Promise.resolve(); await Promise.resolve()
  assert.equal(v.calls.prepare, 1) // el servidor devuelve/reutiliza su task_id, no force
  assert.equal(v.calls.intervals, 2)
  v.unmount()
})
test('estado de preparación inaccesible no autoriza un POST', async () => {
  const v = view({ getSimulation: () => Promise.reject(new Error('sin conexión')) })
  await v.mount()
  assert.equal(v.calls.prepare, 0)
  assert.equal(v.calls.intervals, 0)
  assert.equal(v.state.prepareError.value, 'sin conexión')
  v.unmount()
})
test('fallo después de generar perfiles nuevos no muestra semillas de la configuración anterior', async () => {
  let status = 'preparing'
  const v = view({
    getSimulation: () => Promise.resolve({ success: true, data: { status, error: 'configuración rechazada' } }),
    getSimulationProfilesRealtime: () => Promise.resolve({ success: true, data: { profiles: Array.from({ length: 84 }, (_, i) => ({ name: `nuevo_${i}` })) } })
  })
  v.state.runnerStatus.value = 'idle'
  v.state.phase.value = 4
  v.state.simulationConfig.value = { agent_configs: Array.from({ length: 76 }), initial_posts: ['semilla anterior'] }
  await v.state.regenerarPublico()
  await v.state.fetchProfilesRealtime()
  assert.equal(v.state.profiles.value.length, 84)
  assert.equal(v.state.simulationConfig.value, null)
  status = 'failed'
  await v.state.pollPrepareStatus()
  assert.equal(v.state.profiles.value.length, 84)
  assert.equal(v.state.simulationConfig.value, null)
  assert.equal(v.state.phase.value, 1)
  assert.equal(v.state.prepareError.value, 'configuración rechazada')
  v.unmount()
})
