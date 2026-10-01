import PocketBase, { BaseAuthStore } from 'pocketbase'

const PB_URL = import.meta.env.VITE_POCKETBASE_URL || 'https://pocketbase.koolgrowth.com'

// El SDK guarda la sesión en `window.localStorage` sin protegerlo: con los datos del sitio bloqueados (navegación
// privada de algunos navegadores, política del equipo) lanza un SecurityError al arrancar y la app entera se quedaba en
// blanco. Si no se puede usar, la sesión vive en memoria: vale para esta visita.
const storageWorks = () => {
  try {
    const probe = '__simuloo_probe__'
    window.localStorage.setItem(probe, '1')
    window.localStorage.removeItem(probe)
    return true
  } catch (_) {
    return false
  }
}

export const pb = new PocketBase(PB_URL, storageWorks() ? undefined : new BaseAuthStore())
