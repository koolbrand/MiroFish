<template>
  <!-- Muro de Biankas en pixel art: cada una es una persona simulada que opina
       (lima a favor, blanca indecisa, tinta en contra), conversa con sus
       vecinas y cambia de idea. Decorativo: el contenido no depende de él. -->
  <div ref="root" class="bianka-crowd" aria-hidden="true">
    <canvas
      ref="canvas"
      class="crowd-canvas"
      :class="{ 'is-hovering': hovering }"
      @click="onClick"
    ></canvas>

    <div
      v-for="b in bubbles"
      :key="b.id"
      :ref="el => setBubbleEl(b.id, el)"
      class="crowd-bubble"
      :class="[`is-${b.bucket}`, `to-${b.side}`, `kind-${b.kind}`, `dir-${b.dir}`]"
      :style="{ maxWidth: `${b.width}px` }"
    >
      <span class="crowd-bubble-who"><i class="swatch" :class="`is-${b.bucket}`"></i><span class="who-text">{{ b.who }}</span></span>
      <span class="crowd-bubble-text">{{ b.text }}</span>
    </div>

    <div ref="readout" class="crowd-readout" :style="{ bottom: `${bottomInset + 24}px` }">
      <div class="readout-head">
        <span>{{ $t('home.crowdCaption') }}</span>
        <span class="readout-round">{{ $t('home.crowdRound') }} {{ String(round).padStart(2, '0') }}/{{ ROUNDS }}</span>
      </div>
      <div class="readout-event">{{ eventLabel || '—' }}</div>
      <div class="readout-bar">
        <span class="seg is-favor" :style="{ width: `${stats.favor}%` }"></span>
        <span class="seg is-undecided" :style="{ width: `${stats.undecided}%` }"></span>
        <span class="seg is-against" :style="{ width: `${stats.against}%` }"></span>
      </div>
      <div class="readout-legend">
        <span><i class="swatch is-favor"></i>{{ $t('home.crowdFor') }} <b>{{ stats.favor }} %</b></span>
        <span><i class="swatch is-undecided"></i>{{ $t('home.crowdUndecided') }} <b>{{ stats.undecided }} %</b></span>
        <span><i class="swatch is-against"></i>{{ $t('home.crowdAgainst') }} <b>{{ stats.against }} %</b></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  // Tarjeta central: nadie «habla» debajo de ella ni le pone bocadillos encima.
  avoidEl: { type: Object, default: null },
  // Alto (px) de la parte inferior que tapa el formulario que monta sobre la portada.
  bottomInset: { type: Number, default: 0 },
})

const { t } = useI18n()

// ── Sprite de Bianka (el conejo de la firma, 26×29 celdas) ───────────────────
// Extraído de bianka-mascot-alpha.gif. Filas 1–11: orejas; 12+: cabeza y cuerpo.
const BASE = [
  '..........................',
  '........xx................',
  '.......xxxx...............',
  '.......xxxx...............',
  '.......xxxx...............',
  '.......xxxx........xxx....',
  '.......xxxx........xxx....',
  '.......xxxx......xxxxx....',
  '.......xxxx......xxxxx....',
  '.......xxxx.....xxxxx.....',
  '.......xxxx.....xxxxx.....',
  '.......xxxx....xxxxx......',
  '.......xxxxxxxxxxxxx......',
  '.......xxxxxxxxxxxx.......',
  '.......xxxxxxxxxxxx.......',
  '......xxxxxxxxxxxxxx......',
  '......xxxxxxxxxxxxxx......',
  '......xxxxxxxxxxxxxx......',
  '......xxxxxxxxxxxxxx......',
  '....xxxxxxxxxxxxxxxxx.....',
  '....xxxxxxxxxxxxxxxxx.....',
  '....xxxxxxxxxxxxxxxxx.....',
  '...xxxxxxxxxxxxxxxxxxx....',
  '...xxxxxxxxxxxxxxxxxxx....',
  '...xxxxxxxxxxxxxxxxxxx....',
  '...xxxxxxxxxxxxxxxxxxx....',
  '.....xxxxxxxxxxxxxxxx.....',
  '.....xxxxxxxxxxxxxxxx.....',
  '.......xxxxxxxxxxxx.......',
]
const BW = 26
const OX = 2          // margen del lienzo del sprite (contorno y sombreros altos)
const OY = 6
const GW = BW + OX * 2
const GH = BASE.length + OY + 2
const mirrorCol = (c) => BW - 1 - c

const cellsOf = (rows, fromRow, toRow, test) => {
  const out = []
  for (let r = fromRow; r <= toRow; r++) {
    for (let c = 0; c < BW; c++) if (rows[r][c] === 'x' && test(c)) out.push([r, c])
  }
  return out
}
const BODY_CELLS = cellsOf(BASE, 12, BASE.length - 1, () => true)
const EAR_L = cellsOf(BASE, 1, 11, c => c <= 11)
const EAR_R_BENT = cellsOf(BASE, 1, 11, c => c >= 14)
const mirror = (cells) => cells.map(([r, c]) => [r, mirrorCol(c)])
const EAR_R_UP = mirror(EAR_L)
const EAR_L_BENT = mirror(EAR_R_BENT)
const EAR_R_FLOP = [[10, 16], [10, 17], [10, 18], [10, 19], [11, 16], [11, 17], [11, 18], [11, 19], [11, 20],
  [12, 19], [12, 20], [12, 21], [12, 22], [13, 21], [13, 22], [13, 23]]
const EAR_SHORT_L = EAR_L.filter(([r]) => r >= 6).map(([r, c]) => (r === 6 && (c === 7 || c === 10) ? null : [r, c])).filter(Boolean)
const EAR_SHORT_R = mirror(EAR_SHORT_L)
const EARS = [
  { id: 'classic', cells: [...EAR_L, ...EAR_R_BENT], w: 40 },
  { id: 'up', cells: [...EAR_L, ...EAR_R_UP], w: 20 },
  { id: 'v', cells: [...EAR_L_BENT, ...EAR_R_BENT], w: 14 },
  { id: 'flop', cells: [...EAR_L, ...EAR_R_FLOP], w: 16 },
  { id: 'short', cells: [...EAR_SHORT_L, ...EAR_SHORT_R], w: 10 },
]

