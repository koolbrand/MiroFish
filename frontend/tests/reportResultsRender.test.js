import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createResultsController } from '../src/lib/reportResults.js'
import { resultsFixture } from './reportResults.fixture.js'
import MiniMarkdown from '../src/lib/miniMarkdown.js'

function parts(name) {
  const source = readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
  return { script: source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, ''), render: new Function('Vue', compile(source.match(/<template>([\s\S]*?)<\/template>\s*<script setup>/)[1], { prefixIdentifiers: true }).code)(Vue) }
}
const main = parts('ReportResults'), references = parts('ReportResultReferences')
async function html(results, ready = true, locale = 'es') {
  let requests = 0
  const i18n = createI18n({ legacy: false, locale, messages: { [locale]: JSON.parse(readFileSync(new URL(`../../locales/${locale}.json`, import.meta.url), 'utf8')) } })
  const Component = { props: ['reportId', 'results', 'reportReady', 'summary'], render: main.render, setup(props) {
    const bindings = { ...Vue, defineProps: () => props, defineEmits: () => () => {},
      getReportResults: () => { requests++; throw new Error('API no permitida en SSR') }, generateReportResults: () => { requests++; throw new Error('POST no permitido en SSR') },
      createResultsController: options => createResultsController({ ...options, schedule: () => 1, cancel: () => {} }) }
    return new Function(...Object.keys(bindings), main.script + '\nreturn {snapshot,busy,problem,controller,data,canCreate,errorKey};')(...Object.values(bindings))
  } }
  const app = Vue.createSSRApp(Component, { reportId: 'report_synthetic', results, reportReady: ready, summary: 'RESUMEN_DE_RESPALDO' })
  app.use(i18n)
  app.component('MiniMarkdown', MiniMarkdown)
  app.component('ReportResultReferences', { props: ['refs'], render: references.render, setup(props) {
    return new Function('computed', 'defineProps', references.script + '\nreturn {sourceRefs};')(Vue.computed, () => props)
  } })
  const output = await renderToString(app)
  return { output, requests }
}
test('render real abre con hallazgo literal y no duplica summary ni presenta actividad', async () => {
  const { output, requests } = await html(resultsFixture())
  assert.match(output, /La claridad de las condiciones reduce la fricción/)
  assert.match(output, /Selección de hallazgos del informe/)
  assert.match(output, /Hallazgo/)
  assert.match(output, /Posiciones observadas/)
  assert.match(output, /posiciones y tamaños no indican apoyo/)
  assert.match(output, /Lo que no puede concluirse/)
  assert.equal(output.includes('RESUMEN_DE_RESPALDO'), false)
  assert.equal(output.includes('Acciones registradas'), false)
  assert.equal(output.includes('overview-metrics'), false)
  assert.equal(requests, 0)
})
test('legacy ofrece CTA explícito; pending no muestra botón ni empieza ningún trabajo', async () => {
  const legacy = await html(null)
  assert.match(legacy.output, /Crear resumen visual de resultados/)
  assert.match(legacy.output, /informe terminado/)
  assert.equal(legacy.requests, 0)
  const pending = await html(null, false)
  assert.equal(pending.output.includes('<button'), false)
  assert.match(pending.output, /RESUMEN_DE_RESPALDO/)
  assert.equal(pending.requests, 0)
})
test('failed y stale conservan informe pero ocultan resultados anteriores y permiten retry', async () => {
  for (const status of ['failed', 'stale']) {
    const { output, requests } = await html({ ...resultsFixture(), status, error_code: 'payload_invalid' })
    assert.equal(output.includes('La claridad de las condiciones reduce la fricción'), false)
    assert.match(output, /Reintentar el resumen visual/)
    assert.match(output, /RESUMEN_DE_RESPALDO/)
    assert.equal(requests, 0)
  }
})
test('generating muestra estado y no CTA de generación', async () => {
  const { output, requests } = await html({ version: 2, status: 'generating' })
  assert.match(output, /Preparando el resumen visual/)
  assert.equal(output.includes('<button'), false)
  assert.equal(requests, 0)
})
test('citas, títulos y contenido son texto escapado; sin posiciones no se inventan', async () => {
  const input = resultsFixture()
  input.data.headline.text = '<script>dato inseguro</script>'
  input.data.findings[0].refs[0] = { section_index: 1, section_title: '<img src=x onerror=attack>', quote: 'Texto literal <script>alert(1)</script> del informe.' }
  input.data.contrasts = []
  const { output } = await html(input)
  assert.equal(output.includes('<script>'), false)
  assert.equal(output.includes('<img'), false)
  assert.match(output, /&lt;script&gt;dato inseguro&lt;\/script&gt;/)
  assert.match(output, /Texto literal &lt;script&gt;/)
  assert.match(output, /no son una comprobación independiente/)
  assert.equal(output.includes('Posiciones observadas'), false)
  assert.equal(output.includes('Qué podría cambiar el resultado'), false)
})
test('contenido propio del informe y controles tienen traducciones es/en/zh', async () => {
  for (const locale of ['es', 'en', 'zh']) {
    const { output } = await html(resultsFixture(), true, locale)
    assert.equal(output.includes('reportResults.'), false)
    assert.match(output, /<figcaption>/)
    assert.match(output, /<blockquote>/)
  }
})
test('markdown seguro conserva negación y fragmento completo, con origen fuera del desplegable', async () => {
  const input = resultsFixture()
  input.data.findings[0].text = '> **No hay evidencia** de que la propuesta garantice ventas. <img src=x onerror=attack>'
  const { output } = await html(input)
  assert.match(output, /<strong>No hay evidencia<\/strong> de que la propuesta garantice ventas/)
  assert.match(output, /&lt;img src=x onerror=attack&gt;/)
  assert.equal(output.includes('<img'), false)
  assert.match(output.replace(/<!--[\s\S]*?-->/g, ''), /class="result-source"[^>]*>Sección 1 · Conclusiones del ensayo ficticio<\/p><details>/)
  assert.equal(output.includes('Qué implica'), false)
})
