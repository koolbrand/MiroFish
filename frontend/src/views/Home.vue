<template>
  <div class="home">
    <nav class="topbar">
      <router-link to="/" class="topbar-brand" :aria-label="$t('home.heroDescBrand')">
        <BrandLogo />
      </router-link>
      <div class="topbar-links">
        <AppVersion class="topbar-version tech-only" />
        <LanguageSwitcher />
        <HelpButton tourId="home" />
        <router-link to="/projects" class="nav-projects" data-tour="home-projects-link">
          {{ $t('nav.projects') }} <span class="arrow" aria-hidden="true">→</span>
        </router-link>
      </div>
    </nav>

    <main>
      <!-- Portada: un muro de Biankas de todo tipo que opinan, conversan y cambian
           de idea ronda a ronda; el mensaje va en una tarjeta en el centro -->
      <header class="stage" :style="{ '--readout-h': `${readoutH}px` }">
        <BiankaCrowd :avoid-el="stageCard" :bottom-inset="overlap" :top-inset="topInset" @readout="readoutH = $event" />
        <div ref="stageCard" class="stage-card">
          <p class="eyebrow"><span class="eyebrow-dot" aria-hidden="true"></span>{{ $t('home.tagline') }}</p>
          <h1 class="stage-title">
            <i18n-t keypath="home.stageTitleLine1" tag="span" class="line">
              <template #hl><span class="hl">{{ $t('home.stageTitleHl') }}</span></template>
            </i18n-t>
            <span class="line">{{ $t('home.stageTitleLine2') }}</span>
          </h1>
          <p class="stage-lede">
            <i18n-t keypath="home.stageLede" tag="span">
              <template #crowd><strong>{{ $t('home.stageLedeCrowd') }}</strong></template>
            </i18n-t>
          </p>
          <div class="stage-actions">
            <button type="button" class="btn btn-lime" @click="scrollToForm">
              {{ $t('home.heroCta') }} <span aria-hidden="true">↓</span>
            </button>
            <a href="#como-funciona" class="btn btn-outline">{{ $t('home.workflowSequence') }}</a>
          </div>
        </div>
      </header>

      <!-- El ensayo: el formulario monta sobre el borde de la portada -->
      <section id="ensayo" class="composer-wrap" :aria-label="$t('home.composerTitle')">
        <div class="composer">
          <header class="composer-head">
            <div>
              <span class="kicker">{{ $t('home.composerKicker') }}</span>
              <h2 class="composer-title">{{ $t('home.composerTitle') }}</h2>
            </div>
          </header>

          <div class="composer-grid">
            <div class="cstep">
              <div class="cstep-label"><span class="cstep-num">01</span>{{ $t('home.composerStep1') }}</div>
              <p class="cstep-hint">{{ $t('home.composerStep1Hint') }}</p>
              <div
                class="dropzone"
                data-tour="home-upload"
                role="button"
                tabindex="0"
                :aria-label="$t('home.dragToUpload')"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
                @keydown.enter.prevent="triggerFileInput"
                @keydown.space.prevent="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt,.png,.jpg,.jpeg,.webp,.gif"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                <div class="drop-inner">
                  <span class="drop-icon" aria-hidden="true">↑</span>
                  <span class="drop-title">{{ files.length ? $t('home.addMoreFiles') : $t('home.dragToUpload') }}</span>
                  <span class="drop-hint">{{ $t('home.orBrowse') }}</span>
                  <span class="drop-formats">{{ $t('home.supportedFormats') }}</span>
                </div>
              </div>
              <ul v-if="files.length" class="file-chips">
                <li v-for="(file, index) in files" :key="file.name + index" class="file-chip">
                  <span class="file-chip-name" :title="file.name">{{ file.name }}</span>
                  <button
                    type="button"
                    class="file-chip-remove"
                    :aria-label="$t('home.removeFile', { name: file.name })"
                    @click="removeFile(index)"
                  >×</button>
                </li>
              </ul>

              <!-- Plantilla, revisión con Jev y entrevista para el brief -->
              <BriefAssistant
                :files="files"
                :topic="formData.simulationRequirement"
                :disabled="loading"
                @add-file="file => addFiles([file])"
              />
            </div>

            <div class="cstep-col">
              <div class="cstep" data-tour="home-prompt">
                <label class="cstep-label" for="home-question"><span class="cstep-num">02</span>{{ $t('home.composerStep2') }}</label>
                <textarea
                  id="home-question"
                  ref="questionEl"
                  v-model="formData.simulationRequirement"
                  class="field field-question"
                  :placeholder="$t('home.promptPlaceholder')"
                  rows="5"
                  :disabled="loading"
                ></textarea>
                <div class="examples">
                  <span class="examples-label">{{ $t('home.examplesLabel') }}</span>
                  <button
                    v-for="ex in EXAMPLES"
                    :key="ex"
                    type="button"
                    class="example-chip"
                    :disabled="loading"
                    @click="useExample(ex)"
                  >{{ $t(`home.example${ex}Label`) }}</button>
                </div>
              </div>

              <div class="cstep" data-tour="home-project-name">
                <label class="cstep-label" for="home-name">
                  <span class="cstep-num">03</span>{{ $t('home.composerStep3') }}
                  <span class="optional">{{ $t('home.optional') }}</span>
                </label>
                <input
                  id="home-name"
                  v-model="formData.projectName"
                  type="text"
                  class="field"
                  :placeholder="$t('home.projectNamePlaceholder')"
                  maxlength="120"
                  :disabled="loading"
                />
              </div>
            </div>
          </div>

          <footer class="composer-foot">
            <!-- una Bianka que te guía: blanca mientras falta algo, lima y contenta cuando ya se puede lanzar -->
            <div class="composer-guide">
              <BiankaAvatar class="guide-face" :look="guideLook" :bucket="canSubmit ? 'favor' : 'undecided'" :happy="canSubmit" :headroom="8" :pixel="3" />
              <p class="composer-status" :class="{ ready: canSubmit }" aria-live="polite">
                {{ statusText }}
              </p>
            </div>
            <button
              class="launch-btn"
              data-tour="home-start"
              :disabled="!canSubmit || loading"
              @click="startSimulation"
            >
              {{ loading ? $t('home.initializing') : $t('home.startEngine') }}
              <span class="arrow" aria-hidden="true">→</span>
            </button>
          </footer>
        </div>
      </section>

      <!-- Cómo funciona: línea de tiempo que se dibuja al entrar -->
      <section id="como-funciona" class="section how">
        <div v-reveal class="section-head">
          <span class="kicker">{{ $t('home.workflowSequence') }}</span>
          <h2 class="section-title">
            <i18n-t keypath="home.howTitle" tag="span">
              <template #hl><span class="hl alt">{{ $t('home.howTitleHl') }}</span></template>
            </i18n-t>
          </h2>
        </div>
        <div ref="trackEl" class="track" :class="{ wide: isWide }">
          <div class="track-line" aria-hidden="true"><span class="track-fill"></span></div>
          <canvas ref="walkerEl" class="walker" aria-hidden="true"></canvas>
          <ol class="stations">
            <li
              v-for="n in 5"
              :key="n"
              :ref="el => (stationEls[n - 1] = el)"
              class="station"
              :class="{ reached: isReached(n - 1) }"
            >
              <div class="vignette"><BiankaScene :scene="SCENE_IDS[n - 1]" :active="isReached(n - 1)" /></div>
              <span class="station-num">0{{ n }}</span>
              <h3 class="station-title">{{ $t(`home.step0${n}Title`) }}</h3>
              <p class="station-desc">{{ $t(`home.step0${n}Desc`) }}</p>
            </li>
          </ol>
        </div>
      </section>

      <!-- Qué obtienes: la prueba tangible del resultado (informe de ejemplo) -->
      <section class="section results">
        <div v-reveal class="section-head">
          <span class="kicker">{{ $t('home.resultsKicker') }}</span>
          <h2 class="section-title wide">{{ $t('home.resultsTitle') }}</h2>
        </div>
        <div class="results-grid">
          <ul v-reveal class="deliverables">
            <li v-for="n in 4" :key="n">
              <strong>{{ $t(`home.deliverable${n}Title`) }}</strong>
              <span>{{ $t(`home.deliverable${n}Desc`) }}</span>
            </li>
          </ul>
          <ReportExample />
        </div>
      </section>

      <!-- Cifras medidas, banda lima a sangre -->
      <section class="figures" :aria-label="$t('home.figuresLabel')">
        <div class="figures-peek" aria-hidden="true"><BiankaRow mood="mix" :pixel="3" :visible-px="66" /></div>
        <ul class="figures-grid">
          <li v-for="f in figures" :key="f.label" class="figure">
            <span class="figure-value"><CountUp :value="f.value" /></span>
            <span v-if="f.unit" class="figure-unit">{{ f.unit }}</span>
            <span class="figure-label">{{ f.label }}</span>
          </li>
        </ul>
      </section>

      <section class="section projects">
        <HistoryDatabase />
      </section>

      <section class="closing">
        <h2 class="closing-title">
          {{ $t('home.closingTitle') }}
          <span class="hl">{{ $t('home.closingHl') }}</span>
        </h2>
        <button type="button" class="btn btn-lime" @click="scrollToForm">
          {{ $t('home.heroCta') }} <span aria-hidden="true">↑</span>
        </button>
        <div class="closing-crowd" aria-hidden="true"><BiankaRow mood="favor" :pixel="4" :visible-px="104" /></div>
      </section>
    </main>

    <footer class="site-footer">
      <span class="footer-tag"><BiankaAvatar :look="{ ears: 'up', head: 'cap', body: 'scarf' }" bucket="favor" :pixel="2" />{{ $t('home.footerTagline') }}</span>
      <a class="footer-by" href="https://koolbrand.com" target="_blank" rel="noopener">
        {{ $t('home.footerBy') }}
        <img src="/brand/koolbrand-logo-negativo-sin-claim.svg" alt="Koolbrand" width="112" height="22" />
      </a>
    </footer>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import BriefAssistant from '../components/BriefAssistant.vue'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import AppVersion from '../components/AppVersion.vue'
