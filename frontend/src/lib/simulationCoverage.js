// El motor inicia en 00:00 y aplica el límite a las rondas del plan.
// Solo describe el reloj simulado; no interpreta acciones como respuestas de una encuesta.
const positive = (value) => Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : null

export function simulationCoverage(config, rounds) {
  const time = config?.time_config
  const minutes = positive(time?.minutes_per_round)
  const hours = positive(time?.total_simulation_hours)
  if (!minutes || !hours) return null
  const plannedRounds = Math.floor(hours * 60 / minutes)
  if (!plannedRounds) return null
  const requested = Number(rounds)
  if (!Number.isFinite(requested) || requested < 0) return null
  const effectiveRounds = Math.min(plannedRounds, Math.floor(requested))
  // El plan acotado por la API nunca supera 100 rondas. Para un registro antiguo
  // más largo basta recorrer un día completo para saber si cubrió sus picos.
  const visited = new Set()
  for (let r = 0; r < Math.min(effectiveRounds, 10000) && visited.size < 24; r++) {
    visited.add(Math.floor(r * minutes / 60) % 24)
  }
  const peakHours = Array.isArray(time.peak_hours) ? time.peak_hours : []
  const missingPeakHours = [...new Set(peakHours.filter(h => Number.isInteger(h) && h >= 0 && h < 24 && !visited.has(h)))]
  return {
    plannedRounds,
    plannedHours: plannedRounds * minutes / 60,
    effectiveRounds,
    effectiveHours: effectiveRounds * minutes / 60,
    limited: effectiveRounds < plannedRounds,
    missingPeakHours
  }
}
