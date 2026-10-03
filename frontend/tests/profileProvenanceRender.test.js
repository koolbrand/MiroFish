// Renderiza la plantilla real con Vue: ni DOM, modelos externos ni bases de datos.
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { profileOrigin, profilePassages, profileStyleKeys } from '../src/lib/profilePresentation.js'
const file = readFileSync(new URL('../src/components/ProfileProvenance.vue', import.meta.url), 'utf8')
const template = file.match(/<template>([\s\S]*?)<\/template>\s*<script setup>/)[1]
const script = file.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const render = new Function('Vue', compile(template, { prefixIdentifiers: true }).code)(Vue)
const messages = JSON.parse(readFileSync(new URL('../../locales/es.json', import.meta.url), 'utf8'))
async function html(profile) {
  const Component = {
    props: ['profile', 'compact'], render,
    setup(props) {
      return new Function('computed', 'defineProps', 'profileOrigin', 'profilePassages', 'profileStyleKeys', script + '\nreturn {origin, passages, styleKeys};')(Vue.computed, () => props, profileOrigin, profilePassages, profileStyleKeys)
    }
  }
  const app = Vue.createSSRApp(Component, { profile })
  app.config.globalProperties.$t = key => key.split('.').reduce((value, part) => value?.[part], messages) || key
  return renderToString(app)
}
test('material aportado mantiene condicional y negación literales y nunca interpreta HTML', async () => {
  const output = await html({ profile_schema_version: 1, identity_kind: 'named_actor', source_passages: [{ text: 'Si se admite, podría convocarse. No se ha convocado. <script>alert(1)</script>' }], communication_style: { caution: 'cautious' }, persona: 'PROMPT_INTERNO_NO_VISIBLE' })
  assert.match(output, /Material aportado/)
  assert.match(output, /no se ha verificado externamente/)
  assert.match(output, /Si se admite, podría convocarse\. No se ha convocado\./)
  assert.match(output, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/)
  assert.equal(output.includes('<script>'), false)
  assert.equal(output.includes('PROMPT_INTERNO_NO_VISIBLE'), false)
  assert.match(output, /Estilo de comunicación simulado/)
})
test('encuesta y legado se anuncian con límites distintos', async () => {
  const survey = await html({ profile_schema_version: 1, identity_kind: 'survey_respondent', survey_facts: ['Recuerdo de voto: no respondió'] })
  assert.match(survey, /Encuesta real/)
  assert.match(survey, /respuestas nuevas son generados/)
  assert.match(survey, /Recuerdo de voto: no respondió/)
  const legacy = await html({ bio: 'Texto antiguo', data_source: 'CIS' })
  assert.match(legacy, /Perfil de una versión anterior/)
  assert.equal(legacy.includes('Encuesta real'), false)
})

test('biografía ficticia canónica es visible y escapada solo en público sintético', async () => {
  const biography = 'Personaje ficticio con preferencia imaginada. <img src=x onerror=alert(1)>'
  const fictional = await html({ profile_schema_version: 1, identity_kind: 'synthetic_audience', fictional_biography: biography })
  assert.match(fictional, /Biografía ficticia/)
  assert.match(fictional, /Personaje ficticio con preferencia imaginada\./)
  assert.match(fictional, /&lt;img src=x onerror=alert\(1\)&gt;/)
  assert.equal(fictional.includes('<img'), false)
  for (const identity_kind of ['named_actor', 'institution', 'survey_respondent', 'unconfirmed_actor']) {
    const output = await html({ profile_schema_version: 1, identity_kind, fictional_biography: biography })
    assert.equal(output.includes('Biografía ficticia'), false)
    assert.equal(output.includes('preferencia imaginada'), false)
  }
  const legacy = await html({ fictional_biography: biography })
  assert.equal(legacy.includes('Biografía ficticia'), false)
})