// ── Disfraces: cada uno es un oficio o un tipo de persona ────────────────────
// [fila, columna, 'píxeles'] en coordenadas de BASE. k tinta · l lima ·
// L lima oscura · w blanco · g gris · '.' transparente.
const COSTUMES = {
  head: [
    { id: 'cap', earsOver: true, px: [[10, 9, 'llllll'], [11, 8, 'llllllll'], [12, 7, 'llllllllll'], [13, 3, 'kkkkkkkkkkkkk']] },
    { id: 'beret', earsOver: true, px: [[9, 12, 'k'], [10, 9, 'kkkkkk'], [11, 7, 'kkkkkkkkkk'], [12, 6, 'kkkkkkkkkkkkk']] },
    { id: 'tophat', earsOver: true, px: [[3, 9, 'kkkkkkk'], [4, 9, 'kkkkkkk'], [5, 9, 'kkkkkkk'], [6, 9, 'kkkkkkk'], [7, 9, 'kkkkkkk'], [8, 9, 'kkkkkkk'], [9, 9, 'lllllll'], [10, 9, 'kkkkkkk'], [11, 6, 'kkkkkkkkkkkkk']] },
    { id: 'graduate', earsOver: true, px: [[9, 3, 'kkkkkkkkkkkkkkkkkkk'], [10, 7, 'kkkkkkkkkkk'], [11, 8, 'kkkkkkkkk'], [10, 21, 'l'], [11, 21, 'l'], [12, 21, 'l'], [13, 20, 'll']] },
    { id: 'hardhat', earsOver: true, px: [[9, 9, 'llllll'], [10, 7, 'llllllllll'], [11, 6, 'llllllllllll'], [12, 4, 'kkkkkkkkkkkkkkkk']] },
    { id: 'chef', hideEars: true, px: [[2, 8, 'wwwwwwwww'], [3, 7, 'wwwwwwwwwww'], [4, 7, 'wwwgwwwgwww'], [5, 8, 'wwwwwwwww'], [6, 9, 'wwwwwww'], [7, 9, 'wwwwwww'], [8, 9, 'wwwwwww'], [9, 9, 'wwwwwww'], [10, 8, 'wwwwwwwww'], [11, 7, 'kkkkkkkkkkk']] },
    { id: 'crown', earsOver: true, px: [[8, 8, 'l..l..l'], [9, 8, 'll.l.ll'], [10, 8, 'lllllll'], [11, 8, 'lLlkLll']] },
    { id: 'beanie', earsOver: true, px: [[8, 11, 'll'], [9, 9, 'kkkkkk'], [10, 8, 'kkkkkkkk'], [11, 7, 'kkkkkkkkkk'], [12, 7, 'lklklklklkl']] },
    { id: 'wizard', hideEars: true, px: [[-4, 13, 'k'], [-3, 12, 'kk'], [-2, 12, 'kkk'], [-1, 11, 'kkkk'], [0, 11, 'kkkkk'], [1, 10, 'kklkkk'], [2, 10, 'kkkkkk'], [3, 9, 'kkkkkkkk'], [4, 9, 'kkklkkkk'], [5, 8, 'kkkkkkkkk'], [6, 8, 'kkkkkkkkkk'], [7, 7, 'kkkkkkkkkkk'], [8, 7, 'kkkkklkkkkk'], [9, 6, 'kkkkkkkkkkkkk'], [10, 4, 'kkkkkkkkkkkkkkkkk']] },
    { id: 'headphones', earsOver: true, px: [[11, 7, 'kkkkkkkkkkkk'], [12, 5, 'k'], [12, 20, 'k'], [13, 5, 'k'], [13, 20, 'k'], [14, 4, 'll'], [15, 4, 'll'], [16, 4, 'll'], [14, 20, 'll'], [15, 20, 'll'], [16, 20, 'll']] },
    { id: 'robot', earsOver: true, screen: true, px: [[5, 12, 'l'], [6, 12, 'k'], [7, 12, 'k'], [8, 12, 'k'], [9, 11, 'kkk'], [14, 8, 'kkkkkkkkkk'], [15, 8, 'kkkkkkkkkk'], [16, 8, 'kkkkkkkkkk'], [17, 8, 'kkkkkkkkkk'], [18, 8, 'kkkkkkkkkk'], [19, 8, 'kkkkkkkkkk']] },
    { id: 'bun', px: [[8, 10, 'ggg'], [9, 9, 'ggggg'], [10, 9, 'ggggg'], [11, 8, 'ggggggg']] },
    { id: 'mohawk', px: [[5, 12, 'l'], [6, 11, 'll'], [7, 11, 'll'], [8, 11, 'lll'], [9, 11, 'lll'], [10, 11, 'lll'], [11, 11, 'lll']] },
    { id: 'viking', earsOver: true, px: [[8, 3, 'w'], [9, 3, 'w'], [10, 3, 'ww'], [11, 4, 'ww'], [8, 22, 'w'], [9, 22, 'w'], [10, 21, 'ww'], [11, 20, 'ww'], [11, 7, 'gggggggggggg'], [12, 6, 'gggggggggggggg']] },
  ],
  face: [
    { id: 'sunglasses', noEyes: 'both', px: [[15, 8, 'kkkkkkkkkk'], [16, 8, 'kkkk..kkkk'], [15, 9, 'w'], [15, 15, 'w']] },
    { id: 'glasses', lockEyes: true, px: [[14, 9, 'kkk..kkk'], [15, 9, 'k.kkkk.k'], [16, 9, 'k.k..k.k'], [17, 9, 'kkk..kkk']] },
    { id: 'pirate', noEyes: 'right', noHead: true, px: [[11, 7, 'llllllllllll'], [12, 7, 'lllllllllllll'], [14, 7, 'kkkkkkkkkkkk'], [15, 14, 'kkk'], [16, 14, 'kkk']] },
    { id: 'mustache', px: [[17, 9, 'kkkkkkkk'], [18, 8, 'k'], [18, 17, 'k']] },
    { id: 'monocle', lockEyes: true, px: [[14, 14, 'kkk'], [15, 14, 'k.k'], [16, 14, 'k.k'], [17, 14, 'kkk'], [18, 16, 'k'], [19, 17, 'k'], [20, 17, 'k']] },
  ],
  body: [
    { id: 'bowtie', px: [[20, 10, 'll..ll'], [21, 10, 'llkkll'], [22, 10, 'll..ll']] },
    { id: 'tie', px: [[20, 12, 'kk'], [21, 12, 'kk'], [22, 11, 'kkkk'], [23, 11, 'kkkk'], [24, 11, 'kkkk'], [25, 12, 'kk']] },
    { id: 'stripes', pattern: 'stripes', px: [] },
    { id: 'spots', pattern: 'spots', px: [] },
    { id: 'scarf', px: [[19, 5, 'llllllllllllllll'], [20, 5, 'LLLLLLLLLLLLLLLL'], [21, 15, 'll'], [22, 15, 'll'], [23, 15, 'lL']] },
    { id: 'sign', px: [[19, 5, 'kkkkkkkkkkkkkkkk'], [20, 5, 'kwwwwwwwwwwwwwwk'], [21, 5, 'kwwwwwwkwwwwwwwk'], [22, 5, 'kwwwwwwkwwwwwwwk'], [23, 5, 'kwwwwwwwwwwwwwwk'], [24, 5, 'kwwwwwwkwwwwwwwk'], [25, 5, 'kkkkkkkkkkkkkkkk'], [26, 12, 'kk'], [27, 12, 'kk'], [28, 12, 'kk']] },
    { id: 'coffee', px: [[18, 15, 'g.g'], [19, 16, 'g'], [21, 14, 'lllll'], [22, 14, 'lwlll'], [22, 19, 'l'], [23, 14, 'lllll'], [23, 19, 'l'], [24, 15, 'lll']] },
    { id: 'pencil', px: [[18, 20, 'gg'], [19, 19, 'll'], [20, 18, 'll'], [21, 17, 'll'], [22, 16, 'll'], [23, 15, 'll'], [24, 14, 'ww'], [25, 13, 'k']] },
    { id: 'heart', px: [[21, 9, 'll.ll'], [22, 8, 'lllllll'], [23, 8, 'lllllll'], [24, 9, 'lllll'], [25, 10, 'lll'], [26, 11, 'l']] },
    { id: 'plane', px: [[19, 16, 'l'], [20, 14, 'lll'], [21, 12, 'lllll'], [22, 10, 'llllLll'], [23, 13, 'Ll'], [24, 14, 'L']] },
    { id: 'phone', px: [[20, 14, 'kkkk'], [21, 14, 'klLk'], [22, 14, 'kllk'], [23, 14, 'kllk'], [24, 14, 'kkkk']] },
    { id: 'baby', px: [[17, 15, 'g.g'], [18, 15, 'g.g'], [19, 14, 'ggggg'], [20, 14, 'gkgkg'], [21, 14, 'ggggg'], [22, 15, 'ggg']] },
    { id: 'kbrand', px: [[20, 10, 'l'], [21, 10, 'l..l'], [22, 10, 'l.l'], [23, 10, 'll'], [24, 10, 'l.l'], [25, 10, 'l..l']] },
  ],
}

