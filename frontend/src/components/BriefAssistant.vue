<template>
  <div class="brief-assistant">
    <!-- Acciones: entrevista (principal) y plantilla -->
    <div class="brief-card">
      <div class="brief-card-text">
        <strong>{{ $t('brief.cardTitle') }}</strong>
        <span>{{ $t('brief.cardBody') }}</span>
      </div>
      <div class="brief-card-actions">
        <button type="button" class="brief-btn ghost" :disabled="disabled" @click.stop="openInterview">
          {{ $t('brief.startInterview') }} →
        </button>
        <a class="brief-link" href="/plantilla-brief-simuloo.md" download="plantilla-brief-simuloo.md" @click.stop>
          ↓ {{ $t('brief.downloadTemplate') }}
        </a>
      </div>
    </div>

    <!-- Revisión del brief con Jev -->
    <div v-if="checking || (check && check.available)" class="brief-check">
      <div class="brief-check-head">
        <span class="brief-check-title">{{ $t('brief.checkTitle') }}</span>
        <span v-if="checking" class="brief-muted">{{ $t('brief.checking') }}</span>
        <span v-else-if="check && !check.available" class="brief-muted">{{ $t('brief.checkUnavailable') }}</span>
      </div>
      <ul v-if="check && check.available && check.sections?.length" class="brief-sections">
        <li v-for="s in check.sections" :key="s.key" :class="{ ok: s.present, missing: !s.present, required: s.required }">
          <span class="mark">{{ s.present ? '✓' : (s.required ? '✗' : '·') }}</span>
          <span class="name">{{ s.title }}</span>
          <span v-if="!s.present && s.required" class="tag">{{ $t('brief.required') }}</span>
        </li>
      </ul>
      <p v-if="missingRequired.length" class="brief-warning">
        {{ $t('brief.missingRequired') }}
      </p>
      <p v-else-if="check && check.available && check.sections?.length" class="brief-ok">
        {{ $t('brief.allRequiredOk') }}
      </p>
    </div>

    <!-- Entrevista (grill-me) -->
    <div v-if="interviewOpen" class="brief-modal" @click.self="closeInterview">
      <div
        class="brief-dialog"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
        ref="dialogEl"
        @keydown.tab="trapTab"
      >
        <div class="brief-dialog-head">
          <span>{{ $t('brief.interviewTitle') }}</span>
          <button type="button" class="brief-close" @click="closeInterview" :aria-label="$t('brief.close')">×</button>
        </div>

        <p class="brief-muted brief-intro">{{ $t('brief.interviewIntro') }}</p>

        <!-- Progreso por sección -->
        <ul v-if="coverage?.sections?.length" class="brief-sections compact">
          <li v-for="s in coverage.sections" :key="s.key" :class="{ ok: s.present, missing: !s.present }">
            <span class="mark">{{ s.present ? '✓' : '·' }}</span><span class="name">{{ s.title }}</span>
          </li>
        </ul>

        <div v-if="!draft" class="brief-chat" ref="chatBox">
          <div v-for="(turn, i) in transcript" :key="i" class="brief-turn">
            <div class="q">{{ turn.question }}</div>
            <div class="a">{{ turn.answer }}</div>
          </div>
          <div v-if="currentQuestion" class="brief-turn">
            <div class="q current">{{ currentQuestion }}</div>
          </div>
          <div v-if="busy" class="brief-muted">{{ busyLabel }}</div>
        </div>

        <div v-if="!draft && currentQuestion && !busy" class="brief-answer">
          <textarea
            v-model="answer"
            rows="3"
            :placeholder="$t('brief.answerPlaceholder')"
            @keydown.meta.enter="sendAnswer"
            @keydown.ctrl.enter="sendAnswer"
          ></textarea>
          <div class="brief-answer-actions">
            <button type="button" class="brief-btn" :disabled="!answer.trim()" @click="sendAnswer">{{ $t('brief.send') }} →</button>
            <button type="button" class="brief-btn ghost" :disabled="!transcript.length" @click="compose">{{ $t('brief.composeNow') }}</button>
          </div>
        </div>

        <!-- Borrador final -->
        <div v-if="draft" class="brief-draft">
          <p class="brief-muted">{{ $t('brief.draftHint') }}</p>
          <textarea v-model="draft" rows="14"></textarea>
          <div class="brief-answer-actions">
            <button type="button" class="brief-btn" @click="useDraft">{{ $t('brief.useDraft') }}</button>
            <button type="button" class="brief-btn ghost" @click="downloadDraft">↓ {{ $t('brief.downloadDraft') }}</button>
          </div>
        </div>

        <p v-if="errorMsg" class="brief-warning" role="alert">{{ errorMsg }}</p>
        <!-- Si el modelo falla, lo respondido no se pierde y se puede reintentar -->
        <div v-if="errorMsg && !busy && !draft && !currentQuestion" class="brief-answer-actions">
          <button type="button" class="brief-btn" @click="retry">{{ $t('brief.retry') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { checkBrief, interviewNext, interviewCompose } from '../api/brief'

const props = defineProps({
  files: { type: Array, default: () => [] },
  topic: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  // Sin sesión no se llama a la API (revisión y entrevista usan el modelo): se pide iniciar sesión
  signedIn: { type: Boolean, default: true }
})
const emit = defineEmits(['add-file', 'need-login'])
const { t } = useI18n()

const TEXT_EXT = ['md', 'markdown', 'txt', 'pdf']
const isText = (f) => TEXT_EXT.includes(f.name.split('.').pop().toLowerCase())

// ── Revisión automática al cambiar los archivos ──
const checking = ref(false)
const check = ref(null)
let checkTimer = null
let checkSeq = 0

const missingRequired = computed(() => (check.value?.available ? check.value.missing_required || [] : []))

watch(() => `${props.signedIn}|${props.files.map(f => `${f.name}:${f.size}`).join('|')}`, () => {
  clearTimeout(checkTimer)
  const textFiles = props.files.filter(isText)
  if (!props.signedIn || !textFiles.length) {
    check.value = null
    return
  }
  checkTimer = setTimeout(async () => {
    const seq = ++checkSeq
    checking.value = true
    try {
      const res = await checkBrief(textFiles)
      if (seq === checkSeq) check.value = res.data
    } catch (e) {
      if (seq === checkSeq) check.value = { available: false }
    } finally {
      if (seq === checkSeq) checking.value = false
    }
  }, 600)
}, { immediate: true })

// ── Entrevista ──
const interviewOpen = ref(false)
const transcript = ref([])
const currentQuestion = ref('')
const currentSection = ref('')
const coverage = ref(null)
const answer = ref('')
const draft = ref('')
const busy = ref(false)
const busyLabel = ref('')
const errorMsg = ref('')
const chatBox = ref(null)
let seedText = ''

const readSeedText = async () => {
  const texts = await Promise.all(
    props.files.filter(f => ['md', 'markdown', 'txt'].includes(f.name.split('.').pop().toLowerCase()))
      .map(f => f.text().catch(() => ''))
  )
  return texts.join('\n\n').slice(0, 12000)
}

const scrollChat = () => nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })

const askNext = async () => {
  busy.value = true
  busyLabel.value = t('brief.thinking')
  errorMsg.value = ''
  try {
    const res = await interviewNext({ topic: props.topic, transcript: transcript.value, seed_text: seedText })
    coverage.value = res.data.coverage
    if (res.data.done) {
      currentQuestion.value = ''
      await compose()
    } else {
      currentQuestion.value = res.data.question
      currentSection.value = res.data.section
    }
    return true
  } catch (e) {
    errorMsg.value = t('brief.error', { error: e.message })
    return false
  } finally {
    busy.value = false
    scrollChat()
  }
}

const openInterview = async () => {
  if (!props.signedIn) return emit('need-login')
  interviewOpen.value = true
  focusDialog()
  if (currentQuestion.value || draft.value) return
  if (!transcript.value.length) seedText = await readSeedText()
  // Sin pregunta y sin borrador (se cerró tras un fallo): se vuelve a preguntar, ya no se queda sin salida
  await askNext()
}

const sendAnswer = async () => {
  if (!answer.value.trim() || busy.value) return
  const asked = currentQuestion.value
  const turn = { question: asked, answer: answer.value.trim(), section: currentSection.value }
  transcript.value.push(turn)
  answer.value = ''
  currentQuestion.value = ''
  scrollChat()
  if (!(await askNext())) {
    // El modelo falló: la pregunta y lo escrito vuelven a su sitio para reintentar sin perder nada
    transcript.value.pop()
    currentQuestion.value = asked
    answer.value = turn.answer
  }
}

const retry = async () => {
  if (busy.value) return
  if (transcript.value.length && !currentQuestion.value) {
    await compose()
    if (!draft.value) await askNext()
  } else {
    await askNext()
  }
}

const compose = async () => {
  busy.value = true
  busyLabel.value = t('brief.composing')
  errorMsg.value = ''
  try {
    const res = await interviewCompose({ topic: props.topic, transcript: transcript.value, seed_text: seedText })
    draft.value = res.data.markdown
    coverage.value = res.data.coverage
  } catch (e) {
    errorMsg.value = t('brief.error', { error: e.message })
  } finally {
    busy.value = false
  }
}

const briefFile = () => new File([draft.value], 'brief-simuloo.md', { type: 'text/markdown' })

const useDraft = () => {
  emit('add-file', briefFile())
  interviewOpen.value = false
}