import BrandLogo from '../components/BrandLogo.vue'
import HelpButton from '../components/HelpButton.vue'
import BiankaCrowd from '../components/BiankaCrowd.vue'
import ReportExample from '../components/ReportExample.vue'
import BiankaRow from '../components/BiankaRow.vue'
import BiankaAvatar from '../components/BiankaAvatar.vue'
import CountUp from '../components/CountUp.vue'
import BiankaScene from '../components/BiankaScene.vue'
import { fixedLook, drawBianka } from '../lib/biankaSprite'
import { vReveal } from '../composables/useReveal'
import { useTutorial } from '../composables/useTutorial'
import { getTour } from '../tours/tours'

const { t } = useI18n()
const router = useRouter()
const { maybeAutoStart } = useTutorial()

// Alto con el que la tarjeta del formulario monta sobre la portada (px).
const overlap = ref(72)
const readoutH = ref(150)              // alto del marcador de la portada (lo mide BiankaCrowd)
const topInset = ref(88)               // barra flotante: nadie habla debajo
const stageCard = ref(null)
const questionEl = ref(null)

const EXAMPLES = ['Launch', 'Price', 'Campaign', 'Crisis']

// Cifras medidas: el número se anima, la unidad («min») va aparte y más pequeña.
const splitFigure = (s) => {
  // «20–30 min» → «20–30» + «min»; «10–120» → «10–120»
  const m = String(s).match(/^(\d[\d.,]*(?:\s*[–-]\s*\d[\d.,]*)?)\s*(.*)$/)
  return m ? { value: m[1].trim(), unit: (m[2] || '').trim() } : { value: s, unit: '' }
}
const figures = computed(() => [
  { value: '20–30', unit: t('home.figureUnitMinutes'), label: t('home.metricLowCostDesc') },
  { value: '10–120', unit: t('home.figureUnitPeople'), label: t('home.metricHighAvailDesc') },
  { value: '2', unit: t('home.figureUnitNetworks'), label: t('home.figurePlatformsDesc') },
  { value: '5', unit: t('home.figureUnitSteps'), label: t('home.figureStepsDesc') },
])

