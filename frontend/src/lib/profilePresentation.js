// Solo el contrato canónico declara de dónde procede la identidad. Los perfiles
// antiguos siguen legibles, pero no se les atribuye verificación retrospectiva.
const KINDS = new Set(['named_actor', 'institution', 'survey_respondent', 'synthetic_audience', 'unconfirmed_actor'])
export function profileOrigin(profile) {
  if (profile?.profile_schema_version !== 1 || !KINDS.has(profile.identity_kind)) return 'legacy'
  if (profile.identity_kind === 'survey_respondent') return 'survey'
  if (profile.identity_kind === 'synthetic_audience') return 'synthetic'
  if (profile.identity_kind === 'unconfirmed_actor') return 'unconfirmed'
  return 'provided'
}
export function knownProfileText(value) {
  if (typeof value !== 'string') return null
  const text = value.trim()
  return !text || /^(unknown|unspecified|undefined|null|none|n\/a|desconocid[oa]|no especificad[oa]|未知|未指定|-)$/i.test(text) ? null : text
}
export function profileDemographic(profile, field) {
  const origin = profileOrigin(profile)
  // No presentar defaults históricos ni demografía ficticia como hechos de un actor.
  if (origin !== 'survey' && origin !== 'synthetic') return null
  const value = profile?.[field]
  if (field === 'age') return Number.isInteger(value) && value > 0 && value <= 120 ? value : null
  if (field === 'gender') return ['male', 'female', 'other'].includes(value) ? value : null
  if (field === 'mbti') return origin === 'synthetic' && /^[IE][NS][TF][JP]$/i.test(value || '') ? value : null
  return knownProfileText(value)
}
export function profilePassages(profile) {
  if (!['provided', 'unconfirmed'].includes(profileOrigin(profile))) return []
  return Array.isArray(profile.source_passages) ? profile.source_passages.filter(p => typeof p?.text === 'string' && p.text.trim()) : []
}
export function profileStyleKeys(profile) {
  if (profileOrigin(profile) === 'legacy') return []
  const style = profile.communication_style || {}
  const options = { formality: ['formal', 'conversational'], length: ['brief', 'balanced'], caution: ['cautious'], disagreement: ['respectful'] }
  return Object.entries(options).flatMap(([field, values]) => values.includes(style[field]) ? [`profiles.style.${style[field]}`] : [])
}

export function legacyProfilePersona(profile) {
  return profile?.profile_schema_version == null && typeof profile.persona === 'string' ? profile.persona : null
}