const PAL = { k: '#111111', l: '#CCE673', L: '#94AA3D', w: '#FFFFFF', g: '#8A8A8A', c: '#F2F1EF' }
const LOOK = {
  favor: { body: '#CCE673', face: '#111111', stripe: '#111111' },
  undecided: { body: '#FFFFFF', face: '#111111', stripe: '#111111' },
  against: { body: '#2A2A2A', face: '#F2F1EF', stripe: '#F2F1EF' },
}
// Si un complemento cae sobre el cuerpo y es del mismo color, se cambia para que se vea.
const ALT = { '#CCE673': PAL.L, '#FFFFFF': PAL.g, '#111111': PAL.c, '#2A2A2A': PAL.c }

const ROUNDS = 10
const ROUND_SECONDS = 6.5
const VALENCE = [0.55, -0.45, 0.4, -0.4, 0.5, -0.3, 0.45, -0.35, 0.4, 0.3]

const root = ref(null)
const canvas = ref(null)
const readout = ref(null)
const round = ref(0)
const eventLabel = ref('')
const stats = reactive({ favor: 0, undecided: 100, against: 0 })
const bubbles = ref([])
const hovering = ref(false)

let ctx = null
let W = 0, H = 0, dpr = 1, P = 4, CX = 68, RY = 76
let agents = []
let avoid = []
let waves = []
let threads = []
let raf = null, running = false, visible = true, last = 0, now = 0
let roundClock = 0, talkClock = 0, statsClock = 0, measureClock = 0, resetClock = -1
let bubbleSeq = 0
let epoch = 0
let pointer = null
const bubbleEls = new Map()
const spriteCache = new Map()
let resizeObs = null, interObs = null
const reducedMotion = typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const bucketOf = (o) => (o > 0.33 ? 'favor' : o < -0.33 ? 'against' : 'undecided')
const bucketLabel = (b) => t({ favor: 'home.crowdFor', undecided: 'home.crowdUndecided', against: 'home.crowdAgainst' }[b])
const setBubbleEl = (id, el) => { if (el) bubbleEls.set(id, el); else bubbleEls.delete(id) }
const rand = (a, b) => a + Math.random() * (b - a)
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)]
const pickWeighted = (arr) => {
  let n = Math.random() * arr.reduce((s, e) => s + e.w, 0)
  for (const e of arr) { if ((n -= e.w) <= 0) return e }
  return arr[0]
}
const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5
const randomLean = () => Math.max(-1, Math.min(1, gauss() * 1.6 + 0.12))

