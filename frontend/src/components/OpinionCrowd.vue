<template>
  <!-- La multitud opinando: 120 Biankas (el tope del rango que la app publica) leen una propuesta de EJEMPLO y van cambiando de
       opinión ronda a ronda. A la derecha, lo que van diciendo: habla quien acaba de cambiar de idea y se ilumina en la multitud.
       Todo es ilustrativo (personas y frases inventadas) y está rotulado como tal. Con «reducir movimiento» se ve el estado final, quieto. -->
  <article ref="root" class="oc" :aria-label="$t('home.multLabel')">
    <header class="oc-head">
      <div class="oc-brief">
        <span class="oc-label">{{ $t('home.multBriefLabel') }}</span>
        <strong class="oc-brief-text">{{ $t('home.multBrief') }}</strong>
      </div>
      <div class="oc-count">
        <span class="oc-count-num">{{ N }}</span>
        <span class="oc-count-unit">{{ $t('home.multCount') }}</span>
      </div>
      <div class="oc-round">
        <span class="oc-label">{{ $t('home.crowdRound') }} <b>{{ String(round).padStart(2, '0') }}/{{ ROUNDS }}</b></span>
        <span class="oc-event"><span class="oc-label">{{ $t('home.crowdEventTag') }}</span> {{ $t(`home.crowdEvent${round}`) }}</span>
      </div>
    </header>

    <div class="oc-stats">
      <div class="oc-bar" aria-hidden="true">
        <span class="seg is-favor" :style="{ width: `${(stats.favor / N) * 100}%` }"></span>
        <span class="seg is-undecided" :style="{ width: `${(stats.undecided / N) * 100}%` }"></span>
        <span class="seg is-against" :style="{ width: `${(stats.against / N) * 100}%` }"></span>
      </div>
      <div class="oc-legend">
        <span><i class="swatch is-favor"></i>{{ $t('home.crowdFor') }} <b>{{ stats.favor }}</b></span>
        <span><i class="swatch is-undecided"></i>{{ $t('home.crowdUndecided') }} <b>{{ stats.undecided }}</b></span>
        <span><i class="swatch is-against"></i>{{ $t('home.crowdAgainst') }} <b>{{ stats.against }}</b></span>
      </div>
    </div>

    <div class="oc-body">
      <div class="oc-stage"><canvas ref="canvas" aria-hidden="true"></canvas></div>
      <div class="oc-feed">
        <span class="oc-label">{{ $t('home.multFeed') }}</span>
        <TransitionGroup name="oc-msg" tag="ul" class="oc-list">
          <li v-for="m in feed" :key="m.id" class="oc-msg" :class="`is-${m.bucket}`">
            <BiankaAvatar :look="m.look" :bucket="m.bucket" :pixel="2" />
            <div class="oc-msg-text">
              <span class="oc-who">
                <template v-if="m.from"><i class="swatch" :class="`is-${m.from}`"></i><span aria-hidden="true">→</span></template>
                <i class="swatch" :class="`is-${m.bucket}`"></i>{{ m.who }} · {{ m.tag }}
              </span>
              <p>{{ m.text }}</p>
            </div>
          </li>
        </TransitionGroup>
      </div>
    </div>

    <footer class="oc-note">{{ $t('home.multNote') }}</footer>
  </article>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import BiankaAvatar from './BiankaAvatar.vue'
import { makeLook, drawBianka, spriteFor } from '../lib/biankaSprite'

const { t } = useI18n()

