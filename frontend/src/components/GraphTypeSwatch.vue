<template>
  <!-- Muestra de un tipo de entidad: la misma forma y el mismo tono que en el grafo, sobre una tesela de tinta
       (como se ven en el escenario oscuro). Decorativa: el nombre del tipo va siempre al lado. -->
  <span class="gts" aria-hidden="true">
    <svg viewBox="-1.65 -1.65 3.3 3.3" width="12" height="12" focusable="false">
      <path :d="d" :style="pathStyle" />
    </svg>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { SHAPES } from '../lib/graphRender'

const props = defineProps({
  // { shape, fill, stroke? } con nombres de token (--lime-500…), el mismo objeto que usa el canvas
  typeStyle: { type: Object, required: true },
})

const d = computed(() => SHAPES[props.typeStyle?.shape] || SHAPES.circle)
const pathStyle = computed(() => {
  const s = props.typeStyle || {}
  return {
    fill: `var(${s.fill || '--gray-600'})`,
    stroke: s.stroke ? `var(${s.stroke})` : 'none',
    strokeWidth: s.stroke ? 0.36 : 0,
  }
})
</script>

<style scoped>
.gts {
  display: inline-grid;
  place-items: center;
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  background: var(--ink-950);
}
.gts svg { display: block; overflow: visible; }
</style>
