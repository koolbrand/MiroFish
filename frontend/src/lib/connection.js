// ¿Llega la app al servidor? Tres fallos de red seguidos (sin ninguna respuesta) = sin conexión; la primera respuesta
// de cualquier tipo lo repone. Antes, con el servidor caído, las pantallas seguían «vivas» (sondeos fallando en silencio
// con la consola como único testigo) y la persona no sabía por qué no avanzaba nada.
import { ref } from 'vue'

export const offline = ref(false)

let failures = 0
const THRESHOLD = 3

export const noteNetworkFailure = () => {
  failures += 1
  if (failures >= THRESHOLD) offline.value = true
}

export const noteServerReached = () => {
  failures = 0
  if (offline.value) offline.value = false
}

if (typeof window !== 'undefined') {
  window.addEventListener('offline', () => { offline.value = true })
  window.addEventListener('online', () => { failures = 0; offline.value = false })
}