const N = 120                 // el tope del rango publicado («20–120 personas»)
const ROUNDS = 10
const ROUND_SECS = 2.6
const HOLD_SECS = 5
// Cómo acaba el ejemplo: el MISMO final que el gráfico del informe de ejemplo (OpinionChart: 38 % a favor, 41 % dudando, 21 % en contra)
// — interesa, pero el precio genera dudas —, de modo que las dos piezas de la página cuentan la misma historia.
const FINAL = { favor: 46, undecided: 49, against: 25 }
const QUOTES = {
  favor: ['home.multQuoteF1', 'home.multQuoteF2', 'home.multQuoteF3', 'home.multQuoteF4'],
  undecided: ['home.multQuoteU1', 'home.multQuoteU2', 'home.multQuoteU3', 'home.multQuoteU4'],
  against: ['home.multQuoteA1', 'home.multQuoteA2', 'home.multQuoteA3', 'home.multQuoteA4'],
}
const TAG = { favor: 'home.crowdFor', undecided: 'home.crowdTagUndecided', against: 'home.crowdAgainst' }

const root = ref(null)
const canvas = ref(null)
const round = ref(ROUNDS)
const stats = reactive({ favor: FINAL.favor, undecided: FINAL.undecided, against: FINAL.against })
const feed = ref([])

const reduced = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
let ctx = null, W = 0, H = 0, dpr = 1, P = 2
let agents = []
let tNow = 0, last = 0, raf = null, running = false, visible = false
let speakClock = 1.2, msgSeq = 0
const recent = []
let io = null, ro = null

const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]] } return a }
const pickOf = (arr) => arr[Math.floor(Math.random() * arr.length)]

const seed = () => {
  const finals = shuffle([
    ...Array(FINAL.favor).fill('favor'), ...Array(FINAL.undecided).fill('undecided'), ...Array(FINAL.against).fill('against'),
  ])
  let prevKey = ''
  agents = finals.map((fin, i) => {
    // quien acaba a favor o en contra casi siempre parte dudando (unas pocas ya traen opinión); unas cuantas de las que
    // acaban dudando partían con una opinión y la moderan
    const start = fin === 'undecided' ? (Math.random() < 0.15 ? pickOf(['favor', 'against']) : 'undecided') : (Math.random() < 0.22 ? fin : 'undecided')
    let look = makeLook()
    for (let k = 0; k < 6 && look.key === prevKey; k++) look = makeLook()
    prevKey = look.key
    return {
      look: { ...look, pose: null }, mirror: i % 2 === 1, start, final: fin,
      flipAt: start === fin ? 0 : 2 + Math.floor(Math.random() ** 0.85 * (ROUNDS - 1)),   // ronda en la que cambia de idea (2–10)
      phase: Math.random() * 3, blink: Math.random() * 4, hopAt: -10, speakUntil: -1, spokeIn: 0,
      x: 0, y: 0,
    }
  })
}

const bucketAt = (a, r) => (a.flipAt && r >= a.flipAt ? a.final : a.start)
const recount = () => {
  const c = { favor: 0, undecided: 0, against: 0 }
  for (const a of agents) c[bucketAt(a, round.value)]++
  stats.favor = c.favor; stats.undecided = c.undecided; stats.against = c.against
}

// ── Colocación: cuadrícula escalonada, del ancho disponible ─────────────────────────────────────────────
const layout = () => {
  const el = canvas.value
  if (!el) return
  const w = el.parentElement.clientWidth
  if (!w) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  P = w < 440 ? 1 : 2     // en un móvil, píxel de 1 (si no, la multitud ocuparía tres pantallas)
  const tileW = 21 * P, tileH = 22 * P
  const cols = Math.max(5, Math.floor((w - tileW / 2 - 8 * P) / tileW))   // 4 celdas de margen a cada lado: el contorno nunca toca el marco
  const rows = Math.ceil(N / cols)
  const h = 9 * P + (rows - 1) * tileH + 31 * P                         // arriba 9 celdas de aire (el sombrero de mago sobresale 6 y salta 3)
  W = w; H = h
  el.width = Math.round(W * dpr); el.height = Math.round(H * dpr)
  el.style.width = `${W}px`; el.style.height = `${H}px`
  ctx = el.getContext('2d')
  const x0 = (W - (cols * tileW + tileW / 2)) / 2 - 3 * P
  agents.forEach((a, i) => {
    const r = Math.floor(i / cols), c = i % cols
    a.x = Math.round(x0 + c * tileW + (r % 2 ? tileW / 2 : 0))
    a.y = Math.round(9 * P + r * tileH)
  })
  paint()
}

