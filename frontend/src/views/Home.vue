<template>
  <div class="home">
    <nav class="topbar">
      <router-link to="/" class="topbar-brand" :aria-label="$t('home.heroDescBrand')">
        <BrandLogo />
      </router-link>
      <div class="topbar-links">
        <AppVersion class="topbar-version" />
        <LanguageSwitcher />
        <HelpButton tourId="home" />
        <router-link to="/projects" class="nav-projects" data-tour="home-projects-link">
          {{ $t('nav.projects') }} <span class="arrow" aria-hidden="true">→</span>
        </router-link>
      </div>
    </nav>

    <main>
      <!-- Portada: la multitud de ejemplo reacciona ronda a ronda detrás del titular -->
      <header class="stage">
        <CrowdCanvas :quiet-el="stageInner" :bottom-inset="overlap" />
        <div ref="stageInner" class="stage-inner">
          <p class="eyebrow" data-quiet><span class="eyebrow-dot" aria-hidden="true"></span>{{ $t('home.tagline') }}</p>
          <h1 class="stage-title">
            <i18n-t keypath="home.stageTitleLine1" tag="span" class="line" data-quiet>
              <template #hl><span class="hl">{{ $t('home.stageTitleHl') }}</span></template>
            </i18n-t>
            <span class="line" data-quiet>{{ $t('home.stageTitleLine2') }}</span>
          </h1>
          <p class="stage-lede" data-quiet>
            <i18n-t keypath="home.stageLede" tag="span">
              <template #crowd><strong>{{ $t('home.stageLedeCrowd') }}</strong></template>
            </i18n-t>
          </p>
          <div class="stage-actions" data-quiet>
            <button type="button" class="btn btn-lime" @click="scrollToForm">
              {{ $t('home.heroCta') }} <span aria-hidden="true">↓</span>
            </button>
            <a href="#como-funciona" class="btn btn-outline-light">{{ $t('home.workflowSequence') }}</a>
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
            <p class="composer-status" :class="{ ready: canSubmit }" aria-live="polite">
              {{ statusText }}
            </p>
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
        <ol v-reveal class="rail">
          <li v-for="n in 5" :key="n" class="station" :style="{ '--i': n - 1 }">
            <span class="station-num">0{{ n }}</span>
            <h3 class="station-title">{{ $t(`home.step0${n}Title`) }}</h3>
            <p class="station-desc">{{ $t(`home.step0${n}Desc`) }}</p>
          </li>
        </ol>
      </section>

      <!-- Qué obtienes: entregables + gráfico de ejemplo animado -->
      <section class="section results">
        <div class="results-grid">
          <div v-reveal class="results-copy">
            <span class="kicker">{{ $t('home.resultsKicker') }}</span>
            <h2 class="section-title small">{{ $t('home.resultsTitle') }}</h2>
            <ul class="deliverables">
              <li v-for="n in 4" :key="n">
                <strong>{{ $t(`home.deliverable${n}Title`) }}</strong>
                <span>{{ $t(`home.deliverable${n}Desc`) }}</span>
              </li>
            </ul>
          </div>
          <OpinionChart />
        </div>
      </section>

      <!-- Cifras medidas, banda lima a sangre -->
      <section class="figures" :aria-label="$t('home.figuresLabel')">
        <ul class="figures-grid">
          <li v-for="f in figures" :key="f.label" class="figure">
            <span class="figure-value"><CountUp :value="f.value" /><span v-if="f.unit" class="figure-unit">{{ f.unit }}</span></span>
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
      </section>
    </main>

    <footer class="site-footer">
      <span>{{ $t('home.footerTagline') }}</span>
      <a class="footer-by" href="https://koolbrand.com" target="_blank" rel="noopener">
        {{ $t('home.footerBy') }}
        <img src="/brand/koolbrand-logo-negativo-sin-claim.svg" alt="Koolbrand" width="112" height="22" />
      </a>
    </footer>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import BriefAssistant from '../components/BriefAssistant.vue'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import AppVersion from '../components/AppVersion.vue'
