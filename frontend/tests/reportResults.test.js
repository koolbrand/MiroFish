import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resultsSnapshot, createResultsController } from '../src/lib/reportResults.js'
import { resultsFixture } from './reportResults.fixture.js'
const deferred = () => { let resolve, reject; const promise = new Promise((r, j) => { resolve = r; reject = j }); return { promise, resolve, reject } }
function harness(options = {}) {
  const tasks = new Map(), changes = [], problems = []
  let clock = 0, sequence = 0, reads = 0, posts = 0
  const controller = createResultsController({
    read: async (id, signal) => { reads++; return options.read ? options.read(id, signal) : resultsFixture() },
    generate: async (id, signal) => { posts++; return options.generate ? options.generate(id, signal) : { version: 2, status: 'generating' } },
    onSnapshot: value => changes.push(value), onProblem: value => problems.push(value),
    schedule: fn => { tasks.set(++sequence, fn); return sequence }, cancel: id => tasks.delete(id), now: () => clock, windowMs: options.windowMs || 300000
  })
  controller.reset('report_a')
  return { controller, tasks, changes, problems, reads: () => reads, posts: () => posts,
    async tick(ms = 3000) { clock += ms; const next = tasks.entries().next().value; if (next) { tasks.delete(next[0]); await next[1](); await new Promise(r => setImmediate(r)) } },
    latest: () => changes.at(-1)
  }
}
test('legacy, failed y pending jamás generan ni consultan por observar/montar', async () => {
  const v = harness()
  for (const value of [null, { version: 2, status: 'failed' }, { version: 2, status: 'stale' }]) v.controller.observe(value, true)
  v.controller.observe({ version: 2, status: 'generating' }, false)
  await v.controller.start()
  assert.equal(v.posts(), 0)
  assert.equal(v.reads(), 0)
  assert.equal(v.tasks.size, 0)
})
test('POST explícito único ante doble clic; GET sondea hasta ready y luego se detiene', async () => {
  const response = deferred(), v = harness({ generate: () => response.promise })
  v.controller.observe(null, true)
  const start = v.controller.start()
  await v.controller.start()
  assert.equal(v.posts(), 1)
  response.resolve({ version: 2, status: 'generating' })
  await start
  assert.equal(v.tasks.size, 1)
  await v.tick()
  assert.equal(v.reads(), 1)
  assert.equal(v.latest().status, 'ready')
  assert.equal(v.tasks.size, 0)
  await v.controller.start()
  assert.equal(v.posts(), 1)
})
test('generación observada solo programa un GET, sin POST automático', async () => {
  const v = harness()
  v.controller.observe({ version: 2, status: 'generating' }, true)
  v.controller.observe({ version: 2, status: 'generating' }, true)
  assert.equal(v.tasks.size, 1)
  await v.tick()
  assert.equal(v.posts(), 0)
  assert.equal(v.reads(), 1)
})
test('GET de padres anterior al POST no cancela generación ni su sondeo', async () => {
  const v = harness()
  v.controller.observe({ version: 2, status: 'not_generated' }, true)
  await v.controller.start()
  assert.equal(v.tasks.size, 1)
  v.controller.observe({ version: 2, status: 'not_generated' }, true)
  assert.equal(v.latest().status, 'generating')
  assert.equal(v.tasks.size, 1)
  await v.tick()
  assert.equal(v.latest().status, 'ready')
  assert.equal(v.posts(), 1)
})
test('cambio de informe y dispose cancelan sondeos y descartan POST/GET tardíos', async () => {
  const response = deferred(), v = harness({ generate: () => response.promise })
  v.controller.observe(null, true)
  const old = v.controller.start()
  v.controller.reset('report_b')
  v.controller.observe(null, true)
  response.resolve(resultsFixture())
  await old
  assert.equal(v.latest().status, 'not_generated')
  const reading = deferred(), w = harness({ read: () => reading.promise })
  w.controller.observe({ version: 2, status: 'generating' }, true)
  const poll = w.controller.resume()
  w.controller.dispose()
  const before = w.changes.length
  reading.resolve(resultsFixture())
  await poll
  assert.equal(w.changes.length, before)
  assert.equal(w.tasks.size, 0)
})
test('fallo de transporte no reintenta POST; consulta explícita recupera estado', async () => {
  const v = harness({ generate: () => { throw new Error('mensaje privado no visible') }, read: () => ({ version: 2, status: 'not_generated' }) })
  v.controller.observe(null, true)
  await v.controller.start()
  assert.equal(v.posts(), 1)
  assert.equal(v.tasks.size, 0)
  assert.equal(v.problems.at(-1), 'connection')
  await v.controller.resume()
  assert.equal(v.reads(), 1)
  assert.equal(v.posts(), 1)
  assert.equal(v.latest().status, 'not_generated')
})
test('plazo de sondeo termina sin nuevas generaciones y puede consultarse de nuevo', async () => {
  const v = harness({ windowMs: 3000, read: () => ({ version: 2, status: 'generating' }) })
  v.controller.observe({ version: 2, status: 'generating' }, true)
  await v.tick(3000)
  assert.equal(v.tasks.size, 0)
  assert.equal(v.problems.at(-1), 'poll_timeout')
  await v.controller.resume()
  assert.equal(v.posts(), 0)
  assert.equal(v.reads(), 2)
  v.controller.dispose()
})
test('stale o failed nunca exponen datos antiguos y rechaza referencias incompletas', () => {
  for (const status of ['stale', 'failed', 'generating']) assert.equal(resultsSnapshot({ ...resultsFixture(), status }).data, null)
  const invalid = resultsFixture()
  invalid.data.findings[0].refs = []
  assert.equal(resultsSnapshot(invalid).status, 'failed')
  assert.equal(resultsSnapshot(invalid).data, null)
  assert.equal(resultsSnapshot({ version: 1, status: 'ready' }).data, null)
})
test('ready no retrocede por GET anterior al trabajo; hash distinto y stale sí invalidan', () => {
  const v = harness()
  v.controller.observe(resultsFixture(), true)
  v.controller.observe({ version: 2, status: 'generating', report_sha256: 'a'.repeat(64) }, true)
  assert.equal(v.latest().status, 'ready')
  v.controller.observe({ version: 2, status: 'stale', data: resultsFixture().data }, true)
  assert.equal(v.latest().status, 'stale')
  assert.equal(v.latest().data, null)
})
test('DTO v2 exige selección extractiva sin categorías derivadas, topes y respaldos por posición', () => {
  const mutations = [
    d => { d.findings[0].kind = 'condition' },
    d => { d.findings[0].implication = 'Prosa añadida que no pertenece al contrato' },
    d => { d.findings[0].id = '../unsafe' },
    d => { d.findings[0].text = 'a'.repeat(601) },
    d => { d.headline.refs.push(d.headline.refs[0]) },
    d => { d.contrasts[0].refs.pop() },
    d => { d.contrasts[0].explanation = 'Explicación libre' },
    d => { d.limitations[0].refs[0] = { ...d.limitations[0].refs[0], section_title: 't'.repeat(501) } }
  ]
  for (const mutate of mutations) {
    const value = structuredClone(resultsFixture())
    mutate(value.data)
    assert.equal(resultsSnapshot(value).status, 'failed')
    assert.equal(resultsSnapshot(value).data, null)
  }
  assert.equal(resultsSnapshot(resultsFixture()).status, 'ready')
  assert.equal(resultsSnapshot({ ...resultsFixture(), version: 1 }).data, null)
})
test('cliente results envía POST sin body/retry y GET corto con signal', async () => {
  const script = readFileSync(new URL('../src/api/report.js', import.meta.url), 'utf8').replace(/^import .*$/gm, '')
  const calls = [], service = { post: (...args) => { calls.push(['post', ...args]); return Promise.resolve() }, get: (...args) => { calls.push(['get', ...args]); return Promise.resolve() } }
  const api = new Function('service', script.replace(/export const /g, 'const ') + '\nreturn {generateReportResults,getReportResults};')(service)
  const signal = new AbortController().signal
  await api.generateReportResults('report_synthetic', { signal })
  await api.getReportResults('report_synthetic', { signal })
  assert.equal(calls[0][2], undefined)
  assert.equal(calls[0][3].timeout, 15000)
  assert.equal(calls[1][2].timeout, 15000)
  assert.equal(calls[1][2].signal, signal)
})
