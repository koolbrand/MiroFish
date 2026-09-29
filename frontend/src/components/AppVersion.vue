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
  font-family: var(--kb-font-sans);
  font-size: 0.65rem;
  color: var(--kb-text-2);
  letter-spacing: 0.05em;
  cursor: default;
  user-select: none;
  transition: color 0.2s;
}

.app-version-badge:hover {
  color: var(--kb-subtle);
}

.build-dot {
  opacity: 0.5;
}
</style>
