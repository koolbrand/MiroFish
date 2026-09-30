<template>
  <!-- Prueba tangible del resultado: un informe de predicción de EJEMPLO (escenario y datos inventados,
       rotulado como tal). Reproduce la estructura de los informes reales: veredicto, reacciones por grupo y
       una entrevista a una persona simulada. -->
  <article v-reveal class="report" :aria-label="$t('home.reportKicker')">
    <header class="report-head">
      <span class="report-kicker">{{ $t('home.reportKicker') }}</span>
      <span class="report-tag">{{ $t('home.reportExampleTag') }}</span>
    </header>
    <h3 class="report-title">{{ $t('home.reportTitle') }}</h3>

    <section class="report-block">
      <span class="report-label">{{ $t('home.reportVerdictLabel') }}</span>
      <p class="report-verdict">{{ $t('home.reportVerdict') }}</p>
    </section>

    <section class="report-block">
      <span class="report-label">{{ $t('home.chartKicker') }} · {{ $t('home.chartTitle') }}</span>
      <OpinionChart flat />
    </section>

    <section class="report-block">
      <span class="report-label">{{ $t('home.reportGroupsLabel') }}</span>
      <ul class="groups">
        <li v-for="(g, i) in GROUPS" :key="g.key" :style="{ '--i': i }">
          <span class="group-name">{{ $t(`home.reportGroup${g.key}`) }}</span>
          <span class="group-bar" role="img" :aria-label="`${$t('home.crowdFor')} ${g.f} %, ${$t('home.crowdUndecided')} ${g.u} %, ${$t('home.crowdAgainst')} ${g.a} %`">
            <span class="seg is-favor" :style="{ '--w': `${g.f}%` }"></span>
            <span class="seg is-undecided" :style="{ '--w': `${g.u}%` }"></span>
            <span class="seg is-against" :style="{ '--w': `${g.a}%` }"></span>
          </span>
          <span class="group-num">{{ g.f }} %</span>
        </li>
      </ul>
    </section>

    <section class="report-quote">
      <BiankaAvatar :look="{ ears: 'flop', head: 'beanie', body: 'coffee' }" bucket="undecided" :pixel="2" />
      <div>
        <p class="quote-text">«{{ $t('home.reportQuote') }}»</p>
        <span class="quote-by">{{ $t('home.reportQuoteBy') }}</span>
      </div>
    </section>

    <footer class="report-note">{{ $t('home.reportNote') }}</footer>
  </article>
</template>

<script setup>
import OpinionChart from './OpinionChart.vue'
import BiankaAvatar from './BiankaAvatar.vue'
import { vReveal } from '../composables/useReveal'

// Datos inventados (favor / indecisos / en contra, en %)
const GROUPS = [
  { key: 'Regular', f: 58, u: 27, a: 15 },
  { key: 'Casual', f: 34, u: 41, a: 25 },
  { key: 'Clubs', f: 22, u: 38, a: 40 },
]
</script>

<style scoped>
.report {
  position: relative;
  box-sizing: border-box;
  padding: clamp(20px, 3vw, 30px);
  background: var(--kb-surface);
  border: 2px solid var(--ink-950);
  border-radius: 14px;
  box-shadow: 8px 8px 0 var(--ink-950);
}
/* segundo informe asomando por detrás: hay más donde ése salió */
.report::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--lime-500);
  border: 2px solid var(--ink-950);
  border-radius: 14px;
  transform: rotate(-2deg) translate(-6px, 4px);
}
.report-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.report-kicker { font-family: var(--kb-font-mono); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--kb-muted); }
.report-tag {
  padding: 3px 8px;
  border: 1.5px solid var(--ink-950);
  border-radius: 999px;
  background: var(--lime-500);
  font-family: var(--kb-font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.report-title { margin: 12px 0 0; font-size: clamp(1.15rem, 1.8vw, 1.45rem); font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; text-wrap: balance; }
.report-block { margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--kb-line); }
.report-label { display: block; margin-bottom: 8px; font-family: var(--kb-font-mono); font-size: 10.5px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--kb-accent-text); }
.report-verdict { margin: 0; font-size: 0.98rem; line-height: 1.5; color: var(--kb-text); text-wrap: pretty; }

.groups { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.groups li { display: grid; grid-template-columns: minmax(96px, 150px) 1fr 44px; align-items: center; gap: 12px; font-size: 0.86rem; }
.group-name { color: var(--kb-text-2); }
.group-bar { display: flex; height: 12px; overflow: hidden; border: 1.5px solid var(--ink-950); background: var(--kb-surface); }
.seg { display: block; width: 0; transition: width 0.9s cubic-bezier(0.65, 0, 0.35, 1); transition-delay: calc(var(--i, 0) * 0.15s + 0.4s); }
.seg.is-favor { background: var(--lime-500); }
.seg.is-undecided { background: var(--kb-surface); }
.seg.is-against { background: #2A2A2A; }
.report.is-in .seg { width: var(--w); }
.group-num { font-family: var(--kb-font-mono); font-size: 12px; font-weight: 700; text-align: end; font-variant-numeric: tabular-nums; }

.report-quote { display: flex; gap: 14px; align-items: flex-end; margin-top: 18px; padding: 14px 16px; border: 1.5px solid var(--ink-950); border-radius: 10px; background: var(--kb-surface-2); }
.quote-text { margin: 0 0 6px; font-size: 0.95rem; font-weight: 600; line-height: 1.4; text-wrap: pretty; }
.quote-by { font-family: var(--kb-font-mono); font-size: 10.5px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--kb-muted); }
.report-note { margin-top: 14px; font-size: 0.8rem; line-height: 1.4; color: var(--kb-muted); }

@media (max-width: 560px) {
  .report-quote { align-items: flex-start; }
  .groups li { grid-template-columns: 1fr 44px; }
  .group-bar { grid-column: 1 / -1; grid-row: 2; }
  .group-num { grid-row: 1; grid-column: 2; }
}
@media (prefers-reduced-motion: reduce) { .seg { transition: none; } }
</style>