// ── Construcción de cada Bianka ─────────────────────────────────────────────
const makeLook = () => {
  const face = Math.random() < 0.3 ? pick(COSTUMES.face) : null
  const head = !face?.noHead && Math.random() < 0.55 ? pick(COSTUMES.head) : null
  const body = Math.random() < 0.55 ? pick(COSTUMES.body) : null
  const ears = pickWeighted(EARS)
  // El rótulo del bocadillo sale del rasgo más visible
  const persona = (body || head || face)?.id || 'plain'
  return { key: `${ears.id}|${head?.id}|${face?.id}|${body?.id}`, ears, head, face, body, persona }
}

const spriteFor = (look, bucket) => {
  const key = `${look.key}|${bucket}`
  let spr = spriteCache.get(key)
  if (spr) return spr
  const colors = LOOK[bucket]
  const grid = Array.from({ length: GH }, () => Array(GW).fill(null))
  const bodyMask = Array.from({ length: GH }, () => Array(GW).fill(false))
  const put = (r, c, color) => {
    const R = r + OY, C = c + OX
    if (R >= 0 && R < GH && C >= 0 && C < GW) grid[R][C] = color
  }
  const items = [look.head, look.face, look.body].filter(Boolean)
  const hideEars = items.some(i => i.hideEars)
  const earsOver = items.some(i => i.earsOver)
  const drawEars = () => { if (!hideEars) for (const [r, c] of look.ears.cells) put(r, c, colors.body) }
  if (!earsOver) drawEars()
  for (const [r, c] of BODY_CELLS) { put(r, c, colors.body); bodyMask[r + OY][c + OX] = true }
  if (look.body?.pattern === 'stripes') {
    for (const [r, c] of BODY_CELLS) if (r >= 21 && r % 2 === 1) put(r, c, colors.stripe)
  } else if (look.body?.pattern === 'spots') {
    const spots = [[21, 6], [21, 7], [22, 6], [23, 15], [23, 16], [24, 16], [24, 15], [26, 9], [26, 10], [22, 19], [25, 5], [20, 13]]
    for (const [r, c] of spots) put(r, c, colors.stripe)
  }
  for (const item of items) {
    for (const [r0, c0, s] of item.px) {
      for (let i = 0; i < s.length; i++) {
        if (s[i] === '.') continue
        let color = PAL[s[i]]
        const R = r0 + OY, C = c0 + i + OX
        if (R >= 0 && R < GH && C >= 0 && C < GW && bodyMask[R][C] && color === colors.body) color = ALT[color] || color
        put(r0, c0 + i, color)
      }
    }
  }
  if (earsOver) drawEars()
  // contorno de tinta alrededor de la silueta completa
  const outline = []
  for (let r = 0; r < GH; r++) {
    for (let c = 0; c < GW; c++) {
      if (grid[r][c]) continue
      if ((grid[r - 1]?.[c]) || (grid[r + 1]?.[c]) || grid[r][c - 1] || grid[r][c + 1]) outline.push([r, c])
    }
  }
  const cv = document.createElement('canvas')
  cv.width = GW
  cv.height = GH
  const g = cv.getContext('2d')
  for (let r = 0; r < GH; r++) {
    for (let c = 0; c < GW; c++) {
      if (!grid[r][c]) continue
      g.fillStyle = grid[r][c]
      g.fillRect(c, r, 1, 1)
    }
  }
  g.fillStyle = PAL.k
  for (const [r, c] of outline) g.fillRect(c, r, 1, 1)
  spriteCache.set(key, cv)
  return cv
}

const seedAgents = () => {
  P = W < 700 ? 3 : 4
  CX = 21 * P
  RY = 22 * P
  const cols = Math.ceil(W / CX) + 2
  const rows = Math.ceil((H + 10 * P) / RY) + 1
  agents = []
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const x = (col - 1) * CX + (row % 2 ? CX / 2 : 0) + Math.round(rand(-2, 2)) * P - 6 * P
      const y = row * RY - 9 * P + Math.round(rand(-1, 1)) * P
      agents.push({
        x, y, row, col,
        look: makeLook(),
        mirror: Math.random() < 0.5,
        o: gauss() * 0.18,
        lean: randomLean(),
        stub: Math.random() ** 2 * 0.8,
        bobPeriod: rand(1.6, 2.8),
        bobPhase: Math.random(),
        nextBlink: rand(0, 5),
        blinkUntil: 0,
        hopAt: -10,
        glyph: null,
        glyphUntil: 0,
        talkUntil: 0,
        lookAt: null,
        lookUntil: 0,
        idleGaze: [0, 0],
        nextIdle: rand(1, 5),
        happyUntil: 0,
      })
    }
  }
}

const headOf = (a) => ({ x: a.x + 12.5 * P, y: a.y + 16 * P })

const measureAvoid = () => {
  if (!root.value) return
  const c = root.value.getBoundingClientRect()
  const rel = (r) => ({ l: r.left - c.left, t: r.top - c.top, r: r.right - c.left, b: r.bottom - c.top })
  avoid = []
  if (props.avoidEl) avoid.push(rel(props.avoidEl.getBoundingClientRect()))
  if (props.bottomInset) avoid.push({ l: 0, t: H - props.bottomInset, r: W, b: H })
  if (readout.value) avoid.push(rel(readout.value.getBoundingClientRect()))
}

const hitsAvoid = (box, pad) => avoid.some(q => box.l < q.r + pad && box.r > q.l - pad && box.t < q.b + pad && box.b > q.t - pad)
const headVisible = (a) => {
  const h = { l: a.x + 6 * P, r: a.x + 20 * P, t: a.y + 12 * P, b: a.y + 20 * P }
  return h.r > 0 && h.l < W && h.t > 0 && h.b < H && !hitsAvoid(h, 0)
}

const resize = () => {
  const el = root.value
  if (!el || !canvas.value) return
  const w = el.clientWidth, h = el.clientHeight
  if (!w || !h) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  canvas.value.width = Math.round(w * dpr)
  canvas.value.height = Math.round(h * dpr)
  canvas.value.style.width = `${w}px`
  canvas.value.style.height = `${h}px`
  ctx = canvas.value.getContext('2d')
  const reseed = !agents.length || Math.abs(w - W) > 40 || Math.abs(h - H) > 80
  W = w; H = h
  if (reseed) { epoch++; seedAgents(); bubbles.value = []; threads = [] }
  measureAvoid()
  updateStats()
  if (!running) draw()
}

