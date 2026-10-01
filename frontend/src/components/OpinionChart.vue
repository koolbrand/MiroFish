<template>
  <!-- Gráfico de ejemplo: reparto de la opinión ronda a ronda (100 % apilado).
       Se dibuja de izquierda a derecha al entrar en pantalla. -->
  <figure v-reveal class="opinion-chart" :class="{ flat }">
    <figcaption v-if="!flat" class="chart-caption">
      <span class="chart-kicker">{{ $t('home.chartKicker') }}</span>
      <span class="chart-title">{{ $t('home.chartTitle') }}</span>
    </figcaption>

    <div class="chart-body">
      <div class="chart-plot">
        <svg class="chart-svg" :viewBox="`0 0 ${VW} ${VH}`" preserveAspectRatio="none" role="img" :aria-label="ariaLabel">
          <path :d="areaAgainst" class="area is-against" />
          <path :d="areaUndecided" class="area is-undecided" />
          <path :d="areaFavor" class="area is-favor" />
          <line v-for="g in [25, 50, 75]" :key="g" x1="0" :x2="VW" :y1="y(g)" :y2="y(g)" class="grid" />
          <path :d="lineFavor" class="edge is-favor" pathLength="1" />
          <path :d="lineAgainst" class="edge is-against" pathLength="1" />
        </svg>
        <ul class="chart-ends">
          <li v-for="end in ends" :key="end.key" :class="`is-${end.key}`" :style="{ top: `${end.top}%` }">
            <b>{{ end.value }} %</b> {{ end.label }}
          </li>
        </ul>
      </div>
      <div class="chart-axis" aria-hidden="true">
        <span v-for="r in 11" :key="r" :class="{ minor: (r - 1) % 5 !== 0 }">{{ $t('home.chartRoundShort') }}{{ r - 1 }}</span>
      </div>
    </div>
  </figure>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { vReveal } from '../composables/useReveal'

// flat: sin tarjeta ni título propios (va dentro de otro artefacto, p. ej. el informe de ejemplo)
// favor / against: % a favor y en contra en R0…R10 (el resto son indecisos); por defecto, el ejemplo del pádel
const props = defineProps({
  flat: { type: Boolean, default: false },
  favor: { type: Array, default: () => [8, 14, 12, 19, 17, 26, 24, 31, 29, 35, 38] },
  against: { type: Array, default: () => [5, 4, 11, 10, 17, 14, 19, 16, 20, 19, 21] },
})

const { t } = useI18n()

const VW = 600
const VH = 280
// Serie ilustrativa (rotulada como ejemplo en la interfaz).
const FAVOR = computed(() => props.favor)
const AGAINST = computed(() => props.against)
const UNDECIDED = computed(() => FAVOR.value.map((f, i) => 100 - f - AGAINST.value[i]))

