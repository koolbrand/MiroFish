<template>
  <!-- Logotipo Simuloo: «simul» en Inter Tight 800 y la doble «o» dentro del
       bloque lima rotado (firma Koolbrand). -->
  <span class="brand-logo" role="img" :aria-label="ariaLabel">
    <span class="brand-simul" aria-hidden="true">simul</span><span class="brand-eyes" aria-hidden="true">
      <svg viewBox="0 0 124 64" class="eyes-svg" focusable="false">
        <!-- las dos «o», dibujadas para que no dependan de la carga de la fuente -->
        <circle cx="31" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13" />
        <circle cx="93" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13" />
      </svg>
    </span>
  </span>
</template>

<script setup>
defineProps({
  ariaLabel: {
    type: String,
    default: 'Simuloo'
  }
})
</script>

<style scoped>
.brand-logo {
  display: inline-flex;
  align-items: baseline;
  font-family: var(--kb-font-sans);
  font-weight: 800;
  font-size: 1em;
  line-height: 1;
  letter-spacing: -0.04em;
  white-space: nowrap;
  vertical-align: middle;
  cursor: inherit;
}
.brand-eyes {
  display: inline-flex;
  align-items: flex-end;
  background: var(--kb-accent-solid);
  color: var(--kb-accent-on);
  padding: 0.1em 0.1em 0.07em;
  margin-left: 0.05em;
  border-radius: 0.14em;
  transform: rotate(-2deg);
  align-self: center;
}
/* Alto de la «o» de Inter Tight 800 (≈ altura de x) */
.eyes-svg {
  height: 0.58em;
  width: auto;
  display: block;
  overflow: visible;
}
</style>
