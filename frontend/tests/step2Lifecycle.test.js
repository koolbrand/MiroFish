// Ejecuta el script real de la vista con APIs falsas y eventos de ciclo de vida
// controlados: no se necesita DOM, un proveedor LLM ni una base de datos.
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { profileDemographic, knownProfileText, legacyProfilePersona } from '../src/lib/profilePresentation.js'
const script = readFileSync(new URL('../src/components/Step2EnvSetup.vue', import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(overrides = {}) {
  let mounted, unmounted
  const calls = { prepare: 0, intervals: 0 }
  const ok = data => Promise.resolve({ success: true, data })
  const bindings = {
    ref, computed, profileDemographic, knownProfileText, legacyProfilePersona, watch: () => {}, nextTick: fn => Promise.resolve().then(fn),
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
  const state = new Function(...Object.keys(bindings), script + '\nreturn { phase, profiles, simulationConfig, prepareError, taskId, selectedProfile, regenerarPublico, fetchConfigRealtime, fetchProfilesRealtime, pollPrepareStatus, alreadyRun, runnerStatus, audienceSizeMode, audienceSizeValue, audienceSizeUsed, audienceSizeValid, audienceSizeChanged, demographics };')(...Object.values(bindings))
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
    getSimulation: () => Promise.resolve({ success: true, data: { status: 'failed', error: 'fallo anterior', audience_size: 70 } }),
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
  assert.equal(retryParams.audience_size, 70)
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

test('automático omite tamaño explícito y permite borrar una elección anterior', async () => {
  const requests = []
  const v = view({
    getSimulation: () => Promise.resolve({ success: true, data: { status: 'ready' } }),
    prepareSimulation: data => { requests.push(data); return Promise.resolve({ success: true, data: { task_id: 'task_test' } }) }
  })
  await v.mount()
  assert.equal(requests[0].audience_size, null)
  v.state.phase.value = 4
  v.state.audienceSizeMode.value = 'explicit'
  v.state.audienceSizeValue.value = 70
  assert.equal(v.state.audienceSizeChanged.value, true)
  await v.state.regenerarPublico()
  assert.equal(requests[1].audience_size, 70)
  v.state.phase.value = 4
  v.state.audienceSizeMode.value = 'auto'
  assert.equal(v.state.audienceSizeChanged.value, true)
  await v.state.regenerarPublico()
  assert.equal(requests[2].audience_size, null)
  v.unmount()
})
test('tamaño explícito se recupera y envía como entero incluso con preparación activa', async () => {
  for (const n of [5, 70, 150]) {
    let request
    const v = view({
      getSimulation: () => Promise.resolve({ success: true, data: { status: 'preparing', audience_size: n } }),
      prepareSimulation: data => { request = data; return Promise.resolve({ success: true, data: { task_id: 'task_test' } }) }
    })
    await v.mount()
    assert.equal(v.state.audienceSizeMode.value, 'explicit')
    assert.equal(v.state.audienceSizeValue.value, n)
    assert.equal(request.audience_size, n)
    assert.equal(request.force_regenerate, undefined)
    v.unmount()
  }
})
test('tamaño guardado se consulta en un run ejecutado sin preparar y queda bloqueado', async () => {
  const v = view({
    getRunStatus: () => Promise.resolve({ success: true, data: { runner_status: 'completed' } }),
    getSimulation: () => Promise.resolve({ success: true, data: { status: 'completed', audience_size: 70 } })
  })
  await v.mount()
  assert.equal(v.state.audienceSizeValue.value, 70)
  assert.equal(v.calls.prepare, 0)
  await v.state.regenerarPublico()
  assert.equal(v.calls.prepare, 0)
  v.unmount()
})
test('cantidad inválida no borra configuración ni dispara una preparación', async () => {
  for (const n of ['', '70', true, 4, 151, 5.5, NaN]) {
    const v = view()
    v.state.runnerStatus.value = 'idle'
    v.state.phase.value = 4
    v.state.simulationConfig.value = { valid: true }
    v.state.audienceSizeMode.value = 'explicit'
    v.state.audienceSizeValue.value = n
    assert.equal(v.state.audienceSizeValid.value, false)
    await v.state.regenerarPublico()
    assert.equal(v.calls.prepare, 0)
    assert.equal(v.state.simulationConfig.value.valid, true)
    v.unmount()
  }
})
test('resumen demográfico excluye defaults de actores y perfiles legados', () => {
  const v = view()
  v.state.profiles.value = [
    { profile_schema_version: 1, identity_kind: 'institution', gender: 'male', profession: 'unknown' },
    { profile_schema_version: 1, identity_kind: 'named_actor', gender: 'male' },
    { gender: 'male', profession: 'desconocido' },
    { profile_schema_version: 1, identity_kind: 'survey_respondent', gender: 'female', profession: 'Ingeniera' }
  ]
  assert.deepEqual(v.state.demographics.value.genderBreakdown.map(g => [g.key, g.count]), [['female', 1]])
  assert.deepEqual(v.state.demographics.value.topProfessions, ['Ingeniera'])
  v.unmount()
})