onMounted(async () => {
  await nextTick()
  overlap.value = window.innerWidth <= 640 ? 56 : 72
  topInset.value = window.innerWidth <= 640 ? 76 : 88
  // Tutorial automático en la primera visita (se reabre con el botón «?»).
  maybeAutoStart('home', getTour('home'))
})


// ── «Cómo funciona»: una Bianka camina por la línea del proceso según bajas ─────
const SCENE_IDS = ['read', 'build', 'talk', 'report', 'chat']
const trackEl = ref(null)
const walkerEl = ref(null)
const stationEls = []
const progress = ref(0)              // 0..1 según el scroll
const isWide = ref(true)
const seen = ref([false, false, false, false, false])
const reduceMotion = typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
// Un paso está «alcanzado» cuando llega la Bianka (escritorio) o cuando entra en pantalla (móvil).
const isReached = (i) => reduceMotion || (isWide.value ? progress.value >= i / 4 - 0.02 : seen.value[i])

const WALK_P = 2
const walkerLook = fixedLook({ ears: 'up', head: 'cap', body: 'scarf' })
const guideLook = { ears: 'up', face: 'glasses', body: 'bowtie' }   // la Bianka que guía en el formulario
let wctx = null, wW = 0, wH = 76, wdpr = 1, wraf = null, wVisible = false, pos = 0
let scrollRaf = null, mq = null, io = null, trackIO = null

const stationX = (i) => i * (wW / 5) + 7 - 13 * WALK_P          // esquina izquierda del sprite sobre el punto del paso
const updateProgress = () => {
  scrollRaf = null
  const el = trackEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  progress.value = Math.min(1, Math.max(0, (window.innerHeight * 0.8 - r.top) / 560))
}
const onScroll = () => { if (!scrollRaf) scrollRaf = requestAnimationFrame(updateProgress) }

