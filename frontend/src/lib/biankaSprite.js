// Motor de sprites de la Bianka: el conejo en pixel art de la firma de Koolbrand.
// Lo comparten el muro de la portada, las escenas de «Cómo funciona» y el cierre.
// Todo se dibuja en una retícula de celdas (BW×…): P píxeles de pantalla por celda.

// ── Sprite de Bianka (el conejo de la firma, 26×29 celdas) ───────────────────
// Extraído de bianka-mascot-alpha.gif. Filas 1–11: orejas; 12+: cabeza y cuerpo.
export const BASE = [
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
export const BW = 26
export const OX = 2          // margen del lienzo del sprite (contorno y sombreros altos)
export const OY = 6
export const GW = BW + OX * 2
export const GH = BASE.length + OY + 2
export const mirrorCol = (c) => BW - 1 - c

export const cellsOf = (rows, fromRow, toRow, test) => {
  const out = []
  for (let r = fromRow; r <= toRow; r++) {
    for (let c = 0; c < BW; c++) if (rows[r][c] === 'x' && test(c)) out.push([r, c])
  }
  return out
}
export const BODY_CELLS = cellsOf(BASE, 12, BASE.length - 1, () => true)
export const EAR_L = cellsOf(BASE, 1, 11, c => c <= 11)
export const EAR_R_BENT = cellsOf(BASE, 1, 11, c => c >= 14)
export const mirror = (cells) => cells.map(([r, c]) => [r, mirrorCol(c)])
export const EAR_R_UP = mirror(EAR_L)
export const EAR_L_BENT = mirror(EAR_R_BENT)
export const EAR_R_FLOP = [[10, 16], [10, 17], [10, 18], [10, 19], [11, 16], [11, 17], [11, 18], [11, 19], [11, 20],
  [12, 19], [12, 20], [12, 21], [12, 22], [13, 21], [13, 22], [13, 23]]
export const EAR_SHORT_L = EAR_L.filter(([r]) => r >= 6).map(([r, c]) => (r === 6 && (c === 7 || c === 10) ? null : [r, c])).filter(Boolean)
export const EAR_SHORT_R = mirror(EAR_SHORT_L)
export const EARS = [
  { id: 'classic', cells: [...EAR_L, ...EAR_R_BENT], w: 40 },
  { id: 'up', cells: [...EAR_L, ...EAR_R_UP], w: 20 },
  { id: 'v', cells: [...EAR_L_BENT, ...EAR_R_BENT], w: 14 },
  { id: 'flop', cells: [...EAR_L, ...EAR_R_FLOP], w: 16 },
  { id: 'short', cells: [...EAR_SHORT_L, ...EAR_SHORT_R], w: 10 },
]

// ── Disfraces: cada uno es un oficio o un tipo de persona ────────────────────
// [fila, columna, 'píxeles'] en coordenadas de BASE. k tinta · l lima ·
// L lima oscura · w blanco · g gris · '.' transparente.
export const COSTUMES = {
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

export const PAL = { k: '#111111', l: '#CCE673', L: '#94AA3D', w: '#FFFFFF', g: '#8A8A8A', c: '#F2F1EF' }
export const LOOK = {
  favor: { body: '#CCE673', face: '#111111', stripe: '#111111' },
  undecided: { body: '#FFFFFF', face: '#111111', stripe: '#111111' },
  against: { body: '#2A2A2A', face: '#F2F1EF', stripe: '#F2F1EF' },
}
// Si un complemento cae sobre el cuerpo y apenas contrasta con él, se cambia para que se vea:
// sobre lima, el lima pasa a tinta; sobre blanco, el blanco pasa a gris y el lima a lima oscuro;
// sobre tinta, la tinta pasa a crema.
export const ALT = {
  '#CCE673': { '#CCE673': PAL.k, '#94AA3D': PAL.k },
  '#FFFFFF': { '#FFFFFF': PAL.g, '#CCE673': PAL.L },
  '#2A2A2A': { '#111111': PAL.c, '#2A2A2A': PAL.c },
}


// ── Utilidades aleatorias ───────────────────────────────────────────────────
export const rand = (a, b, rng = Math.random) => a + rng() * (b - a)
export const pick = (arr, rng = Math.random) => arr[Math.floor(rng() * arr.length)]
export const pickWeighted = (arr, rng = Math.random) => {
  let n = rng() * arr.reduce((s, e) => s + e.w, 0)
  for (const e of arr) { if ((n -= e.w) <= 0) return e }
  return arr[0]
}
export const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5
// Desde el primer fotograma ya hay opiniones (≈ 15 % a favor, 7 % en contra): el color se lee sin esperar,
// y el lima empieza como acento, no como manto (crece con lo que ocurre ronda a ronda).
export const initialOpinion = () => {
  const r = Math.random()
  if (r < 0.15) return 0.45 + Math.random() * 0.35
  if (r < 0.22) return -(0.45 + Math.random() * 0.35)
  return gauss() * 0.18
}
export const randomLean = () => Math.max(-1, Math.min(1, gauss() * 1.6 + 0.12))


// Generador con semilla (mulberry32): la misma cadena da siempre la misma Bianka (avatares de proyectos).
export const seededRng = (seed) => {
  let h = 1779033703 ^ String(seed).length
  for (let i = 0; i < String(seed).length; i++) { h = Math.imul(h ^ String(seed).charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19) }
  let a = h >>> 0
  return () => {
    a = (a + 0x6D2B79F5) >>> 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
export const bucketOf = (o) => (o > 0.33 ? 'favor' : o < -0.33 ? 'against' : 'undecided')

const spriteCache = new Map()

// Una Bianka con el aspecto que se indique (orejas, gorro, cara, cuerpo), no aleatoria.
export const fixedLook = ({ ears = 'classic', head = null, face = null, body = null } = {}) => {
  const e = EARS.find(x => x.id === ears) || EARS[0]
  const find = (arr, id) => (id ? arr.find(c => c.id === id) || null : null)
  const h = find(COSTUMES.head, head), f = find(COSTUMES.face, face), b = find(COSTUMES.body, body)
  return { key: `fixed|${e.id}|${h?.id}|${f?.id}|${b?.id}`, ears: e, head: h, face: f, body: b, persona: (b || h || f)?.id || 'plain' }
}

// ── Construcción de cada Bianka ─────────────────────────────────────────────
// El salpicado (`spots`) añade ruido de alta frecuencia y no se lee a distancia: no entra en el sorteo.
const BODY_POOL = COSTUMES.body.filter(b => b.id !== 'spots')
export const makeLook = (rng = Math.random) => {
  // Cada Bianka lleva al menos un complemento (nunca un conejo liso): más variedad, ningún vecino idéntico.
  for (let tries = 0; tries < 8; tries++) {
    const face = rng() < 0.34 ? pick(COSTUMES.face, rng) : null
    const head = !face?.noHead && rng() < 0.94 ? pick(COSTUMES.head, rng) : null
    const body = rng() < 0.62 ? pick(BODY_POOL, rng) : null
    if (!face && !head && !body && tries < 7) continue
    const ears = pickWeighted(EARS, rng)
    // El rótulo del bocadillo sale del rasgo más visible
    const persona = (body || head || face)?.id || 'plain'
    return { key: `${ears.id}|${head?.id}|${face?.id}|${body?.id}`, ears, head, face, body, persona }
  }
}

export const spriteFor = (look, bucket, thick = false) => {
  const key = `${look.key}|${bucket}${thick ? '|t' : ''}`
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
        if (R >= 0 && R < GH && C >= 0 && C < GW && bodyMask[R][C]) color = ALT[colors.body]?.[color] || color
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
  // «habla»: el contorno de tinta se ensancha una celda más, para que quien habla destaque en el muro
  if (thick) {
    const have = new Set(outline.map(([r, c]) => `${r}:${c}`))
    const extra = []
    for (let r = 0; r < GH; r++) {
      for (let c = 0; c < GW; c++) {
        if (grid[r][c] || have.has(`${r}:${c}`)) continue
        let near = false
        for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) if (have.has(`${r + dr}:${c + dc}`)) { near = true; break }
        if (near) extra.push([r, c])
      }
    }
    outline.push(...extra)
  }
  // halo crema de una celda alrededor del contorno: al solaparse, cada Bianka se recorta limpia
  // sobre la de detrás (como una pegatina) en vez de fundirse con ella
  const ink = new Set(outline.map(([r, c]) => `${r}:${c}`))
  const halo = []
  for (let r = 0; r < GH; r++) {
    for (let c = 0; c < GW; c++) {
      if (grid[r][c] || ink.has(`${r}:${c}`)) continue
      let near = false
      for (let dr = -1; dr <= 1 && !near; dr++) for (let dc = -1; dc <= 1; dc++) if (ink.has(`${r + dr}:${c + dc}`)) { near = true; break }
      if (near) halo.push([r, c])
    }
  }
  const cv = document.createElement('canvas')
  cv.width = GW
  cv.height = GH
  const g = cv.getContext('2d')
  g.fillStyle = PAL.c
  for (const [r, c] of halo) g.fillRect(c, r, 1, 1)
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


// ── Cara y dibujo ────────────────────────────────────────────────────────────
// gaze = [gx, gy] en celdas (−1, 0, 1); blink/happy/talking son estados del momento.
export const drawFace = (ctx, { x, y, P, look, bucket, mirror = false, gaze = [0, 0], blink = false, happy = false, talking = false, now = 0 }) => {
  const items = [look.head, look.face, look.body].filter(Boolean)
  const screen = items.some(i => i.screen)
  const lock = items.some(i => i.lockEyes)
  const noEyes = items.find(i => i.noEyes)?.noEyes
  const colors = LOOK[bucket]
  const cell = (r, c) => {
    const cc = mirror ? mirrorCol(c) : c
    ctx.fillRect(x + cc * P, y + r * P, P, P)
  }
  let [gx, gy] = gaze
  if (mirror) gx = -gx
  if (lock) { gx = 0; gy = 0 }
  ctx.fillStyle = screen ? PAL.l : colors.face
  const eyes = [10, 15].filter((c, k) => !(noEyes === 'both' || (noEyes === 'right' && k === 1)))
  for (const c of eyes) {
    const ec = c + gx
    if (happy) { cell(15, ec - 1); cell(14, ec); cell(15, ec + 1) }
    else if (blink) cell(16, ec)
    else { cell(15 + gy, ec); cell(16 + gy, ec) }
  }
  // boca: cerrada en «T»; al hablar se abre y se cierra
  if (talking && Math.floor(now * 8) % 2 === 0) { cell(18, 12); cell(18, 13); cell(19, 12); cell(19, 13); cell(20, 12); cell(20, 13) }
  else { cell(18, 12); cell(18, 13); cell(19, 12) }
}

// Sprite + cara en (x, y) = esquina superior izquierda de la retícula de la Bianka.
export const drawBianka = (ctx, opts) => {
  const { x, y, P, look, bucket, mirror = false, thick = false } = opts
  const spr = spriteFor(look, bucket, thick)
  const sx = x - OX * P, sy = y - OY * P
  if (mirror) {
    ctx.save()
    ctx.translate(sx + GW * P, sy)
    ctx.scale(-1, 1)
    ctx.drawImage(spr, 0, 0, GW * P, GH * P)
    ctx.restore()
  } else {
    ctx.drawImage(spr, sx, sy, GW * P, GH * P)
  }
  drawFace(ctx, opts)
}
