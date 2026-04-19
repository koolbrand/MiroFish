import { ref, readonly } from 'vue'
import { pb } from '../lib/pocketbase'

const user = ref(pb.authStore.model)
const loading = ref(true)

// Escuchar cambios en el estado de autenticación de PocketBase
pb.authStore.onChange((token, model) => {
  user.value = model
  loading.value = false
})

/**
 * Intenta refrescar el token contra PocketBase.
 *
 * - Si el token es válido pero está cerca de expirar, devuelve uno nuevo
 *   con la expiración extendida. Así una sesión abierta puede durar meses
 *   sin obligar al usuario a volver a hacer login.
 * - Si el token fue revocado o ya expiró en el servidor, limpia el store
 *   (lo que dispara el router guard y envía al usuario a /login).
 * - Errores de red se ignoran en silencio: la UX no debería romperse porque
 *   el usuario pierda WiFi momentáneamente.
 */
export async function refreshAuth() {
  if (!pb.authStore.isValid) return false

  try {
    await pb.collection('users').authRefresh()
    return true
  } catch (err) {
    // 401 / 403 → token revocado o expirado server-side
    const status = err?.status ?? err?.response?.status
    if (status === 401 || status === 403) {
      pb.authStore.clear()
      return false
    }
    // Error de red u otra cosa → dejamos la sesión como está,
    // se reintentará en el próximo visibilitychange o intervalo.
    console.warn('authRefresh failed (will retry):', err?.message || err)
    return true
  }
}

// Intentar refresh al cargar la app (tras recarga, nueva pestaña, etc.)
if (pb.authStore.isValid) {
  user.value = pb.authStore.model
  refreshAuth() // fire-and-forget
}
loading.value = false

// Refresh periódico cada 60 min para sesiones muy largas
// (la sesión default de PocketBase dura 14 días; esto la mantiene viva
// mientras la app esté abierta)
const REFRESH_INTERVAL_MS = 60 * 60 * 1000
setInterval(() => {
  if (pb.authStore.isValid) {
    refreshAuth()
  }
}, REFRESH_INTERVAL_MS)

export function useAuth() {
  return {
    user: readonly(user),
    loading: readonly(loading),
    isAuthenticated: () => pb.authStore.isValid,
    refresh: refreshAuth,
    logout: () => {
      pb.authStore.clear()
      user.value = null
    }
  }
}