const sizeWalker = () => {
  const cv = walkerEl.value, tr = trackEl.value
  if (!cv || !tr) return
  wW = tr.clientWidth
  wdpr = Math.min(window.devicePixelRatio || 1, 2)
  cv.width = Math.round(wW * wdpr); cv.height = Math.round(wH * wdpr)
  wctx = cv.getContext('2d'); wctx.setTransform(wdpr, 0, 0, wdpr, 0, 0); wctx.imageSmoothingEnabled = false
}
const walkerTick = () => {
  wraf = null
  if (!wVisible || !wctx || !isWide.value) return
  const x0 = stationX(0), span = stationX(4) - x0
  const target = span * progress.value
  const diff = target - pos
  const walking = Math.abs(diff) > 0.6
  pos = walking ? pos + diff * 0.14 : target
  const t = performance.now() / 1000
  wctx.clearRect(0, 0, wW, wH)
  wctx.imageSmoothingEnabled = false
  // camina a saltitos; parada, respira
  const hop = walking ? (Math.floor(t / 0.16) % 2) * WALK_P : ((t / 1.4) % 1 < 0.5 ? 0 : WALK_P)
  drawBianka(wctx, {
    x: x0 + pos, y: wH - 29 * WALK_P - 4 - hop, P: WALK_P, look: walkerLook, bucket: 'favor',
    mirror: diff < -0.6, now: t, gaze: [diff < -0.6 ? -1 : 1, 0], blink: (t % 3.4) > 3.25, happy: !walking && progress.value >= 0.995, talking: false,
  })
  trackEl.value?.style.setProperty('--fill', `${x0 + pos + 13 * WALK_P}px`)
  wraf = requestAnimationFrame(walkerTick)
}
const startWalker = () => { if (!wraf && wVisible && isWide.value && !reduceMotion) wraf = requestAnimationFrame(walkerTick) }

const layoutMode = () => {
  isWide.value = window.innerWidth > 900
  sizeWalker()
  updateProgress()
  startWalker()
}

onMounted(() => {
  mq = () => layoutMode()
  window.addEventListener('resize', mq, { passive: true })
  window.addEventListener('scroll', onScroll, { passive: true })
  layoutMode()
  if (reduceMotion) {
    trackEl.value?.style.setProperty('--fill', '100%')
  } else {
    trackIO = new IntersectionObserver(([e]) => { wVisible = e.isIntersecting; if (wVisible) startWalker() }, { rootMargin: '120px' })
    trackIO.observe(trackEl.value)
    // en móvil (sin caminante) cada paso se activa al entrar en pantalla
    io = new IntersectionObserver((entries) => entries.forEach((e) => {
      const i = stationEls.indexOf(e.target)
      if (e.isIntersecting && i >= 0 && !seen.value[i]) { const a = [...seen.value]; a[i] = true; seen.value = a }
    }), { threshold: 0.35 })
    stationEls.forEach(el => el && io.observe(el))
  }
})
onUnmounted(() => {
  window.removeEventListener('resize', mq)
  window.removeEventListener('scroll', onScroll)
  if (wraf) cancelAnimationFrame(wraf)
  if (scrollRaf) cancelAnimationFrame(scrollRaf)
  io?.disconnect(); trackIO?.disconnect()
})

// ── Formulario ──────────────────────────────────────────────────────────────
const formData = ref({
  simulationRequirement: '',
  projectName: ''
})
const files = ref([])
const loading = ref(false)
const isDragOver = ref(false)
const fileInput = ref(null)

const canSubmit = computed(() =>
  formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
)

const statusText = computed(() => {
  if (canSubmit.value) {
    return files.value.length === 1
      ? t('home.readyOne')
      : t('home.readyMany', { n: files.value.length })
  }
  return t('home.startHint')
})

const triggerFileInput = () => {
  if (!loading.value) fileInput.value?.click()
}

const handleFileSelect = (event) => {
  addFiles(Array.from(event.target.files))
  // Permite volver a elegir el mismo archivo tras quitarlo.
  event.target.value = ''
}

const handleDragOver = () => {
  if (!loading.value) isDragOver.value = true
}

const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  addFiles(Array.from(e.dataTransfer.files))
}

const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt', 'png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)
  })
  files.value.push(...validFiles)
}

const removeFile = (index) => {
  files.value.splice(index, 1)
}

// Rellena la pregunta con un ejemplo y deja el cursor al final para editarlo.
const useExample = (key) => {
  formData.value.simulationRequirement = t(`home.example${key}`)
  nextTick(() => {
    const el = questionEl.value
    if (!el) return
    el.focus()
    el.setSelectionRange(el.value.length, el.value.length)
  })
}