import BrandLogo from '../components/BrandLogo.vue'
import HelpButton from '../components/HelpButton.vue'
import CrowdCanvas from '../components/CrowdCanvas.vue'
import OpinionChart from '../components/OpinionChart.vue'
import CountUp from '../components/CountUp.vue'
import { vReveal } from '../composables/useReveal'
import { useTutorial } from '../composables/useTutorial'
import { getTour } from '../tours/tours'

const { t } = useI18n()
const router = useRouter()
const { maybeAutoStart } = useTutorial()

// Alto con el que la tarjeta del formulario monta sobre la portada (px).
const overlap = ref(150)
const stageInner = ref(null)
const questionEl = ref(null)

const EXAMPLES = ['Launch', 'Price', 'Campaign', 'Crisis']

// Cifras medidas: el número se anima, la unidad («min») va aparte y más pequeña.
const splitFigure = (s) => {
  // «20–30 min» → «20–30» + «min»; «10–120» → «10–120»
  const m = String(s).match(/^(\d[\d.,]*(?:\s*[–-]\s*\d[\d.,]*)?)\s*(.*)$/)
  return m ? { value: m[1].trim(), unit: (m[2] || '').trim() } : { value: s, unit: '' }
}
const figures = computed(() => [
  { ...splitFigure(t('home.metricLowCost')), label: t('home.metricLowCostDesc') },
  { ...splitFigure(t('home.metricHighAvail')), label: t('home.metricHighAvailDesc') },
  { value: '2', unit: '', label: t('home.figurePlatformsDesc') },
  { value: '5', unit: '', label: t('home.figureStepsDesc') },
])

onMounted(async () => {
  await nextTick()
  overlap.value = window.innerWidth <= 640 ? 96 : 150
  // Tutorial automático en la primera visita (se reabre con el botón «?»).
  maybeAutoStart('home', getTour('home'))
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
  --overlap: 150px;
  --stage-bg: #0B0B0B;
  min-height: 100vh;
  background: var(--kb-bg);
  color: var(--kb-text);
  font-family: var(--kb-font-sans);
}

/* ── Barra superior ─────────────────────────────────────────────────────── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 64px;
  padding-inline: var(--gutter);
  background: rgba(242, 241, 239, 0.88);
  backdrop-filter: saturate(1.4) blur(12px);
  -webkit-backdrop-filter: saturate(1.4) blur(12px);
  border-bottom: 1px solid var(--kb-line);
}
.topbar-brand {
  font-size: 1.55rem;
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

/* ── Portada ────────────────────────────────────────────────────────────── */
.stage {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: grid;
  align-items: center;
  justify-items: center;
  min-height: clamp(640px, calc(100svh - 64px + var(--overlap) - 110px), 1000px);
  padding: clamp(56px, 9vh, 112px) var(--gutter) calc(var(--overlap) + 120px);
  background:
    radial-gradient(90% 70% at 50% 38%, rgba(204, 230, 115, 0.07) 0%, rgba(204, 230, 115, 0) 60%),
    var(--stage-bg);
  color: var(--cream-100);
}
.stage :focus-visible,
.closing :focus-visible,
.site-footer :focus-visible { outline-color: var(--lime-500); }

.stage-inner {
  position: relative;
  z-index: 2;
  max-width: 1040px;
  text-align: center;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 28px;
  font-family: var(--kb-font-mono);
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--lime-500);
  animation: rise 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
.eyebrow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--lime-500);
  animation: live 2s ease-out infinite;
}
.stage-title {
  margin: 0;
  font-size: clamp(3.1rem, 9.2vw, 8.5rem);
  font-weight: 800;
  line-height: 0.95;
  letter-spacing: -0.045em;
  color: var(--cream-100);
  text-wrap: balance;
}
.stage-title .line {
  display: block;
  animation: rise 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) 0.08s both;
}
.stage-title .line + .line { animation-delay: 0.2s; }
.stage-title .hl {
  padding: 0 0.12em 0.06em;
  border-radius: 0.08em;
  animation: stamp 0.55s cubic-bezier(0.3, 1.4, 0.5, 1) 0.55s both;
}
.stage-lede {
  max-width: 58ch;
  margin: 32px auto 0;
  font-size: clamp(1.05rem, 1.5vw, 1.25rem);
  line-height: 1.55;
  color: rgba(242, 241, 239, 0.76);
  text-wrap: pretty;
  animation: rise 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) 0.32s both;
}
.stage-lede strong { color: var(--cream-100); font-weight: 600; }
.stage-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 40px;
  animation: rise 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) 0.44s both;
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
.btn-lime:hover { background: var(--lime-600); border-color: var(--lime-600); transform: translateY(-1px); }
.btn-outline-light {
  background: transparent;
  color: var(--cream-100);
  border: 1px solid rgba(242, 241, 239, 0.3);
}
.btn-outline-light:hover { border-color: var(--cream-100); }

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
  animation: rise 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) 0.5s both;
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
.examples-label { margin-inline-end: 2px; font-size: 0.85rem; color: var(--kb-muted); }
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
.section-title.small { font-size: clamp(2rem, 3.8vw, 3.2rem); }

