import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { profileOrigin, profileDemographic, profilePassages, profileStyleKeys, knownProfileText, legacyProfilePersona } from '../src/lib/profilePresentation.js'

const profile = (identity_kind, extra = {}) => ({ profile_schema_version: 1, identity_kind, ...extra })
test('procedencia distingue material aportado, encuesta, público ficticio, sin vincular y legado', () => {
  for (const [kind, origin] of [['named_actor', 'provided'], ['institution', 'provided'], ['survey_respondent', 'survey'], ['synthetic_audience', 'synthetic'], ['unconfirmed_actor', 'unconfirmed']]) assert.equal(profileOrigin(profile(kind)), origin)
  assert.equal(profileOrigin({ identity_kind: 'named_actor', data_source: 'CIS' }), 'legacy')
  assert.equal(profileOrigin(profile('not_a_kind')), 'legacy')
  assert.equal(profileOrigin({ profile_schema_version: 2, identity_kind: 'named_actor' }), 'legacy')
})
test('actores y legado no presentan defaults edad/MBTI/género/país como hechos', () => {
  for (const p of [profile('named_actor', { age: 30, mbti: 'ISTJ', gender: 'male', country: 'España' }), profile('institution', { age: 30 }), { age: 30, mbti: 'ISTJ' }]) {
    for (const field of ['age', 'mbti', 'gender', 'country']) assert.equal(profileDemographic(p, field), null)
  }
  assert.equal(profileDemographic(profile('survey_respondent', { age: 54 }), 'age'), 54)
  assert.equal(profileDemographic(profile('survey_respondent', { mbti: 'ISTJ' }), 'mbti'), null)
  assert.equal(profileDemographic(profile('synthetic_audience', { mbti: 'ISTJ' }), 'mbti'), 'ISTJ')
  for (const value of [null, undefined, 0, '30', -1]) assert.equal(profileDemographic(profile('survey_respondent', { age: value }), 'age'), null)
  for (const value of ['unknown', 'desconocido', '-', '未知', null, '']) assert.equal(knownProfileText(value), null)
})
test('pasajes se conservan literales sin reconstruir hechos ni atribuir citas a legado', () => {
  const text = 'Si el tribunal lo admite, podría convocarse. No se ha convocado. <script>alert(1)</script>'
  const p = profile('named_actor', { source_passages: [{ text, source_sha256: 'digest', start: 0, end: text.length }] })
  assert.equal(profilePassages(p)[0].text, text)
  assert.deepEqual(profilePassages({ source_passages: p.source_passages }), [])
  assert.deepEqual(profilePassages(profile('synthetic_audience', { source_passages: p.source_passages })), [])
})
test('estilo solo admite opciones cerradas, nunca biografía libre como rasgo', () => {
  const p = profile('named_actor', { communication_style: { formality: 'formal', length: 'balanced', caution: 'cautious', disagreement: 'respectful' } })
  assert.deepEqual(profileStyleKeys(p), ['profiles.style.formal', 'profiles.style.balanced', 'profiles.style.cautious', 'profiles.style.respectful'])
  assert.deepEqual(profileStyleKeys(profile('named_actor', { communication_style: { formality: 'ganó las elecciones', length: '<html>' } })), [])
})
test('nuevos rótulos y mensajes tienen traducción propia en los tres idiomas', () => {
  for (const lang of ['es', 'en', 'zh']) {
    const messages = JSON.parse(readFileSync(new URL(`../../locales/${lang}.json`, import.meta.url), 'utf8'))
    for (const key of ['provided', 'survey', 'synthetic', 'legacy', 'unconfirmed']) {
      assert.equal(typeof messages.profiles.origin[key], 'string')
      assert.equal(typeof messages.profiles.description[key], 'string')
    }
    assert.equal(typeof messages.profiles.fictionalBiography, 'string')
    for (const key of ['invalidAudienceSize', 'audienceSizeUnavailable']) assert.equal(typeof messages.api[key], 'string')
    for (const key of ['audienceSizeLabel', 'audienceSizeAuto', 'audienceSizeExplicit', 'audienceSizeNumber', 'audienceSizeHint']) assert.equal(typeof messages.step2[key], 'string')
  }
})

test('prompt técnico canónico no se presenta como trasfondo del personaje', () => {
  const prompt = 'SOURCE_PASSAGES_JSON: [{"text": "memory"}]'
  assert.equal(legacyProfilePersona(profile('named_actor', { persona: prompt })), null)
  assert.equal(legacyProfilePersona(profile('survey_respondent', { persona: prompt })), null)
  assert.equal(legacyProfilePersona({ persona: 'Perfil anterior legible' }), 'Perfil anterior legible')
})