// ── Opinión y conversación ─────────────────────────────────────────────────
const react = (a, glyph, dur = 0.9) => {
  a.hopAt = now
  a.glyph = glyph
  a.glyphUntil = now + dur
}

const shift = (a, delta) => {
  const before = bucketOf(a.o)
  a.o = Math.max(-1, Math.min(1, a.o + delta))
  const after = bucketOf(a.o)
  if (before !== after) {
    react(a, after === 'favor' ? 'heart' : after === 'against' ? 'bang' : 'question', 1.1)
    if (after === 'favor') a.happyUntil = now + 1.6
  }
  return before !== after
}

const fireEvent = () => {
  round.value += 1
  const n = ((round.value - 1) % ROUNDS) + 1
  eventLabel.value = t(`home.crowdEvent${n}`)
  waves.push({ dir: Math.random() < 0.5 ? 1 : -1, start: now, v: VALENCE[n - 1], hit: new Set() })
}

const stepWaves = () => {
  const speed = (W + 400) / 2.2
  for (const w of waves) {
    const front = w.dir > 0 ? -200 + speed * (now - w.start) : W + 200 - speed * (now - w.start)
    agents.forEach((a, i) => {
      if (w.hit.has(i)) return
      const cx = a.x + 12.5 * P
      if (Math.abs(cx - front) < CX * 0.6) {
        w.hit.add(i)
        const affinity = 1 + 1.3 * Math.max(0, Math.sign(w.v) * a.lean)
        const changed = shift(a, w.v * (0.3 + 0.7 * Math.random()) * (1 - a.stub) * affinity)
        if (!changed) { a.hopAt = now; if (Math.random() < 0.18) react(a, w.v > 0 ? 'bang' : 'question', 0.7) }
      }
    })
  }
  waves = waves.filter(w => now - w.start < 3)
}

const drift = (dt) => {
  const heat = round.value / ROUNDS
  for (const a of agents) a.o += (a.lean * 0.9 - a.o) * 0.02 * heat * dt * (1 - a.stub * 0.5)
}

// ── Colocación de bocadillos ─────────────────────────────────────────────────
// Un bocadillo va encima de la cabeza (lo habitual), debajo o a un lado; hacia
// el lado con más pared y, si ahí no cabe, hacia el otro; y si ni así, se
// estrecha (hasta MIN_BW). Nunca pisa la tarjeta, el marcador ni el borde.
const MIN_BW = 150
const bubbleW = () => (W < 700 ? 180 : W < 1280 ? 200 : 230)
const heightFor = (w) => (w >= 210 ? 76 : w >= 175 ? 88 : 104)
const otherSide = (side) => (side === 'left' ? 'right' : 'left')

// Punto de la cabeza al que se ancla el bocadillo
const anchorOf = (a, dir = 'up', side = 'right') => {
  if (dir === 'side') return { x: a.x + (side === 'right' ? 19.5 : 5.5) * P, y: a.y + 16 * P }
  return { x: a.x + 12.5 * P, y: a.y + (dir === 'down' ? 22 : 11) * P }
}
const preferredSide = (a) => (anchorOf(a).x > W / 2 ? 'left' : 'right')
const boxFor = (a, dir, side, w, h) => {
  const { x, y } = anchorOf(a, dir, side)
  if (dir === 'side') {
    const l = side === 'right' ? x + 12 : x - 12 - w
    return { l, r: l + w, t: y - h / 2, b: y + h / 2 }
  }
  const l = side === 'right' ? x - 18 : x + 18 - w
  return dir === 'down'
    ? { l, r: l + w, t: y + 12, b: y + 12 + h }
    : { l, r: l + w, t: y - 12 - h, b: y - 12 }
}
const boxOf = (bb) => boxFor(agents[bb.agent], bb.dir, bb.side, bb.width, bb.height)
const boxesTouch = (p, q, gap) => p.l < q.r + gap && p.r > q.l - gap && p.t < q.b + gap && p.b > q.t - gap

// ignoreBubbles: solo cuentan los bordes, la tarjeta y el marcador
const boxFree = (box, ignoreBubbles = false) => {
  if (box.l < 8 || box.r > W - 8 || box.t < 8 || box.b > H - 8) return false
  if (hitsAvoid(box, 12)) return false
  if (ignoreBubbles) return true
  return !bubbles.value.some(bb => agents[bb.agent] && boxesTouch(box, boxOf(bb), 14))
}

// Dónde poner el bocadillo de una Bianka: { dir, side, width, height } o null.
// Prefiere el ancho completo en cualquiera de los dos lados antes de estrecharlo.
const placeBubble = (a, dirs = ['up', 'side'], ignoreBubbles = false) => {
  const first = preferredSide(a)
  const full = bubbleW()
  const widths = [full, 170, MIN_BW].filter((w, i, arr) => w <= full && arr.indexOf(w) === i)
  for (const dir of dirs) {
    for (const width of widths) {
      const height = heightFor(width)
      for (const side of [first, otherSide(first)]) {
        if (boxFree(boxFor(a, dir, side, width, height), ignoreBubbles)) return { dir, side, width, height }
      }
    }
  }
  return null
}

const speaking = (i) => bubbles.value.some(b => b.agent === i)

const addBubble = (i, text, kind, life, place) => {
  const a = agents[i]
  const bucket = bucketOf(a.o)
  const id = ++bubbleSeq
  bubbles.value.push({
    id, agent: i, bucket, text, kind,
    who: `${t(`home.biankas.${a.look.persona}`)} · ${bucketLabel(bucket).toLowerCase()}`,
    side: place.side,
    dir: place.dir,
    width: place.width,
    height: place.height,
  })
  a.talkUntil = now + Math.min(life - 0.6, 2.2)
  setTimeout(() => { bubbles.value = bubbles.value.filter(b => b.id !== id) }, life * 1000)
  return id
}

