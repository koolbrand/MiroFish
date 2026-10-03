// La ficha conserva métricas del informe. Un dato ausente nunca equivale a cero.
const count = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
const flag = value => typeof value === 'boolean' ? value : null
export function evidenceFacts(evidence) {
  if (!evidence?.version) return null
  const a = evidence.agents || {}
  const r = evidence.execution || {}
  const s = evidence.source || {}
  const events = evidence.actions || {}
  return {
    agents: count(a.total), anchored: count(a.anchored), active: count(a.active),
    events: count(events.total),
    platforms: Object.entries(events.by_platform || {}).map(([name, n]) => ({ name, count: count(n) })),
    executedRounds: count(r.executed_rounds), configuredRounds: count(r.configured_rounds),
    executedHours: count(r.executed_hours), configuredHours: count(r.configured_hours),
    sourceCharacters: count(s.characters), sourceAvailable: flag(s.available), truncated: flag(s.truncated),
    populationCitation: typeof a.population_citation === 'string' ? a.population_citation : ''
  }
}
