import { ref, watch } from 'vue'

// «Detalles técnicos»: endpoints, IDs y el registro completo del sistema.
// Ocultos por defecto (Simuloo lo usa gente de marketing, no desarrolladores);
// la preferencia se recuerda en el navegador y vale para toda la app.
const STORAGE_KEY = 'simuloo_show_tech'

const read = () => {
  try { return localStorage.getItem(STORAGE_KEY) === '1' } catch { return false }
}

const showTech = ref(read())

const apply = (value) => {
  if (typeof document !== 'undefined') document.body.classList.toggle('show-tech', value)
}
apply(showTech.value)

watch(showTech, (value) => {
  apply(value)
  try { localStorage.setItem(STORAGE_KEY, value ? '1' : '0') } catch { /* modo privado */ }
})

export function useTechDetails () {
  return {
    showTech,
    toggleTech: () => { showTech.value = !showTech.value }
  }
}
