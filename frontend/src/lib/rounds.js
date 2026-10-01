// Rondas de la simulación: una sola fuente para la portada, el paso 2 y los textos de duración.
// Los topes del servidor (10–100) están en backend/app/config.py: SIMULATION_MIN_ROUNDS / SIMULATION_MAX_ROUNDS.

// Modo automático: tres duraciones de conversación a elegir. La del medio es la de siempre.
export const ROUNDS_CHOICES = [
  { key: 'short', rounds: 20 },
  { key: 'standard', rounds: 40 },
  { key: 'long', rounds: 72 },
]
export const DEFAULT_ROUNDS = 40

// Paso a paso: el deslizador no pasa de aquí hasta que haya una simulación larga probada en producción.
export const MANUAL_MAX_ROUNDS = 72
export const MANUAL_MIN_ROUNDS = 10

// Lo máximo que el servidor arranca (si la configuración propone más, lo recorta).
export const SERVER_MAX_ROUNDS = 100

// Medido en producción: ~35 s por ronda con 47 personas (solo la simulación; el análisis y el informe van aparte).
const MINUTES_PER_ROUND = 35 / 60

export const roundsMinutes = (rounds) => Math.round(rounds * MINUTES_PER_ROUND)

// Un número de rondas válido para el modo automático; si no lo es, el de por defecto.
export const normalizeRounds = (value) => {
  const n = Number(value)
  return ROUNDS_CHOICES.some((c) => c.rounds === n) ? n : DEFAULT_ROUNDS
}