const x = (i) => (i / (FAVOR.value.length - 1)) * VW
const y = (v) => VH * (1 - v / 100)
const pts = (vals) => vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`)

const top1 = computed(() => FAVOR.value)
const top2 = computed(() => FAVOR.value.map((f, i) => f + UNDECIDED.value[i]))

const areaFavor = computed(() => `M0,${VH} L${pts(top1.value).join(' L')} L${VW},${VH} Z`)
const areaUndecided = computed(() => `M${pts(top1.value).join(' L')} L${pts(top2.value).reverse().join(' L')} Z`)
const areaAgainst = computed(() => `M${pts(top2.value).join(' L')} L${VW},0 L0,0 Z`)
const lineFavor = computed(() => `M${pts(top1.value).join(' L')}`)
const lineAgainst = computed(() => `M${pts(top2.value).join(' L')}`)

const last = computed(() => FAVOR.value.length - 1)
const ends = computed(() => {
  const l = last.value
  return [
    { key: 'against', value: AGAINST.value[l], label: t('home.crowdAgainst'), top: 100 - (top2.value[l] + AGAINST.value[l] / 2) },
    { key: 'undecided', value: UNDECIDED.value[l], label: t('home.crowdUndecided'), top: 100 - (top1.value[l] + UNDECIDED.value[l] / 2) },
    { key: 'favor', value: FAVOR.value[l], label: t('home.crowdFor'), top: 100 - FAVOR.value[l] / 2 },
  ]
})

const ariaLabel = computed(() =>
  t('home.chartAria', { favor: FAVOR.value[last.value], undecided: UNDECIDED.value[last.value], against: AGAINST.value[last.value] })
)
</script>

<style scoped>
.opinion-chart.flat { border: 0; border-radius: 0; padding: 0; background: transparent; }
.opinion-chart.flat .chart-body { padding-inline-end: 96px; }
.opinion-chart.flat .chart-svg { height: clamp(120px, 15vw, 160px); }
.opinion-chart {
  margin: 0;
  background: var(--kb-surface);
  border: 1px solid var(--kb-line);
  border-radius: 16px;
  padding: clamp(20px, 3vw, 32px);
}
.chart-caption { display: grid; gap: 6px; margin-bottom: 24px; }
.chart-kicker {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--kb-accent-text);
}
.chart-title { font-size: 1.1rem; font-weight: 700; line-height: 1.3; text-wrap: balance; }

.chart-body { padding-inline-end: 118px; }
.chart-plot { position: relative; }
.chart-svg {
  display: block;
  width: 100%;
  height: clamp(180px, 24vw, 260px);
  border-radius: 8px;
  /* revelado de izquierda a derecha */
  clip-path: inset(0 100% 0 0);
  transition: clip-path 1.2s cubic-bezier(0.65, 0, 0.35, 1);
}
.area.is-favor { fill: var(--lime-500); }
.area.is-undecided { fill: var(--gray-100); }
.area.is-against { fill: var(--gray-600); }
.grid { stroke: rgba(17, 17, 17, 0.08); stroke-width: 1; vector-effect: non-scaling-stroke; }
.edge {
  fill: none;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  transition: stroke-dashoffset 1.2s cubic-bezier(0.65, 0, 0.35, 1);
}
.edge.is-favor { stroke: var(--lime-800); }
.edge.is-against { stroke: var(--kb-text); stroke-width: 1.5; }

.chart-ends {
  list-style: none;
  margin: 0;
  padding: 0;
  position: absolute;
  inset-block: 0;
  inset-inline-start: calc(100% + 14px);
  width: 104px;
}
.chart-ends li {
  position: absolute;
  translate: 0 -50%;
  font-size: 12px;
  line-height: 1.2;
  color: var(--kb-muted);
  opacity: 0;
  transition: opacity 0.5s ease 1.0s;
  white-space: nowrap;
}
.chart-ends b {
  display: block;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--kb-text);
  font-variant-numeric: tabular-nums;
}
.chart-ends .is-favor b { color: var(--lime-800); }

.chart-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  color: var(--kb-subtle);
  font-variant-numeric: tabular-nums;
}

.opinion-chart.is-in .chart-svg { clip-path: inset(0 0 0 0); }
.opinion-chart.is-in .edge { stroke-dashoffset: 0; }
.opinion-chart.is-in .chart-ends li { opacity: 1; }

@media (max-width: 560px) {
  /* el eje va justo bajo el gráfico y la leyenda debajo del eje */
  .chart-body, .opinion-chart.flat .chart-body { display: flex; flex-direction: column; padding-inline-end: 0; }
  .chart-plot { display: contents; }
  .chart-svg { order: 1; }
  .chart-axis { order: 2; }
  .chart-ends { order: 3; position: static; width: auto; display: flex; gap: 20px; margin-top: 16px; }
  .chart-ends li { position: static; translate: none; }
  .chart-axis .minor { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .chart-svg, .edge, .chart-ends li { transition: none; }
}
</style>
