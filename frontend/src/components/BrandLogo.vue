<template>
  <svg
    class="brand-logo"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 196 46"
    :aria-label="ariaLabel"
    role="img"
  >
    <!-- Logotipo tipográfico: JetBrains Mono (ya cargada en index.html).
         textLength fija el ancho aunque la fuente tarde en cargar. -->
    <text
      x="0"
      y="39"
      textLength="196"
      lengthAdjust="spacingAndGlyphs"
      font-family="'JetBrains Mono', ui-monospace, monospace"
      font-weight="700"
      font-size="44"
    >SIMULOO</text>
  </svg>
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
  height: 1em;
  width: auto;
  display: inline-block;
  vertical-align: middle;
  fill: currentColor;
}
</style>