// ── Dibujo ─────────────────────────────────────────────────────────────────────────────────────────────
const paint = () => {
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, W, H)
  const r = round.value
  const speakers = []
  for (const a of agents) {
    const speaking = tNow < a.speakUntil
    if (speaking) { speakers.push(a); continue }
    drawOne(a, r, false)
  }
  for (const a of speakers) drawOne(a, r, true)     // quien habla, al frente y con sombra dura
}
const drawOne = (a, r, speaking) => {
  const hopT = tNow - a.hopAt
  const hop = hopT >= 0 && hopT < 0.34 ? Math.round(Math.sin((Math.PI * hopT) / 0.34) * 3) * P : 0
  const bob = reduced ? 0 : (((tNow + a.phase) / 1.6) % 1) < 0.5 ? 0 : P
  drawBianka(ctx, {
    x: a.x, y: a.y + bob - hop, P, look: a.look, bucket: bucketAt(a, r), mirror: a.mirror, now: tNow, lift: speaking,
    gaze: [0, 0], blink: !reduced && ((tNow + a.blink) % 3.8) > 3.65, happy: hopT >= 0 && hopT < 0.6, talking: speaking,
  })
}

// ── Lo que van diciendo ────────────────────────────────────────────────────────────────────────────────
const say = (a, r) => {
  const bucket = bucketAt(a, r)
  // si acaba de cambiar de idea, se ve: de qué opinión venía y que lo dice
  const from = a.flipAt === r && a.start !== a.final ? a.start : null
  // nunca la misma frase dos veces a la vez en pantalla; y, si se puede, tampoco una de las últimas
  const visibleNow = new Set(feed.value.map(m => m.key))
  const fresh = QUOTES[bucket].filter(k => !visibleNow.has(k))
  const pool = fresh.filter(k => !recent.includes(k))
  const key = pickOf(pool.length ? pool : fresh.length ? fresh : QUOTES[bucket])
  recent.push(key); if (recent.length > 6) recent.shift()
  a.spokeIn = r
  a.speakUntil = tNow + 1.7
  a.hopAt = tNow
  feed.value = [{ id: ++msgSeq, key, look: a.look, bucket, from, who: t(`home.biankas.${a.look.persona}`), tag: from ? t('home.multChanged') : t(TAG[bucket]), text: t(key) }, ...feed.value].slice(0, 4)
}
const primeFeed = () => { const a = pickOf(agents); say(a, round.value); say(pickOf(agents.filter(x => x !== a)), round.value) }
const speakNext = () => {
  const r = round.value
  // primero quien acaba de cambiar de idea en esta ronda (y lo cuenta); si no, cualquiera
  const fresh = agents.filter(a => a.flipAt === r && a.spokeIn !== r)
  say(pickOf(fresh.length ? fresh : agents), r)
}

// ── Reloj ───────────────────────────────────────────────────────────────────────────────────────────────
const setRound = (r) => {
  const prev = round.value
  round.value = r
  recount()
  if (r !== prev && r > 1) for (const a of agents) if (a.flipAt === r) a.hopAt = tNow + Math.random() * 0.5   // los que cambian de idea, un saltito
}
const tick = (ts) => {
  raf = null
  if (!running) return
  const dt = Math.min(0.05, (ts - last) / 1000 || 0.016); last = ts
  tNow += dt
  const span = ROUNDS * ROUND_SECS + HOLD_SECS
  if (tNow >= span) { tNow = 0; feed.value = []; recent.length = 0; for (const a of agents) a.spokeIn = 0; setRound(1); primeFeed(); speakClock = 1.2 }
  const r = Math.min(ROUNDS, Math.floor(tNow / ROUND_SECS) + 1)
  if (r !== round.value) setRound(r)
  speakClock -= dt
  if (speakClock <= 0) { speakNext(); speakClock = 1.35 + Math.random() * 0.5 }
  paint()
  raf = requestAnimationFrame(tick)
}
const start = () => { if (running || reduced || !visible || document.hidden) return; running = true; last = performance.now(); raf = requestAnimationFrame(tick) }
const stop = () => { running = false; if (raf) cancelAnimationFrame(raf); raf = null }
const onVis = () => (document.hidden ? stop() : start())

