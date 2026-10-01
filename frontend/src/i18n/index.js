import { createI18n } from 'vue-i18n'
import languages from '../../../locales/languages.json'
// Español, siempre: es el idioma por defecto y el de reserva (`fallbackLocale`), así que va dentro del paquete
import es from '../../../locales/es.json'

// El resto de idiomas se descargan solo si se eligen. Con los tres dentro del paquete, quien usa la app en español
// bajaba ~190 kB de textos (≈ 50 kB comprimidos) que no iba a leer.
const loaders = import.meta.glob('../../../locales/!(languages|es).json')

const availableLocales = [{ key: 'es', label: languages.es?.label || 'Español' }]
const loaderFor = {}
for (const path in loaders) {
  const key = path.match(/\/([^/]+)\.json$/)[1]
  if (languages[key]) {
    loaderFor[key] = loaders[path]
    availableLocales.push({ key, label: languages[key].label })
  }
}

// Solo idiomas con archivo de traducciones (languages.json declara más). El almacenamiento puede estar bloqueado
// (navegación privada, datos del sitio desactivados): sin esto la app entera quedaba en blanco al arrancar.
let storedLocale = null
try { storedLocale = localStorage.getItem('locale') } catch (_) { /* sin almacenamiento: español */ }
const savedLocale = storedLocale && (storedLocale === 'es' || loaderFor[storedLocale]) ? storedLocale : 'es'

const i18n = createI18n({
  legacy: false,
  locale: 'es',
  fallbackLocale: 'es',
  messages: { es }
})

const loaded = new Set(['es'])

// Cambia de idioma descargando antes el archivo si hace falta (si la descarga falla, se queda en el actual)
export async function setLocale(key) {
  if (key !== 'es' && !loaderFor[key]) return false
  if (!loaded.has(key)) {
    const module = await loaderFor[key]()
    i18n.global.setLocaleMessage(key, module.default)
    loaded.add(key)
  }
  i18n.global.locale.value = key
  return true
}

// La app espera a esto antes de pintarse: así quien tiene guardado otro idioma no ve un parpadeo en español
export const localeReady = savedLocale === 'es' ? Promise.resolve(true) : setLocale(savedLocale).catch(() => false)

export { availableLocales }
export default i18n
