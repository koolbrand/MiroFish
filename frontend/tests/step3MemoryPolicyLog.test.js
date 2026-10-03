import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
const file = readFileSync(new URL('../src/components/Step3Simulation.vue', import.meta.url), 'utf8')
const method = file.match(/const doStartSimulation = async [\s\S]*?\n}\n/)[0]
function start(response) {
  const logs = []
  const bindings = {
    unmounted: false, props: { simulationId: 'sim_mock' }, isStarting: ref(false), startError: ref(null), phase: ref(0), runStatus: ref(null),
    addLog: line => logs.push(line), t: key => key, emit: () => {}, resetAllState: () => {},
    startStatusPolling: () => {}, startDetailPolling: () => {}, startSimulation: () => response
  }
  const run = new Function(...Object.keys(bindings), method + '\nreturn doStartSimulation;')(...Object.values(bindings))
  return { run, logs }
}
test('log espera confirmación de política y describe material inmutable en perfiles nuevos', async () => {
  let resolve
  const deferred = new Promise(r => { resolve = r })
  const v = start(deferred)
  const running = v.run()
  assert.equal(v.logs.includes('log.graphMemoryUpdateEnabled'), false)
  assert.equal(v.logs.includes('log.originalMaterialPreserved'), false)
  resolve({ success: true, data: { graph_memory_update_enabled: false, memory_policy: { source_graph: 'immutable' } } })
  await running
  assert.equal(v.logs.includes('log.originalMaterialPreserved'), true)
  assert.equal(v.logs.includes('log.graphMemoryUpdateEnabled'), false)
})
test('legado solo anuncia actualización cuando servidor confirma true', async () => {
  const v = start(Promise.resolve({ success: true, data: { graph_memory_update_enabled: true } }))
  await v.run()
  assert.equal(v.logs.includes('log.graphMemoryUpdateEnabled'), true)
  assert.equal(v.logs.includes('log.originalMaterialPreserved'), false)
})
test('respuesta fallida o sin política no anuncia un modo que no se confirmó', async () => {
  for (const response of [{ success: false, error: 'fallo' }, { success: true, data: {} }]) {
    const v = start(Promise.resolve(response))
    await v.run()
    assert.equal(v.logs.includes('log.graphMemoryUpdateEnabled'), false)
    assert.equal(v.logs.includes('log.originalMaterialPreserved'), false)
  }
})
