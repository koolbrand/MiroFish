import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, computed } from 'vue'
import { evidenceFacts } from '../src/lib/evidenceFacts.js'
import { simulationCoverage } from '../src/lib/simulationCoverage.js'

test('metadatos ausentes se conservan como desconocidos; cero sigue siendo cero', () => {
  const facts = evidenceFacts({ version: 1, agents: { total: 146, anchored: null, active: 0 }, actions: { total: 0, by_platform: { twitter: 0, reddit: null } }, source: { available: false, truncated: false, characters: 0 } })
  assert.equal(facts.agents, 146)
  assert.equal(facts.anchored, null)
  assert.equal(facts.active, 0)
  assert.equal(facts.events, 0)
  assert.deepEqual(facts.platforms, [{ name: 'twitter', count: 0 }, { name: 'reddit', count: null }])
  assert.equal(facts.sourceAvailable, false)
  assert.equal(facts.truncated, false)
  assert.equal(facts.sourceCharacters, 0)
  assert.equal(facts.executedRounds, null)
})

test('tipos inválidos no se convierten en métricas ni en afirmaciones de fuente', () => {
  assert.equal(evidenceFacts(null), null)
  const facts = evidenceFacts({ version: 1, agents: { anchored: false, active: '59' }, source: { available: 'true', truncated: 0 }, execution: { executed_hours: NaN } })
  assert.equal(facts.anchored, null)
  assert.equal(facts.active, null)
  assert.equal(facts.sourceAvailable, null)
  assert.equal(facts.truncated, null)
  assert.equal(facts.executedHours, null)
})

const script = readFileSync(new URL('../src/components/SimulationEvidenceNotice.vue', import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
async function notice(props) {
  const calls = { config: 0, run: 0 }
  let pending
  const bindings = { ref, computed, evidenceFacts, simulationCoverage,
    defineProps: () => props, useI18n: () => ({ locale: ref('es'), t: key => key }),
    watch: (getter, fn) => { pending = fn(getter()) }, onUnmounted: () => {},
    getSimulationConfig: async () => { calls.config++; return { success: true, data: { generation_version: 1 } } },
    getRunStatus: async () => { calls.run++; return { success: true, data: { current_round: 100 } } }
  }
  const result = new Function(...Object.keys(bindings), script + '\nreturn { coverage, facts, legacy };')(...Object.values(bindings))
  await pending
  return { ...result, calls }
}
test('un informe con ficha usa su ejecución persistida y no consulta config ni estado vivo', async () => {
  const v = await notice({ simulationId: 'sim_mock', report: true, reportReady: true, evidence: { version: 1, execution: { configured_rounds: 72, executed_rounds: 15, configured_hours: 72, executed_hours: 15, duration_limited: true } }, runStatus: { current_round: 100 }, config: { generation_version: 1 } })
  assert.deepEqual(v.calls, { config: 0, run: 0 })
  assert.equal(v.coverage.value.effectiveRounds, 15)
  assert.equal(v.coverage.value.effectiveHours, 15)
  assert.equal(v.legacy.value, false)
})
test('mientras carga la ficha del informe no se hacen lecturas redundantes; una ficha parcial no se rellena con datos vivos', async () => {
  const pending = await notice({ simulationId: 'sim_mock', report: true, reportReady: false })
  assert.deepEqual(pending.calls, { config: 0, run: 0 })
  const partial = await notice({ simulationId: 'sim_mock', report: true, reportReady: true, evidence: { version: 1, execution: { configured_rounds: 72, executed_rounds: null } }, config: { time_config: { total_simulation_hours: 72, minutes_per_round: 60 } }, runStatus: { current_round: 100 } })
  assert.equal(partial.facts.value.executedRounds, null)
  assert.equal(partial.coverage.value, null)
  assert.deepEqual(partial.calls, { config: 0, run: 0 })
})

test('preparación fallida o en curso no recupera calendario viejo ni muestra su duración', async () => {
  for (const config of [undefined, { generation_version: 1, time_config: { total_simulation_hours: 72, minutes_per_round: 60 } }]) {
    const v = await notice({ simulationId: 'sim_mock', preview: true, preparationReady: false, config, rounds: 20 })
    assert.deepEqual(v.calls, { config: 0, run: 0 })
    assert.equal(v.coverage.value, null)
    assert.equal(v.legacy.value, false)
  }
})

test('configuración en vuelo se descarta si la preparación deja de ser válida', async () => {
  let resolveConfig, rerun, initial
  const request = new Promise(resolve => { resolveConfig = resolve })
  const props = { simulationId: 'sim_test', preview: true, preparationReady: true, rounds: 20 }
  const bindings = {
    ref, computed, evidenceFacts, simulationCoverage, defineProps: () => props,
    useI18n: () => ({ locale: ref('es'), t: key => key }), onUnmounted: () => {},
    watch: (getter, fn) => { rerun = () => fn(getter()); initial = rerun() },
    getSimulationConfig: () => request, getRunStatus: () => { throw new Error('preview no consulta run') }
  }
  const v = new Function(...Object.keys(bindings), script + '\nreturn { loadedConfig, coverage };')(...Object.values(bindings))
  props.preparationReady = false
  await rerun()
  resolveConfig({ success: true, data: { time_config: { total_simulation_hours: 72, minutes_per_round: 60 } } })
  await initial
  assert.equal(v.loadedConfig.value, null)
  assert.equal(v.coverage.value, null)
})