.rail {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 64px 0 0;
  padding: 0;
  list-style: none;
}
.rail.reveal { opacity: 1; transform: none; }
.rail::before {
  content: '';
  position: absolute;
  inset-inline: 0;
  top: 6px;
  height: 2px;
  background: var(--ink-950);
  transform: scaleX(0);
  transform-origin: left center;
  transition: transform 1.4s cubic-bezier(0.65, 0, 0.35, 1);
}
.rail.is-in::before { transform: scaleX(1); }
.station {
  position: relative;
  padding-block-start: 38px;
  padding-inline-end: 24px;
  opacity: 0;
  transform: translateY(14px);
  transition: opacity 0.6s ease, transform 0.6s ease;
  transition-delay: calc(var(--i) * 0.18s + 0.25s);
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
  background: var(--lime-500);
}
.rail.is-in .station { opacity: 1; transform: none; }
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
  align-items: center;
  gap: 48px 64px;
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
.figures-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 40px 32px;
  max-width: 1240px;
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
  font-size: clamp(2.4rem, 4vw, 4.2rem);
  font-size: min(4.8rem, 23cqi);
  font-weight: 800;
  line-height: 0.95;
  /* más suelto que en los titulares: con -0.045em el guion de «20–30» se pegaba a las cifras */
  letter-spacing: -0.02em;
  white-space: nowrap;
}
.figure-unit { margin-inline-start: 0.18em; font-size: 0.42em; letter-spacing: 0; }
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
@media (max-width: 1180px) {
  .figures-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 48px 40px; }
}
@media (max-width: 960px) {
  .results-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 900px) {
  .composer-grid { grid-template-columns: minmax(0, 1fr); }
  .rail { grid-template-columns: minmax(0, 1fr); margin-top: 48px; }
  .rail::before {
    inset-inline: auto;
    inset-inline-start: 6px;
    top: 0;
    bottom: 0;
    width: 2px;
    height: auto;
    transform: scaleY(0);
    transform-origin: center top;
  }
  .rail.is-in::before { transform: scaleY(1); }
  .station { padding-block: 0 36px; padding-inline: 40px 0; }
  .station::before { top: 2px; }
}
@media (max-width: 640px) {
  .home { --overlap: 96px; }
  .topbar-version { display: none; }
  .topbar-links { gap: 10px; }
  /* hueco sobre el titular para que la multitud también «hable» en móvil */
  .stage { padding-top: 112px; padding-bottom: calc(var(--overlap) + 120px); }
  .launch-btn { width: 100%; justify-content: center; }
}
@media (max-width: 480px) {
  .figures-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .eyebrow, .eyebrow-dot, .stage-title .line, .stage-title .hl,
  .stage-lede, .stage-actions, .composer { animation: none; }
  .rail::before, .station { transition: none; }
}
</style>