const neighborsOf = (i, radius) => {
  const a = agents[i]
  const h = headOf(a)
  return agents
    .map((b, j) => ({ j, d: Math.hypot(headOf(b).x - h.x, headOf(b).y - h.y) }))
    .filter(n => n.j !== i && n.d < radius)
}

const startConversation = (forced = null, forcedPlace = null) => {
  const max = W < 700 ? 2 : 4
  if (bubbles.value.length >= max && forced === null) return
  let i = forced
  let place = forcedPlace
  if (i === null) {
    for (let tries = 0; tries < 60; tries++) {
      const k = Math.floor(Math.random() * agents.length)
      if (speaking(k) || !headVisible(agents[k])) continue
      const found = placeBubble(agents[k])
      if (found) { i = k; place = found; break }
    }
  }
  if (i === null || speaking(i) || !place) return
  const a = agents[i]
  const bucket = bucketOf(a.o)
  const pool = { favor: [1, 2, 3], undecided: [4, 5, 6], against: [7, 8, 9] }[bucket]
  addBubble(i, t(`home.crowdVoice${pick(pool)}`), 'say', 3.6, place)
  const myEpoch = epoch
  a.hopAt = now
  // Las vecinas giran los ojos hacia quien habla
  const near = neighborsOf(i, CX * 2.6)
  for (const n of near) { agents[n.j].lookAt = i; agents[n.j].lookUntil = now + 2.4 }
  // y una contesta
  const candidates = near.filter(n => !speaking(n.j) && headVisible(agents[n.j]))
  setTimeout(() => {
    if (myEpoch !== epoch || (!running && !forced)) return
    const opts = candidates
      .map(n => ({ j: n.j, place: placeBubble(agents[n.j]) }))
      .filter(o => o.place)
    if (!opts.length) return
    const { j, place: replyPlace } = pick(opts)
    const b = agents[j]
    const before = bucketOf(b.o)
    let changed = false
    if (Math.abs(b.o - a.o) < 0.9) changed = shift(b, 0.55 * (a.o - b.o) * (1 - b.stub))
    const after = bucketOf(b.o)
    // la respuesta debe cuadrar con lo que piensa quien contesta: quien está a favor no duda
    const key = changed ? pick([5, 6]) : after === bucketOf(a.o) ? pick([1, 2]) : after === 'favor' ? 3 : 4
    if (!changed && before !== bucketOf(a.o)) react(b, 'question', 0.9)
    const id = addBubble(j, t(`home.crowdReply${key}`), 'reply', 3.0, replyPlace)
    b.lookAt = i; b.lookUntil = now + 2.6
    a.lookAt = j; a.lookUntil = now + 2.6
    threads.push({ from: i, to: j, until: now + 2.8, id })
  }, 1300)
}

const updateStats = () => {
  if (!agents.length) return
  const c = { favor: 0, undecided: 0, against: 0 }
  for (const a of agents) c[bucketOf(a.o)]++
  const n = agents.length
  stats.favor = Math.round((c.favor / n) * 100)
  stats.against = Math.round((c.against / n) * 100)
  stats.undecided = Math.max(0, 100 - stats.favor - stats.against)
}

// ── Dibujo ──────────────────────────────────────────────────────────────────
const GLYPHS = {
  bang: { color: PAL.k, rows: ['k', 'k', 'k', '.', 'k'] },
  question: { color: PAL.k, rows: ['.kk.', 'k..k', '..k.', '.k..', '....', '.k..'] },
  heart: { color: '#94AA3D', rows: ['.k.k.', 'kkkkk', 'kkkkk', '.kkk.', '..k..'] },
}

const drawGlyph = (a, dy) => {
  const g = GLYPHS[a.glyph]
  if (!g) return
  const w = g.rows[0].length
  const x0 = a.x + (12.5 - w / 2) * P
  const y0 = a.y + dy - (g.rows.length + 2) * P
  ctx.fillStyle = g.color
  g.rows.forEach((row, r) => {
    for (let c = 0; c < row.length; c++) if (row[c] === 'k') ctx.fillRect(x0 + c * P, y0 + r * P, P, P)
  })
}

const gazeOf = (a) => {
  let target = null
  if (a.lookAt !== null && now < a.lookUntil && agents[a.lookAt]) target = headOf(agents[a.lookAt])
  else if (pointer) {
    const h = headOf(a)
    if (Math.hypot(pointer.x - h.x, pointer.y - h.y) < 380) target = pointer
  }
  if (!target) return a.idleGaze
  const h = headOf(a)
  const dx = target.x - h.x, dy = target.y - h.y
  return [Math.abs(dx) > 18 ? Math.sign(dx) : 0, Math.abs(dy) > 18 ? Math.sign(dy) : 0]
}

const drawFace = (a, dy) => {
  const look = a.look
  const items = [look.head, look.face, look.body].filter(Boolean)
  const screen = items.some(i => i.screen)
  const lock = items.some(i => i.lockEyes)
  const noEyes = items.find(i => i.noEyes)?.noEyes
  const colors = LOOK[bucketOf(a.o)]
  const cell = (r, c) => {
    const cc = a.mirror ? mirrorCol(c) : c
    ctx.fillRect(a.x + cc * P, a.y + dy + r * P, P, P)
  }
  let [gx, gy] = gazeOf(a)
  if (a.mirror) gx = -gx
  if (lock) { gx = 0; gy = 0 }
  ctx.fillStyle = screen ? PAL.l : colors.face
  const blink = now < a.blinkUntil
  const happy = now < a.happyUntil
  const eyes = [10, 15].filter((c, k) => !(noEyes === 'both' || (noEyes === 'right' && k === 1)))
  for (const c of eyes) {
    const ec = c + gx
    if (happy) { cell(15, ec - 1); cell(14, ec); cell(15, ec + 1) }
    else if (blink) cell(16, ec)
    else { cell(15 + gy, ec); cell(16 + gy, ec) }
  }
  // boca: cerrada en «T»; al hablar se abre y se cierra
  const talking = now < a.talkUntil && Math.floor(now * 8) % 2 === 0
  if (talking) { cell(18, 12); cell(18, 13); cell(19, 12); cell(19, 13); cell(20, 12); cell(20, 13) }
  else { cell(18, 12); cell(18, 13); cell(19, 12) }
}