const scrollToForm = () => {
  document.getElementById('ensayo')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Pasa al asistente: la subida y la llamada a la API se hacen en Process.
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(
      files.value,
      formData.value.simulationRequirement,
      (formData.value.projectName || '').trim()
    )
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
.home {
  --gutter: clamp(16px, 4vw, 48px);
  --overlap: 72px;
  --stage-bg: #0B0B0B;
  min-height: 100vh;
  background: var(--kb-bg);
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
}

/* ── Barra superior ─────────────────────────────────────────────────────── */
.topbar {
  position: fixed;
  top: 14px;
  inset-inline: 0;
  margin-inline: auto;
  z-index: 50;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: min(calc(100% - 2 * var(--gutter)), 1144px);
  height: 58px;
  padding-inline: 22px 20px;
  background: rgba(247, 246, 243, 0.94);
  backdrop-filter: saturate(1.4) blur(10px);
  -webkit-backdrop-filter: saturate(1.4) blur(10px);
  border: 2px solid var(--ink-950);
  border-radius: 999px;
  box-shadow: 4px 4px 0 var(--ink-950);
}
.topbar-brand {
  font-size: 1.4rem;
  color: var(--kb-text);
  text-decoration: none;
}
.topbar-links {
  display: flex;
  align-items: center;
  gap: 12px 20px;
}
.nav-projects {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 2px;
  font-weight: 600;
  color: var(--kb-text);
  text-decoration: none;
  white-space: nowrap;
}
.nav-projects .arrow { transition: transform 0.2s ease; }
.nav-projects:hover .arrow { transform: translateX(3px); }
.nav-projects:hover { text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 6px; }

/* ── Portada ────────────────────────────────────────────────────────────── */
.stage {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: grid;
  align-items: center;
  justify-items: center;
  min-height: max(640px, calc(100svh + var(--overlap)));
  /* abajo se reserva el hueco del marcador (su alto real + aire), para que la tarjeta nunca lo pise */
  padding: clamp(96px, 13vh, 132px) var(--gutter) calc(var(--overlap) + var(--readout-h, 150px) + 40px);
  background: var(--cream-100);
  color: var(--kb-text);
}
.closing :focus-visible,
.site-footer :focus-visible { outline-color: var(--lime-500); }

.stage-card {
  position: relative;
  z-index: 2;
  box-sizing: border-box;
  width: min(760px, 100%);
  padding: clamp(28px, 4.5vw, 52px) clamp(20px, 4vw, 56px);
  background: var(--kb-surface);
  border: 2px solid var(--ink-950);
  border-radius: 18px;
  box-shadow: 8px 8px 0 var(--ink-950);
  text-align: center;
  animation: rise 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) 0.1s both;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 20px;
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--kb-accent-text);
}
.eyebrow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lime-700);
  animation: live 2s ease-out infinite;
}
.stage-title {
  margin: 0;
  font-size: clamp(2.5rem, 7vw, 5rem);
  font-weight: 800;
  line-height: 0.98;
  letter-spacing: -0.045em;
  color: var(--kb-text);
  text-wrap: balance;
}
.stage-title .line { display: block; }
.stage-title .hl {
  padding: 0 0.12em 0.06em;
  border-radius: 0.08em;
  animation: stamp 0.55s cubic-bezier(0.3, 1.4, 0.5, 1) 0.75s both;
}
.stage-lede {
  max-width: 50ch;
  margin: 24px auto 0;
  font-size: clamp(1rem, 1.4vw, 1.15rem);
  line-height: 1.55;
  color: var(--kb-text-2);
  text-wrap: pretty;
}
.stage-lede strong { color: var(--kb-text); font-weight: 700; }
.stage-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 32px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 16px 26px;
  border-radius: 10px;
  font: 600 1rem/1 var(--kb-font-sans);
  text-decoration: none;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}
.btn-lime {
  background: var(--lime-500);
  color: var(--ink-950);
  border: 1px solid var(--lime-500);
}
.btn-lime:hover { background: var(--lime-600); border-color: var(--lime-600); transform: translate(-1px, -1px); box-shadow: 3px 3px 0 var(--ink-950); }
.btn-outline {
  background: var(--kb-surface);
  color: var(--kb-text);
  border: 1px solid var(--kb-line-strong);
}
.btn-outline:hover { border-color: var(--ink-950); background: var(--cream-100); transform: translate(-1px, -1px); box-shadow: 3px 3px 0 var(--ink-950); }
.btn:active { transform: none; box-shadow: none; }

