<template>
  <div class="language-switcher" :class="{ 'is-compact': compact }" ref="switcherRef">
    <button class="switcher-trigger" :aria-label="currentLabel" :aria-expanded="open" @click="toggleDropdown">
      <span class="lbl-long">{{ currentLabel }}</span><span class="lbl-short" aria-hidden="true">{{ shortLabel }}</span>
      <span class="caret" aria-hidden="true">{{ open ? '▲' : '▼' }}</span>
    </button>
    <ul v-if="open" class="switcher-dropdown">
      <li
        v-for="loc in availableLocales"
        :key="loc.key"
        class="switcher-option"
        :class="{ active: loc.key === locale }"
        @click="switchLocale(loc.key)"
      >
        {{ loc.label }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { availableLocales, setLocale } from '@/i18n/index.js'

defineProps({
  // solo el código del idioma (ES ▾): para cabeceras con poco sitio
  compact: { type: Boolean, default: false }
})
const { locale } = useI18n()
const open = ref(false)
const switcherRef = ref(null)

const currentLabel = computed(() => {
  const found = availableLocales.find(l => l.key === locale.value)
  return found ? found.label : locale.value
})

// En pantallas muy estrechas, el idioma se muestra con su código (ES · EN · 中文)
const shortLabel = computed(() => (currentLabel.value.length <= 3 ? currentLabel.value : locale.value.toUpperCase()))

const toggleDropdown = () => {
  open.value = !open.value
}

const switchLocale = async (key) => {
  open.value = false
  try {
    if (!(await setLocale(key))) return       // si el archivo del idioma no se pudo descargar, se queda en el actual
  } catch (_) {
    return
  }
  try { localStorage.setItem('locale', key) } catch (_) { /* almacenamiento bloqueado: vale para esta visita */ }
  document.documentElement.lang = key
}

const onClickOutside = (e) => {
  if (switcherRef.value && !switcherRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.documentElement.lang = locale.value
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.language-switcher {
  position: relative;
  display: inline-block;
  font-family: var(--kb-font-sans);
}

/* Light theme (default - for white header backgrounds) */
.switcher-trigger {
  background: transparent;
  color: var(--kb-text-2);
  border: 1px solid var(--kb-control-line);
  padding: 4px 12px;
  font-family: var(--kb-font-mono);
  font-size: 0.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.2s, opacity 0.2s;
}

.switcher-trigger:hover {
  border-color: var(--kb-text);
  background: var(--kb-soft);
}

.caret {
  font-size: 0.6rem;
}
.lbl-short { display: none; }
.is-compact .lbl-long { display: none; }
.is-compact .lbl-short { display: inline; }
@media (max-width: 400px) {
  .lbl-long { display: none; }
  .lbl-short { display: inline; }
  .switcher-trigger { padding: 4px 8px; gap: 4px; }
}

.switcher-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: #FFFFFF;
  border: 1px solid var(--kb-line-strong);
  list-style: none;
  padding: 4px 0;
  min-width: 100%;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.switcher-option {
  padding: 6px 12px;
  font-size: 0.8rem;
  color: var(--kb-text-2);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.switcher-option:hover {
  background: var(--kb-soft);
}

.switcher-option.active {
  color: var(--orange, var(--kb-accent-text));
}


</style>
