<template>
  <router-view />
  <TourOverlay />
  <ConnectionBanner />
</template>

<script setup>
import { onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { refreshAuth } from './composables/useAuth'
import TourOverlay from './components/TourOverlay.vue'
import ConnectionBanner from './components/ConnectionBanner.vue'

// El título y la descripción de la pestaña siguen al idioma elegido
// (index.html trae los de español para quien no ejecuta JavaScript).
const { t, locale } = useI18n()
watch(locale, () => {
  document.title = t('meta.title')
  document.querySelector('meta[name="description"]')?.setAttribute('content', t('meta.description'))
}, { immediate: true })

// Cuando la pestaña vuelve a ser visible tras una suspensión del
// equipo (tapa del portátil cerrada, monitor apagado, o simplemente
// estar en segundo plano mucho tiempo), refrescamos el token de
// PocketBase para que la sesión no muera silenciosamente ni se quede
// con datos obsoletos.
const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible') {
    refreshAuth()
  }
}

onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style>
/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: var(--kb-font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--kb-text);
  background-color: var(--kb-bg);
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--kb-soft);
}

::-webkit-scrollbar-thumb {
  background: var(--kb-text);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--kb-text-2);
}

/* 全局按钮样式 */
button {
  font-family: inherit;
}
</style>