/* ── Formulario ─────────────────────────────────────────────────────────── */
.composer-wrap {
  position: relative;
  z-index: 3;
  margin-top: calc(-1 * var(--overlap));
  padding-inline: var(--gutter);
  scroll-margin-top: 88px;
}
.composer {
  max-width: 1160px;
  margin: 0 auto;
  padding: clamp(24px, 4vw, 48px);
  background: var(--kb-surface);
  border-radius: 20px;
  box-shadow: 0 50px 100px -50px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(17, 17, 17, 0.06);
  animation: rise 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) 0.5s both;
}
.composer-head { margin-bottom: 32px; }
.kicker {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--kb-accent-text);
}
.composer-title {
  margin: 8px 0 0;
  font-size: clamp(1.6rem, 2.8vw, 2.35rem);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.03em;
  text-wrap: balance;
}
.composer-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 40px 48px;
}
.cstep-col { display: grid; align-content: start; gap: 28px; }
.cstep-label {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--kb-text);
}
.cstep-num {
  padding: 3px 7px;
  border-radius: 6px;
  background: var(--ink-950);
  color: var(--lime-500);
  font-family: var(--kb-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
}
.optional { font-size: 0.85rem; font-weight: 500; color: var(--kb-muted); }
.cstep-hint {
  margin: -2px 0 12px;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--kb-muted);
  text-wrap: pretty;
}

.dropzone {
  display: grid;
  place-items: center;
  min-height: 176px;
  padding: 24px;
  border: 1.5px dashed var(--kb-line-strong);
  border-radius: 14px;
  background: var(--kb-surface-2);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.dropzone:hover,
.dropzone.drag-over { border-color: var(--lime-700); background: var(--lime-50); }
.dropzone.has-files { min-height: 120px; }
.drop-inner { display: grid; justify-items: center; gap: 6px; }
.drop-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: 6px;
  border-radius: 50%;
  background: var(--ink-950);
  color: var(--lime-500);
  font-size: 1.2rem;
  transition: transform 0.2s ease;
}
.dropzone:hover .drop-icon,
.dropzone.drag-over .drop-icon { transform: translateY(-3px); }
.drop-title { font-size: 1rem; font-weight: 600; }
.drop-hint { font-size: 0.88rem; color: var(--kb-muted); }
.drop-formats {
  margin-top: 6px;
  font-family: var(--kb-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--kb-subtle);
}
.file-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}
.file-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 4px 4px 4px 12px;
  border: 1px solid var(--lime-600);
  border-radius: 999px;
  background: var(--lime-50);
  font-size: 0.85rem;
}
.file-chip-name {
  overflow: hidden;
  max-width: 260px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-chip-remove {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--kb-text-2);
  font-size: 1.05rem;
  line-height: 1;
  cursor: pointer;
}
.file-chip-remove:hover { background: rgba(17, 17, 17, 0.08); }

.field {
  box-sizing: border-box;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--kb-line-strong);
  border-radius: 12px;
  background: var(--kb-surface);
  color: var(--kb-text);
  font: 400 1rem/1.5 var(--kb-font-sans);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.field::placeholder { color: var(--kb-subtle); }
.field:focus { outline: none; border-color: var(--ink-950); box-shadow: 0 0 0 3px rgba(204, 230, 115, 0.7); }
.field:disabled { background: var(--kb-surface-2); cursor: not-allowed; }
.field-question { min-height: 150px; resize: vertical; font-size: 1.05rem; }
.examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.examples-label { flex-basis: 100%; margin-bottom: -2px; font-size: 0.85rem; color: var(--kb-muted); }   /* la etiqueta va sola arriba: los cuatro ejemplos caben en una fila */
.example-chip {
  padding: 8px 12px;
  border: 1px solid var(--kb-line-strong);
  border-radius: 999px;
  background: var(--kb-surface);
  color: var(--kb-text);
  font: 500 0.85rem/1 var(--kb-font-sans);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.example-chip:hover:not(:disabled) { border-color: var(--ink-950); background: var(--lime-50); }
.example-chip:disabled { opacity: 0.5; cursor: not-allowed; }

.composer-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px 24px;
  margin-top: 36px;
  padding-top: 24px;
  border-top: 1px solid var(--kb-line);
}
.composer-guide { display: flex; align-items: center; gap: 14px; flex: 1 1 320px; min-width: 0; }
.guide-face { flex: none; }
.composer-status {
  max-width: 52ch;
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.5;
  color: var(--kb-muted);
  text-wrap: pretty;
}
.composer-status.ready { color: var(--kb-accent-text); font-weight: 600; }
.launch-btn {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  padding: 18px 30px;
  border: none;
  border-radius: 12px;
  background: var(--lime-500);
  color: var(--ink-950);
  font: 700 1.05rem/1 var(--kb-font-sans);
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}
.launch-btn .arrow { transition: transform 0.2s ease; }
.launch-btn:hover:not(:disabled) { background: var(--lime-600); transform: translateY(-1px); }
.launch-btn:hover:not(:disabled) .arrow { transform: translateX(4px); }
.launch-btn:disabled { background: var(--gray-100); color: var(--gray-600); cursor: not-allowed; }

