import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { resultsFixture } from './reportResults.fixture.js'
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(file, getReport) {
  const source = readFileSync(new URL(`../src/components/${file}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  const props = Vue.reactive({ reportId: 'report_a' })
  let close = () => {}
  const bindings = { ...Vue, defineProps: () => props, defineEmits: () => () => {}, watch: () => {}, onMounted: () => {}, onUnmounted: fn => { close = fn },
    useRouter: () => ({ push: () => {} }), useI18n: () => ({ t: key => key, locale: Vue.ref('es') }), useTechDetails: () => ({ showTech: Vue.ref(false), toggleTech: () => {} }),
    document: { removeEventListener: () => {} }, getReport, getAgentLog: async () => ({ success: true, data: { logs: [] } }) }
  const method = file === 'Step4Report' ? 'checkReportStatus' : 'loadReportData'
  const api = new Function(...Object.keys(bindings), script + `\nreturn {load:${method},acceptReportResults,reportResults,reportResultsReady};`)(...Object.values(bindings))
  return { ...api, props, close: () => close(), source }
}
for (const file of ['Step4Report', 'Step5Interaction']) {
  test(`${file}: results y completed vienen del GET; handler invalida GET anterior al POST`, async () => {
    const late = deferred(), v = view(file, () => late.promise)
    const get = v.load()
    v.acceptReportResults({ version: 2, status: 'generating', data: null })
    late.resolve({ success: true, data: { status: 'completed', results: { version: 2, status: 'not_generated' } } })
    await get
    assert.equal(v.reportResults.value.status, 'generating')
    assert.match(v.source, /@results-updated="acceptReportResults"/)
    const good = view(file, async () => ({ success: true, data: { status: 'completed', results: resultsFixture() } }))
    await good.load()
    assert.equal(good.reportResultsReady.value, true)
    assert.equal(good.reportResults.value.status, 'ready')
  })
  test(`${file}: cambio reportId/unmount descarta payload anterior`, async () => {
    for (const dispose of [false, true]) {
      const old = deferred(), v = view(file, () => old.promise)
      const read = v.load()
      if (dispose) v.close()
      else v.props.reportId = 'report_b'
      old.resolve({ success: true, data: { status: 'completed', results: resultsFixture() } })
      await read
      assert.equal(v.reportResults.value, null)
      assert.equal(v.reportResultsReady.value, false)
    }
  })
}
