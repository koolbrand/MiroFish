<template>
  <Transition name="conn-fade">
    <div v-if="offline" class="conn-banner" role="status" aria-live="polite">
      <span class="conn-dot" aria-hidden="true"></span>
      {{ $t('errors.offlineBanner') }}
    </div>
  </Transition>
</template>

<script setup>
import { offline } from '../lib/connection'
</script>

<style scoped>
.conn-banner {
  position: fixed;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  z-index: 9000;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: calc(100vw - 32px);
  padding: 10px 16px;
  border: 1px solid var(--ink-950);
  border-radius: 10px;
  background: var(--kb-surface, #fff);
  color: var(--kb-text, #111);
  font: 600 0.88rem/1.35 var(--kb-font-sans);
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.12);
}
.conn-dot {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--lime-500, #cce673);
  border: 2px solid var(--ink-950);
  animation: conn-pulse 1.4s ease-in-out infinite;
}
@keyframes conn-pulse { 50% { opacity: 0.35; } }
.conn-fade-enter-active, .conn-fade-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.conn-fade-enter-from, .conn-fade-leave-to { opacity: 0; transform: translate(-50%, 8px); }
@media (prefers-reduced-motion: reduce) {
  .conn-dot { animation: none; }
  .conn-fade-enter-active, .conn-fade-leave-active { transition: none; }
}
</style>