/* ── Secciones ──────────────────────────────────────────────────────────── */
.section {
  max-width: 1240px;
  margin: 0 auto;
  padding: clamp(96px, 12vw, 168px) var(--gutter) 0;
}
.section-title {
  max-width: 18ch;
  margin: 12px 0 0;
  font-size: clamp(2.2rem, 5.2vw, 4.4rem);
  font-weight: 800;
  line-height: 1.02;
  letter-spacing: -0.04em;
  text-wrap: balance;
}
.section-title.wide { max-width: 26ch; }
.section-title.small { font-size: clamp(2rem, 3.8vw, 3.2rem); }

.track { position: relative; margin-top: 96px; }
.track-line {
  position: absolute;
  inset-inline: 0;
  top: 6px;
  height: 2px;
  background: var(--ink-950);
}
/* el tramo ya recorrido se rellena de lima detrás de la línea */
.track-fill {
  position: absolute;
  inset-block: -3px;
  inset-inline-start: 0;
  width: var(--fill, 0px);
  border-radius: 4px;
  background: var(--lime-500);
}
.walker {
  position: absolute;
  inset-inline: 0;
  top: -66px;
  width: 100%;
  height: 76px;
  pointer-events: none;
  image-rendering: pixelated;
}
.stations {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  list-style: none;
}
.station {
  position: relative;
  padding-block-start: 38px;
  padding-inline-end: 20px;
}
.station::before {
  content: '';
  position: absolute;
  top: 0;
  inset-inline-start: 0;
  box-sizing: border-box;
  width: 14px;
  height: 14px;
  border: 2px solid var(--ink-950);
  border-radius: 50%;
  background: var(--kb-surface);
  transition: background 0.25s ease;
}
.station.reached::before { background: var(--lime-500); }
.vignette {
  margin: 0 0 18px;
  padding: 10px 0;
  border: 2px solid var(--ink-950);
  border-radius: 12px;
  background:
    radial-gradient(rgba(17, 17, 17, 0.09) 1px, transparent 1.5px) 0 0 / 12px 12px,
    var(--kb-surface);
  box-shadow: 4px 4px 0 var(--ink-950);
  overflow: hidden;
}
.station-num {
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--kb-muted);
}
.station-title {
  margin: 10px 0 8px;
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.01em;
}
.station-desc {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--kb-text-2);
  text-wrap: pretty;
}

.results-grid {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  align-items: start;
  gap: 48px clamp(40px, 6vw, 88px);
  margin-top: 56px;
}
.deliverables {
  display: grid;
  gap: 20px;
  margin: 36px 0 0;
  padding: 0;
  list-style: none;
}
.deliverables li {
  display: grid;
  gap: 4px;
  padding-inline-start: 18px;
  border-inline-start: 3px solid var(--lime-500);
}
.deliverables strong { font-size: 1.05rem; }
.deliverables span { font-size: 0.95rem; line-height: 1.5; color: var(--kb-text-2); text-wrap: pretty; }

.figures {
  margin-top: clamp(96px, 12vw, 168px);
  padding: clamp(56px, 8vw, 104px) var(--gutter);
  background: var(--lime-500);
  color: var(--ink-950);
}
/* Biankas que asoman por el borde superior de la banda (sus cuerpos quedan «detrás» de ella) */
.figures { position: relative; }
.figures-peek { position: absolute; inset-inline: 0; bottom: 100%; height: 66px; pointer-events: auto; }
.figures-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 40px 32px;
  max-width: min(1144px, 100%);
  margin: 0 auto;
  padding: 0;
  list-style: none;
}
.figure {
  /* la cifra se dimensiona con su columna, no con la pantalla: así nunca invade la de al lado */
  container-type: inline-size;
  display: grid;
  align-content: start;
  gap: 12px;
  padding-top: 20px;
  border-top: 2px solid var(--ink-950);
}
.figure-value {
  display: block;
  font-size: min(4.8rem, 23cqi);
  font-weight: 800;
  line-height: 0.95;
  letter-spacing: -0.02em;
  white-space: nowrap;
}
.figure-unit {
  display: block;
  margin-block-start: 10px;
  font-family: var(--kb-font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-800);
}
.figure-label {
  max-width: 26ch;
  font-size: 0.98rem;
  font-weight: 500;
  line-height: 1.45;
  color: var(--ink-800);
  text-wrap: pretty;
}

.projects { padding-bottom: 0; }

.closing {
  margin-top: clamp(96px, 12vw, 168px);
  padding: clamp(96px, 14vw, 200px) var(--gutter);
  background:
    radial-gradient(70% 60% at 50% 100%, rgba(204, 230, 115, 0.1) 0%, rgba(204, 230, 115, 0) 70%),
    var(--stage-bg);
  color: var(--cream-100);
  text-align: center;
}
.closing { position: relative; overflow: hidden; padding-bottom: clamp(190px, 20vw, 260px); }
.closing-crowd { position: absolute; inset-inline: 0; bottom: 0; height: 104px; }
.footer-tag { display: inline-flex; align-items: center; gap: 12px; }
.closing-title {
  max-width: 16ch;
  margin: 0 auto 48px;
  font-size: clamp(2.6rem, 7.4vw, 7rem);
  font-weight: 800;
  line-height: 0.98;
  letter-spacing: -0.045em;
  text-wrap: balance;
}
.closing-title .hl { margin-top: 0.12em; padding: 0 0.12em 0.06em; }

