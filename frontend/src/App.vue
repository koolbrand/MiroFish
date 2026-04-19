<template>
  <router-view />
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { refreshAuth } from './composables/useAuth'

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
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* 全局按钮样式 */
button {
  font-family: inherit;
}
</style>
