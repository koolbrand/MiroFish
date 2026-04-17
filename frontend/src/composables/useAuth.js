import { ref, readonly } from 'vue'
import { pb } from '../lib/pocketbase'

const user = ref(pb.authStore.model)
const loading = ref(true)

// Escuchar cambios en el estado de autenticación de PocketBase
pb.authStore.onChange((token, model) => {
  user.value = model
  loading.value = false
})

// Sesión ya existente
if (pb.authStore.isValid) {
  user.value = pb.authStore.model
}
loading.value = false

export function useAuth() {
  return {
    user: readonly(user),
    loading: readonly(loading),
    isAuthenticated: () => pb.authStore.isValid,
    logout: () => {
      pb.authStore.clear()
      user.value = null
    }
  }
}