const downloadDraft = () => {
  const url = URL.createObjectURL(briefFile())
  const a = document.createElement('a')
  a.href = url
  a.download = 'brief-simuloo.md'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const closeInterview = () => { interviewOpen.value = false }

// Diálogo: el foco entra al abrir, Tab no se sale de él y Esc lo cierra. Esc se escucha en todo el documento:
// tras enviar una respuesta el botón se deshabilita y el foco cae al <body>, fuera del diálogo.
const dialogEl = ref(null)
const onEscape = (event) => { if (event.key === 'Escape') closeInterview() }
watch(interviewOpen, (open) => {
  if (open) document.addEventListener('keydown', onEscape)
  else document.removeEventListener('keydown', onEscape)
})
onBeforeUnmount(() => document.removeEventListener('keydown', onEscape))
const focusDialog = () => nextTick(() => dialogEl.value?.focus())
const trapTab = (event) => {
  const nodes = [...(dialogEl.value?.querySelectorAll('button, textarea, [href], input, [tabindex]:not([tabindex="-1"])') || [])]
    .filter(el => !el.disabled && el.offsetParent !== null)
  if (!nodes.length) return
  const first = nodes[0], last = nodes[nodes.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogEl.value)) {
    event.preventDefault(); last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus()
  }
}
</script>

<style scoped>
.brief-assistant { margin-top: 12px; font-family: var(--kb-font-sans); font-size: 12px; }
.brief-card {
  display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  padding: 14px 16px; background: var(--kb-accent-subtle); border: 1px solid var(--kb-accent-line); border-radius: 12px;
  font-family: var(--kb-font-sans); font-size: 13px;
}
.brief-card-text { display: grid; gap: 2px; min-width: 220px; flex: 1; }
.brief-card-text strong { font-size: 14px; }
.brief-card-text span { color: var(--kb-text-2); }
.brief-card-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.brief-link {
  background: none; border: none; padding: 0; cursor: pointer; color: var(--kb-text);
  font: inherit; text-decoration: underline; text-underline-offset: 3px;
}
.brief-link:hover:not(:disabled) { color: var(--kb-accent-text); background: rgba(204, 230, 115, 0.4); text-decoration-thickness: 2px; }
.brief-link:disabled { opacity: 0.4; cursor: not-allowed; }
.brief-check { margin-top: 12px; border: 1px solid var(--kb-line); padding: 12px 14px; }
.brief-check-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.brief-check-title { text-transform: uppercase; letter-spacing: 0.08em; color: var(--kb-muted); }
.brief-muted { color: var(--kb-subtle); }
.brief-sections { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.brief-sections.compact { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); margin: 8px 0 12px; }
.brief-sections li { display: flex; gap: 8px; align-items: baseline; }
.brief-sections .mark { width: 12px; }
.brief-sections li.ok .mark { color: #1a7f37; }
.brief-sections li.missing.required .mark { color: var(--kb-accent-text); }
.brief-sections li.missing .name { color: var(--kb-muted); }
.brief-sections .tag { font-size: 10px; color: var(--kb-accent-text); border: 1px solid var(--kb-accent-line); padding: 0 4px; }
.brief-warning { margin: 10px 0 0; color: var(--kb-accent-text); }
.brief-ok { margin: 10px 0 0; color: #1a7f37; }

.brief-modal {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.45); z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 16px;
}
.brief-dialog {
  background: #fff; width: min(720px, 100%); max-height: 90vh; overflow: auto;
  padding: 20px 22px; border: 1px solid var(--kb-text);
}
.brief-dialog-head {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em;
}
.brief-close { background: none; border: none; font-size: 22px; cursor: pointer; line-height: 1; }
.brief-intro { margin: 8px 0 0; line-height: 1.5; }
.brief-chat { max-height: 38vh; overflow: auto; display: grid; gap: 12px; margin: 8px 0; }
.brief-turn .q { font-weight: 600; line-height: 1.5; }
.brief-turn .q.current { color: var(--kb-accent-text); }
.brief-turn .a { margin-top: 4px; padding-left: 10px; border-left: 2px solid var(--kb-line); color: var(--kb-text-2); white-space: pre-wrap; }
.brief-answer textarea, .brief-draft textarea {
  width: 100%; box-sizing: border-box; font: inherit; padding: 10px; border: 1px solid var(--kb-control-line); border-radius: 10px; resize: vertical;
}
.brief-answer-actions { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
.brief-btn {
  font: inherit; font-weight: 600; padding: 9px 14px; border: 1px solid var(--kb-text); border-radius: 8px; background: var(--kb-text); color: #fff; cursor: pointer;
}
.brief-btn:hover:not(:disabled) { background: var(--lime-500); color: var(--ink-950); border-color: var(--ink-950); }
.brief-btn.ghost { background: #fff; color: var(--kb-text); }
.brief-btn.ghost:hover:not(:disabled) { background: var(--lime-50); }
.brief-btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
