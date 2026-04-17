<template>
  <span class="app-version-badge" :title="`Build: ${buildDate}`">
    {{ version }} <span class="build-dot">·</span> {{ buildDate }}
  </span>
</template>

<script setup>
const version = __APP_VERSION__
const buildDate = __BUILD_DATE__
</script>

<style scoped>
.app-version-badge {
  font-family: 'Courier New', monospace;
  font-size: 0.65rem;
  color: #444;
  letter-spacing: 0.05em;
  cursor: default;
  user-select: none;
  transition: color 0.2s;
}

.app-version-badge:hover {
  color: #888;
}

.build-dot {
  opacity: 0.5;
}
</style>