const drawThreads = () => {
  threads = threads.filter(th => now < th.until && agents[th.from] && agents[th.to])
  ctx.fillStyle = PAL.k
  for (const th of threads) {
    const p = anchorOf(agents[th.from]), q = anchorOf(agents[th.to])
    const mx = (p.x + q.x) / 2, my = Math.min(p.y, q.y) - 40
    const steps = Math.max(6, Math.round(Math.hypot(q.x - p.x, q.y - p.y) / (P * 3)))
    for (let s = 1; s < steps; s++) {
      const u = s / steps
      const x = (1 - u) ** 2 * p.x + 2 * (1 - u) * u * mx + u ** 2 * q.x
      const y = (1 - u) ** 2 * p.y + 2 * (1 - u) * u * my + u ** 2 * q.y
      ctx.fillRect(Math.round(x / P) * P, Math.round(y / P) * P, P, P)
    }
  }
}

const offsetOf = (a) => {
  const bob = ((now / a.bobPeriod + a.bobPhase) % 1) < 0.5 ? 0 : P
  const hopT = now - a.hopAt
  const hop = hopT >= 0 && hopT < 0.32 ? Math.round(Math.sin((Math.PI * hopT) / 0.32) * 3) * P : 0
  return bob - hop
}

const draw = () => {
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, W, H)
  for (const a of agents) {
    const dy = offsetOf(a)
    const spr = spriteFor(a.look, bucketOf(a.o))
    const x = a.x - OX * P
    const y = a.y + dy - OY * P
    if (a.mirror) {
      ctx.save()
      ctx.translate(x + GW * P, y)
      ctx.scale(-1, 1)
      ctx.drawImage(spr, 0, 0, GW * P, GH * P)
      ctx.restore()
    } else {
      ctx.drawImage(spr, x, y, GW * P, GH * P)
    }
    drawFace(a, dy)
  }
  drawThreads()
  for (const a of agents) if (a.glyph && now < a.glyphUntil) drawGlyph(a, offsetOf(a))
  for (const bub of bubbles.value) {
    const el = bubbleEls.get(bub.id)
    const a = agents[bub.agent]
    if (!el || !a) continue
    const { x, y } = anchorOf(a, bub.dir, bub.side)
    el.style.transform = `translate(${Math.round(x)}px, ${Math.round(y + offsetOf(a))}px)`
    el.style.visibility = hitsAvoid(boxOf(bub), 0) ? 'hidden' : ''
  }
}

const tick = (ts) => {
  raf = null
  if (!running) return
  const dt = Math.min(0.05, (ts - last) / 1000 || 0.016)
  last = ts
  now += dt
  for (const a of agents) {
    if (now > a.nextBlink) { a.blinkUntil = now + 0.13; a.nextBlink = now + rand(2.5, 6.5) }
    if (now > a.nextIdle) { a.idleGaze = [Math.round(rand(-1, 1)), Math.round(rand(-1, 0.4))]; a.nextIdle = now + rand(2, 6) }
  }
  stepWaves()
  drift(dt)
  if (resetClock >= 0) {
    resetClock += dt
    if (resetClock > 3.5) {
      for (const a of agents) { a.o = gauss() * 0.18; a.lean = randomLean() }
      round.value = 0
      eventLabel.value = ''
      resetClock = -1
      roundClock = 0
    }
  } else {
    roundClock += dt
    if (roundClock >= (round.value === 0 ? 1.2 : ROUND_SECONDS)) {
      roundClock = 0
      if (round.value >= ROUNDS) resetClock = 0
      else fireEvent()
    }
  }
  talkClock += dt
  if (talkClock > (W < 700 ? 2.6 : 1.7)) { talkClock = 0; startConversation() }
  statsClock += dt
  if (statsClock > 0.4) { statsClock = 0; updateStats() }
  measureClock += dt
  if (measureClock > 1.5) { measureClock = 0; measureAvoid() }
  draw()
  raf = requestAnimationFrame(tick)
}

const start = () => {
  if (running || reducedMotion || !visible || document.hidden) return
  running = true
  last = performance.now()
  raf = requestAnimationFrame(tick)
}
const stop = () => {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = null
}
const onVisibility = () => (document.hidden ? stop() : start())

// ── Interacción: te miran y, si tocas una, habla ────────────────────────────
const agentAt = (x, y) => {
  for (let k = agents.length - 1; k >= 0; k--) {
    const a = agents[k]
    const dy = offsetOf(a)
    if (x > a.x + 5 * P && x < a.x + 21 * P && y > a.y + dy + 12 * P && y < a.y + dy + 22 * P) return k
  }
  return null
}
// Bajo el marcador (que deja pasar los eventos) o la franja que tapa el formulario
// hay Biankas que no se ven: ahí ni cambia el cursor ni responde el clic.
const coveredAt = (x, y) => hitsAvoid({ l: x, r: x, t: y, b: y }, 0)
const onPointerMove = (e) => {
  if (!root.value) return
  const c = root.value.getBoundingClientRect()
  const x = e.clientX - c.left, y = e.clientY - c.top
  pointer = x >= 0 && y >= 0 && x <= c.width && y <= c.height ? { x, y } : null
  hovering.value = pointer !== null && e.target === canvas.value && !coveredAt(x, y) && agentAt(x, y) !== null
}
const onClick = (e) => {
  const c = root.value.getBoundingClientRect()
  const x = e.clientX - c.left, y = e.clientY - c.top
  if (coveredAt(x, y)) return
  const k = agentAt(x, y)
  if (k === null || speaking(k)) return
  measureAvoid()
  const a = agents[k]
  const dirs = ['up', 'down', 'side']
  let place = placeBubble(a, dirs)
  if (!place) {
    // El clic manda: si solo estorban otros bocadillos, se retiran para dejarle sitio.
    place = placeBubble(a, dirs, true)
    if (place) {
      const box = boxFor(a, place.dir, place.side, place.width, place.height)
      bubbles.value = bubbles.value.filter(bb => agents[bb.agent] && !boxesTouch(box, boxOf(bb), 14))
    }
  }
  // Sin sitio ni retirando bocadillos (pegada a la tarjeta, al marcador o al borde): solo reacciona.
  if (place) startConversation(k, place)
  else react(a, 'bang', 0.8)
}

