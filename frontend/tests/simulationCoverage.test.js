import { test } from 'node:test'
import assert from 'node:assert/strict'
import { simulationCoverage } from '../src/lib/simulationCoverage.js'
const config = { time_config: { total_simulation_hours: 72, minutes_per_round: 60, peak_hours: [20, 21, 22, 23] } }
test('el caso electoral de 15 rondas no cubre las horas punta de un plan de 72', () => {
  assert.deepEqual(simulationCoverage(config, 15), { plannedRounds: 72, plannedHours: 72, effectiveRounds: 15, effectiveHours: 15, limited: true, missingPeakHours: [20, 21, 22, 23] })
})
test('límite mayor que el plan no promete rondas ni horas adicionales', () => {
  assert.equal(simulationCoverage(config, 100).effectiveRounds, 72)
  assert.equal(simulationCoverage(config, 100).limited, false)
  assert.deepEqual(simulationCoverage(config, 40).missingPeakHours, [])
})
test('se usa la hora de inicio de cada ronda, también en rondas de media hora', () => {
  const halfHour = { time_config: { total_simulation_hours: 24, minutes_per_round: 30, peak_hours: [7, 8] } }
  assert.deepEqual(simulationCoverage(halfHour, 16).missingPeakHours, [8])
  assert.equal(simulationCoverage(halfHour, 16).effectiveHours, 8)
})
test('configuración incompleta no fabrica duración; cero rondas conserva el cero', () => {
  assert.equal(simulationCoverage({}, 15), null)
  assert.equal(simulationCoverage(config, undefined), null)
  assert.equal(simulationCoverage(config, -1), null)
  assert.equal(simulationCoverage(config, 0).effectiveHours, 0)
})
