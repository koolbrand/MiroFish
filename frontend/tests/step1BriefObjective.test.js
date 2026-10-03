// Regresión de la vista real con GET /brief falso: sin LLM ni datos de producción.
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref, reactive, computed } from 'vue'
const script = readFileSync(new URL('../src/components/Step1GraphBuild.vue', import.meta.url), 'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(getProjectBrief, project = { project_id: 'proj_a' }) {
  const props = reactive({ projectData: project, systemLogs: [] })
  let unmount
  const bindings = {
    ref, computed, watch: () => {}, nextTick: fn => Promise.resolve().then(fn), onUnmounted: fn => { unmount = fn },
    defineProps: () => props, defineEmits: () => () => {},
    useI18n: () => ({ t: key => key, locale: ref('es') }), useRouter: () => ({ push: () => {} }),
    useTechDetails: () => ({ showTech: ref(false), toggleTech: () => {} }),
    usePipeline: () => ({ isRunning: ref(false), state: ref(null) }), getProjectBrief,
    entityLabel: n => n, relationLabel: n => n, attributeLabel: n => n
  }
  const result = new Function(...Object.keys(bindings), script + '\nreturn { loadBrief, objective, objectiveEmpty, briefLoading, brief, briefError };')(...Object.values(bindings))
  return { ...result, props, unmount: () => unmount() }
}
test('objetivo omitido en creación se recupera del brief sin aviso vacío durante carga', async () => {
  const request = deferred()
  const v = view(() => request.promise)
  const loading = v.loadBrief('proj_a')
  assert.equal(v.briefLoading.value, true)
  assert.equal(v.objective.value, '')
  assert.equal(v.objectiveEmpty.value, false)
  request.resolve({ success: true, data: { simulation_requirement: '  Comparar reacciones al escenario  ', files: [] } })
  await loading
  assert.equal(v.objective.value, 'Comparar reacciones al escenario')
  assert.equal(v.objectiveEmpty.value, false)
  assert.equal(v.briefLoading.value, false)
})
test('objetivo del proyecto tiene prioridad y solo un brief leído realmente vacío activa aviso', async () => {
  const v = view(async () => ({ success: true, data: { simulation_requirement: 'Versión del brief' } }), { project_id: 'proj_a', simulation_requirement: 'Objetivo del proyecto' })
  await v.loadBrief('proj_a')
  assert.equal(v.objective.value, 'Objetivo del proyecto')
  const empty = view(async () => ({ success: true, data: { simulation_requirement: '  ' } }))
  await empty.loadBrief('proj_a')
  assert.equal(empty.objectiveEmpty.value, true)
})
test('error al consultar brief no afirma que el proyecto carece de objetivo', async () => {
  const v = view(async () => { throw new Error('offline') })
  await v.loadBrief('proj_a')
  assert.equal(v.objectiveEmpty.value, false)
  assert.equal(v.briefLoading.value, false)
  assert.equal(v.briefError.value, 'step1.briefLoadFailed')
})
test('respuestas antiguas no pisan el objetivo aun regresando al mismo proyecto', async () => {
  const oldA = deferred(), b = deferred(), newA = deferred()
  const queue = [oldA, b, newA]
  const v = view(() => queue.shift().promise)
  const first = v.loadBrief('proj_a')
  v.props.projectData = { project_id: 'proj_b' }
  const second = v.loadBrief('proj_b')
  v.props.projectData = { project_id: 'proj_a' }
  const third = v.loadBrief('proj_a')
  oldA.resolve({ success: true, data: { simulation_requirement: 'Objetivo antiguo de A' } })
  await first
  assert.equal(v.briefLoading.value, true)
  assert.equal(v.objective.value, '')
  newA.resolve({ success: true, data: { simulation_requirement: 'Objetivo vigente de A' } })
  await third
  b.resolve({ success: true, data: { simulation_requirement: 'Objetivo de B' } })
  await second
  assert.equal(v.objective.value, 'Objetivo vigente de A')
  assert.equal(v.briefLoading.value, false)
})
test('respuesta posterior a cerrar la vista no restaura brief ni objetivo', async () => {
  const request = deferred()
  const v = view(() => request.promise)
  const loading = v.loadBrief('proj_a')
  v.unmount()
  request.resolve({ success: true, data: { simulation_requirement: 'Respuesta tardía' } })
  await loading
  assert.equal(v.brief.value, null)
  assert.equal(v.objective.value, '')
})