// Sin animación: las diez rondas de golpe y el resultado quieto.
const renderStatic = () => {
  for (let r = 0; r < ROUNDS; r++) {
    const v = VALENCE[r]
    for (const a of agents) {
      const affinity = 1 + 1.3 * Math.max(0, Math.sign(v) * a.lean)
      a.o = Math.max(-1, Math.min(1, a.o + v * (0.3 + 0.7 * Math.random()) * (1 - a.stub) * affinity))
      a.o += (a.lean * 0.9 - a.o) * 0.25 * (r / ROUNDS)
    }
  }
  round.value = ROUNDS
  eventLabel.value = t(`home.crowdEvent${ROUNDS}`)
  updateStats()
  draw()
}

onMounted(() => {
  resize()
  resizeObs = new ResizeObserver(() => resize())
  resizeObs.observe(root.value)
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.fonts?.ready?.then(() => { measureAvoid(); if (!running) draw() })
  if (reducedMotion) { renderStatic(); return }
  interObs = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    visible ? start() : stop()
  })
  interObs.observe(root.value)
  document.addEventListener('visibilitychange', onVisibility)
  start()
})

onUnmounted(() => {
  stop()
  resizeObs?.disconnect()
  interObs?.disconnect()
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<style scoped>
.bianka-crowd {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.crowd-canvas { display: block; image-rendering: pixelated; }
.crowd-canvas.is-hovering { cursor: pointer; }

.crowd-bubble {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 3;
  width: max-content;
  translate: -18px calc(-100% - 12px);
  padding: 8px 11px 9px;
  background: var(--kb-surface);
  color: var(--kb-text);
  border: 2px solid var(--ink-950);
  border-radius: 4px;
  box-shadow: 4px 4px 0 var(--ink-950);
  display: grid;
  gap: 3px;
  pointer-events: none;
  animation: bubble-pop 0.22s steps(3, end) both;
}
.crowd-bubble.kind-reply { background: var(--cream-100); }
.crowd-bubble.to-left { translate: calc(-100% + 18px) calc(-100% - 12px); }
.crowd-bubble.dir-down { translate: -18px 12px; }
.crowd-bubble.dir-down.to-left { translate: calc(-100% + 18px) 12px; }
.crowd-bubble.dir-side { translate: 12px -50%; }
.crowd-bubble.dir-side.to-left { translate: calc(-100% - 12px) -50%; }
/* pico escalonado, en píxeles */
.crowd-bubble::before,
.crowd-bubble::after {
  content: '';
  position: absolute;
  left: 12px;
  width: 8px;
  height: 6px;
  background: var(--ink-950);
}
.crowd-bubble::before { bottom: -8px; }
.crowd-bubble::after { bottom: -12px; left: 12px; width: 4px; height: 4px; }
.crowd-bubble.to-left::before,
.crowd-bubble.to-left::after { left: auto; right: 12px; }
/* si se abre hacia abajo, el pico va arriba */
.crowd-bubble.dir-down::before { bottom: auto; top: -8px; }
.crowd-bubble.dir-down::after { bottom: auto; top: -12px; }
/* al lado de la cabeza, el pico sale por el costado */
.crowd-bubble.dir-side::before { bottom: auto; top: calc(50% - 4px); left: -8px; width: 6px; height: 8px; }
.crowd-bubble.dir-side::after { bottom: auto; top: calc(50% - 2px); left: -12px; width: 4px; height: 4px; }
.crowd-bubble.dir-side.to-left::before { left: auto; right: -8px; }
.crowd-bubble.dir-side.to-left::after { left: auto; right: -12px; }
.crowd-bubble-who {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  font-family: var(--kb-font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--kb-muted);
  white-space: nowrap;
}
.who-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.crowd-bubble-text {
  font-family: var(--kb-font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  text-wrap: pretty;
}
@keyframes bubble-pop {
  from { opacity: 0; scale: 0.6; }
  to { opacity: 1; scale: 1; }
}

.swatch {
  display: inline-block;
  flex: none;
  width: 8px;
  height: 8px;
  border: 1.5px solid var(--ink-950);
}
.swatch.is-favor { background: var(--lime-500); }
.swatch.is-undecided { background: #fff; }
.swatch.is-against { background: #2A2A2A; }

.crowd-readout {
  position: absolute;
  z-index: 3;
  inset-inline-start: clamp(16px, 4vw, 48px);
  bottom: 24px;
  width: min(360px, calc(100% - 32px));
  padding: 12px 14px;
  background: var(--kb-surface);
  border: 2px solid var(--ink-950);
  border-radius: 6px;
  box-shadow: 4px 4px 0 var(--ink-950);
  color: var(--kb-text);
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  pointer-events: none;
}
.readout-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--kb-muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.readout-round { color: var(--kb-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.readout-event {
  margin-top: 6px;
  font-family: var(--kb-font-sans);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--kb-text);
}
.readout-bar {
  display: flex;
  height: 8px;
  margin: 10px 0;
  overflow: hidden;
  border: 1.5px solid var(--ink-950);
  background: #fff;
}
.readout-bar .seg { transition: width 0.6s steps(6, end); }
.readout-bar .is-favor { background: var(--lime-500); }
.readout-bar .is-undecided { background: #fff; }
.readout-bar .is-against { background: #2A2A2A; }
.readout-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; color: var(--kb-text-2); }
.readout-legend span { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
.readout-legend b { font-weight: 700; color: var(--kb-text); font-variant-numeric: tabular-nums; }

@media (max-width: 700px) {
  .crowd-readout { inset-inline-start: 16px; bottom: 16px; }
}
@media (prefers-reduced-motion: reduce) {
  .crowd-bubble { animation: none; }
  .readout-bar .seg { transition: none; }
}
</style>
