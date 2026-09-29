<template>
  <!-- Logotipo Simuloo: «simul» en Inter Tight 800 y la doble «o» convertida en
       dos ojos dentro del bloque lima rotado (firma Koolbrand).
       Simula porque observa. -->
  <span class="brand-logo" role="img" :aria-label="ariaLabel">
    <span class="brand-simul" aria-hidden="true">simul</span><span class="brand-eyes" aria-hidden="true">
      <svg viewBox="0 0 124 64" class="eyes-svg" focusable="false">
        <!-- anillos = las dos «o»; pupilas desplazadas: mira de lado -->
        <circle cx="31" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13" />
        <circle cx="93" cy="34" r="22" fill="none" stroke="currentColor" stroke-width="13" />
        <circle class="pupil" cx="37" cy="36" r="7.5" fill="currentColor" />
        <circle class="pupil" cx="99" cy="36" r="7.5" fill="currentColor" />
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
/* Al pasar por encima, los ojos miran al otro lado */
.pupil { transition: transform 0.35s ease; }
.brand-logo:hover .pupil { transform: translateX(-11px); }
@media (prefers-reduced-motion: reduce) {
  .pupil { transition: none; }
}
</style>