// Con «reducir movimiento»: el estado final (ronda 10) y cuatro voces fijas, sin bucle.
const settle = () => {
  round.value = ROUNDS
  recount()
  const by = (b) => agents.find(a => bucketAt(a, ROUNDS) === b && !a.look.head?.hideEars) || agents.find(a => bucketAt(a, ROUNDS) === b)
  const pick4 = [['favor', 0], ['undecided', 0], ['against', 0], ['favor', 1]]
  const used = new Set()
  feed.value = pick4.map(([b, q], i) => {
    const a = agents.find(x => bucketAt(x, ROUNDS) === b && !used.has(x)) || by(b)
    used.add(a)
    return { id: ++msgSeq, look: a.look, bucket: b, who: t(`home.biankas.${a.look.persona}`), tag: t(TAG[b]), text: t(QUOTES[b][q]) }
  })
}

// Dibujar cada Bianka en sus tres opiniones cuesta un poco la primera vez: se hace en ratos libres, antes de que la tarjeta entre en pantalla.
const prewarm = () => {
  const idle = window.requestIdleCallback || ((f) => setTimeout(() => f({ timeRemaining: () => 8 }), 60))
  let i = 0
  const step = (dl) => {
    let n = 0
    while (i < agents.length && n < 8 && (!dl || dl.timeRemaining() > 4)) { for (const b of ['favor', 'undecided', 'against']) spriteFor(agents[i].look, b); i++; n++ }
    if (i < agents.length) idle(step)
  }
  idle(step)
}

onMounted(() => {
  seed()
  prewarm()
  if (reduced) settle(); else { round.value = 1; recount(); primeFeed() }
  layout()
  ro = new ResizeObserver(() => layout()); ro.observe(canvas.value.parentElement)
  io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; visible ? start() : stop() }, { threshold: 0.2 })
  io.observe(root.value)
  document.addEventListener('visibilitychange', onVis)
})
onUnmounted(() => { stop(); ro?.disconnect(); io?.disconnect(); document.removeEventListener('visibilitychange', onVis) })
</script>