.site-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 28px var(--gutter);
  border-top: 1px solid rgba(242, 241, 239, 0.1);
  background: var(--stage-bg);
  color: rgba(242, 241, 239, 0.66);
  font-size: 0.88rem;
}
.footer-by {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: inherit;
  text-decoration: none;
}
.footer-by img { display: block; width: auto; height: 22px; }
.footer-by:hover { color: var(--cream-100); }

@keyframes rise {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: none; }
}
@keyframes stamp {
  from { opacity: 0; transform: rotate(-1.4deg) scale(0.7); }
  to { opacity: 1; transform: rotate(-1.4deg) scale(1); }
}
@keyframes live {
  0% { box-shadow: 0 0 0 0 rgba(204, 230, 115, 0.55); }
  100% { box-shadow: 0 0 0 10px rgba(204, 230, 115, 0); }
}

/* ── Adaptación ─────────────────────────────────────────────────────────── */
/* con la tarjeta ocupando casi todo el ancho, el muro solo tiene hueco arriba y abajo */
@media (max-width: 1240px) {
  /* y el marcador de la simulación pasa a ocupar su propia franja bajo la tarjeta */
  .stage { padding-top: 190px; }
}
@media (min-width: 700px) and (max-width: 1240px) {
  /* tarjeta más estrecha: deja franjas de muro a los lados con sitio para los bocadillos */
  .stage-card { width: min(640px, 100%); }
  .stage-title { font-size: clamp(2.3rem, 6vw, 4.4rem); }
}
@media (max-width: 1180px) {
  .figures-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 48px 40px; }
}
@media (max-width: 960px) {
  .results-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (min-width: 641px) and (max-height: 820px) {
  /* pantallas bajas (portátiles de 720–800 px): tarjeta compacta, todo cabe sin bajar */
  .stage { padding-top: clamp(88px, 12vh, 132px); }
  .stage-card { padding: 28px clamp(20px, 4vw, 48px) 26px; }
  .eyebrow { margin-bottom: 14px; }
  .stage-title { font-size: clamp(2.3rem, 5.4vw, 3.9rem); }
  .stage-lede { margin-top: 16px; font-size: 1rem; }
  .stage-actions { margin-top: 22px; }
}
@media (min-width: 641px) and (max-width: 1240px) and (max-height: 820px) {
  .stage { padding-top: 150px; }
}
@media (max-width: 900px) {
  .composer-grid { grid-template-columns: minmax(0, 1fr); }
  .track { margin-top: 48px; }
  .walker, .track-fill { display: none; }
  .track-line { inset-inline: auto; inset-inline-start: 6px; inset-block: 0; width: 2px; height: auto; }
  .stations { grid-template-columns: minmax(0, 1fr); }
  .station { padding-block: 0 40px; padding-inline: 40px 0; }
  .station::before { top: 2px; }
}
@media (max-width: 640px) {
  .home { --overlap: 56px; }
  .topbar { top: 10px; height: 52px; padding-inline: 16px 14px; width: calc(100% - 20px); }
  /* la tarjeta baja: todo el aire queda encima, en el muro, donde caben los bocadillos */
  .stage { padding-top: 96px; align-items: end; }
  .stage-card { padding: 24px 18px 22px; }
  .eyebrow { font-size: 11px; letter-spacing: 0.08em; margin-bottom: 14px; }
  .stage-title { font-size: 2.35rem; }
  .stage-lede { font-size: 0.98rem; margin-top: 16px; }
  .stage-actions { flex-direction: column; margin-top: 22px; }
  .stage-actions .btn { width: 100%; justify-content: center; }
  .topbar-version { display: none; }
  .topbar-links { gap: 10px; }
  .launch-btn { width: 100%; justify-content: center; }
}
@media (max-width: 480px) {
  .figures-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 400px) {
  /* móviles estrechos: la píldora de navegación tiene que caber entera */
  .topbar { padding-inline: 12px 10px; }
  .topbar-brand { font-size: 1.25rem; }
  .topbar-links { gap: 8px; }
  .nav-projects { gap: 4px; font-size: 0.95rem; }
}
@media (max-width: 340px) {
  .nav-projects .arrow { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .eyebrow-dot, .stage-card, .stage-title .hl, .composer { animation: none; }
  .station::before { transition: none; }
}
</style>