<style scoped>
.oc {
  background: var(--kb-surface);
  border: 2px solid var(--ink-950);
  border-radius: 14px;
  box-shadow: 4px 4px 0 var(--ink-950);
  padding: clamp(18px, 2.4vw, 28px);
  display: grid;
  gap: 18px;
  min-width: 0;
}
.oc-label {
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--kb-muted);
}
.oc-label b { color: var(--kb-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.oc-head {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) auto minmax(0, 1fr);
  gap: 12px clamp(20px, 3vw, 44px);
  align-items: end;
}
.oc-brief { display: grid; gap: 6px; min-width: 0; }
.oc-brief-text { font-size: clamp(1.05rem, 1.6vw, 1.3rem); font-weight: 800; letter-spacing: -0.02em; line-height: 1.15; text-wrap: balance; }
.oc-count { display: flex; align-items: baseline; gap: 10px; }
.oc-count-num { font-size: clamp(2.6rem, 4.4vw, 3.8rem); font-weight: 800; line-height: 0.9; letter-spacing: -0.04em; font-variant-numeric: tabular-nums; }
.oc-count-unit { font-family: var(--kb-font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--kb-text-2); max-width: 24ch; line-height: 1.35; text-wrap: balance; word-break: keep-all; }
.oc-round { display: grid; gap: 4px; justify-items: end; text-align: end; min-width: 0; }
.oc-event { font-size: 0.95rem; font-weight: 700; letter-spacing: -0.01em; color: var(--kb-text); }
.oc-event .oc-label { font-weight: 400; margin-inline-end: 6px; }

.oc-stats { display: grid; gap: 8px; }
.oc-bar { display: flex; height: 14px; border: 2px solid var(--ink-950); background: #fff; overflow: hidden; }
.oc-bar .seg { transition: width 0.6s steps(6, end); }
.oc-bar .is-favor { background: var(--lime-500); }
.oc-bar .is-undecided { background: #fff; }
.oc-bar .is-against { background: #2A2A2A; }
.oc-legend { display: flex; flex-wrap: wrap; gap: 4px 22px; font-family: var(--kb-font-mono); font-size: 13px; color: var(--kb-text-2); }
.oc-legend span { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.oc-legend b { font-weight: 700; color: var(--kb-text); font-variant-numeric: tabular-nums; }
.swatch { display: inline-block; width: 12px; height: 12px; border: 2px solid var(--ink-950); flex: none; box-sizing: border-box; }
.swatch.is-favor { background: var(--lime-500); }
.swatch.is-undecided { background: #fff; }
.swatch.is-against { background: #2A2A2A; }

.oc-body { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); gap: clamp(18px, 2.4vw, 32px); align-items: start; }
.oc-stage { min-width: 0; background: var(--cream-100); border: 2px solid var(--ink-950); overflow: hidden; line-height: 0; }
.oc-stage canvas { display: block; image-rendering: pixelated; }
.oc-feed { display: grid; gap: 10px; min-width: 0; align-content: start; }
.oc-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; position: relative; }
.oc-msg {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  padding: 10px 14px 10px 10px;
  background: #fff;
  border: 2px solid var(--ink-950);
  box-shadow: 3px 3px 0 var(--ink-950);
}
.oc-msg-text { display: grid; gap: 3px; min-width: 0; }
.oc-who { display: inline-flex; align-items: center; gap: 7px; font-family: var(--kb-font-mono); font-size: 10.5px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--kb-muted); min-width: 0; }
.oc-who .swatch { width: 10px; height: 10px; }
.oc-msg p { margin: 0; font-size: 0.98rem; line-height: 1.35; color: var(--kb-text); text-wrap: pretty; }
.oc-note { font-size: 0.85rem; line-height: 1.45; color: var(--kb-text-2); padding-top: 14px; border-top: 1px dashed rgba(17, 17, 17, 0.25); max-width: 72ch; text-wrap: pretty; }

/* entra de arriba con el ritmo del píxel (escalonado); el resto baja un hueco */
.oc-msg-enter-active { transition: opacity 0.35s steps(4, end), transform 0.35s steps(4, end); }
.oc-msg-leave-active { display: none; }   /* la que sale desaparece sin más: nada gris que se pise con la que entra */
.oc-msg-move { transition: transform 0.35s steps(4, end); }
.oc-msg-enter-from { opacity: 0; transform: translateY(-14px); }

@media (max-width: 900px) {
  .oc-head { grid-template-columns: minmax(0, 1fr) auto; }
  .oc-round { grid-column: 1 / -1; justify-items: start; text-align: start; }
  .oc-body { grid-template-columns: minmax(0, 1fr); }
  .oc-msg:nth-child(n + 4) { display: none; }
}
@media (max-width: 560px) {
  /* móvil: cada cosa en su fila (propuesta, cifra, ronda) para que ningún rótulo se parta en tres líneas */
  .oc-head { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .oc-round { grid-column: auto; }
}
@media (max-width: 480px) {
  .oc-legend { gap: 4px 14px; font-size: 12px; }
  .oc-msg p { font-size: 0.92rem; }
}
@media (prefers-reduced-motion: reduce) {
  .oc-bar .seg, .oc-msg-enter-active, .oc-msg-move { transition: none; }
}
</style>
