const STATES = new Set(['not_generated', 'generating', 'ready', 'failed', 'stale'])
export const RESULT_ERROR_CODES = new Set(['interrupted', 'source_invalid', 'source_too_large', 'report_not_ready', 'source_changed', 'payload_invalid', 'provider_timeout', 'provider_token_limit', 'provider_invalid_response', 'provider_error', 'storage_error', 'busy'])
const text = (value, max) => typeof value === 'string' && value.trim().length > 0 && value.length <= max
const refs = (value, count = 1) => Array.isArray(value) && value.length === count && value.every(ref =>
  Number.isInteger(ref?.section_index) && ref.section_index > 0 && ref.section_index <= 1000
  && text(ref.quote, 600) && ref.quote.length >= 12 && text(ref.section_title, 500))
const id = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,32}$/.test(value)
const fields = (value, names) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name))
const list = (value, min, max, validate) => Array.isArray(value) && value.length >= min && value.length <= max && value.every(validate)
// Escapar el texto lo hace Vue. Aquí solo se acepta el contrato de presentación;
// la verificación literal contra el informe corresponde al servidor.
export function resultsSnapshot(value) {
  if (!value) return { version: 2, status: 'not_generated', data: null }
  if (value.version !== 2 || !STATES.has(value.status)) return { version: 2, status: 'failed', error_code: 'payload_invalid', data: null }
  const snapshot = { ...value, data: null, error_code: RESULT_ERROR_CODES.has(value.error_code) ? value.error_code : null }
  if (value.status !== 'ready') return snapshot
  const d = value.data
  const valid = fields(d, ['headline', 'findings', 'contrasts', 'limitations'])
    && fields(d.headline, ['text', 'refs']) && text(d.headline.text, 600) && refs(d.headline.refs)
    && list(d.findings, 2, 4, row => fields(row, ['id', 'text', 'refs']) && id(row.id) && text(row.text, 600) && refs(row.refs))
    && list(d.contrasts, 0, 2, row => fields(row, ['id', 'left', 'right', 'refs']) && id(row.id) && text(row.left, 600) && text(row.right, 600) && refs(row.refs, 2))
    && list(d.limitations, 1, 3, row => fields(row, ['text', 'refs']) && text(row.text, 600) && refs(row.refs))
  return valid ? { ...snapshot, data: d } : { ...snapshot, status: 'failed', error_code: 'payload_invalid' }
}

// Todo POST viene de start(), nunca de observe()/reset()/GET. Un solo sondeo
// pendiente; las respuestas de otro informe o una pantalla cerrada se descartan.
export function createResultsController({ read, generate, onSnapshot, onProblem, onBusy,
  schedule = setTimeout, cancel = clearTimeout, now = Date.now, windowMs = 300000 }) {
  let id = null, epoch = 0, disposed = false, ready = false, snapshot = null
  let timer = null, abort = null, posting = false, reading = false, paused = false, expires = 0
  const clear = () => { if (timer !== null) cancel(timer); timer = null }
  const busy = value => onBusy?.(value)
  const problem = value => onProblem?.(value)
  const current = token => !disposed && token === epoch
  const publish = value => { snapshot = resultsSnapshot(value); onSnapshot?.(snapshot, true) }
  const queue = () => {
    if (disposed || !id || !ready || paused || snapshot?.status !== 'generating' || timer !== null || reading || posting) return
    if (!expires) expires = now() + windowMs
    if (now() >= expires) { paused = true; problem('poll_timeout'); return }
    timer = schedule(() => { timer = null; poll() }, 3000)
  }
  const request = async (post) => {
    if (disposed || !id || !ready || reading || posting) return
    const token = epoch, reportId = id
    clear()
    if (post) posting = true
    else reading = true
    abort = new AbortController()
    busy(true)
    problem(null)
    if (post) publish({ version: 2, status: 'generating', data: null })
    try {
      const result = await (post ? generate(reportId, abort.signal) : read(reportId, abort.signal))
      if (!current(token)) return
      publish(result)
      paused = false
    } catch (error) {
      if (!current(token)) return
      const code = error?.response?.data?.error_code
      if (post && RESULT_ERROR_CODES.has(code)) publish({ version: 2, status: 'failed', error_code: code, data: null })
      else { paused = true; problem('connection') }
    } finally {
      if (current(token)) {
        posting = false; reading = false; abort = null; busy(false)
        queue()
      }
    }
  }
  const poll = () => request(false)
  return {
    reset(reportId) {
      epoch++; clear(); abort?.abort(); abort = null
      id = reportId; ready = false; snapshot = null; posting = false; reading = false; paused = false; expires = 0
      busy(false); problem(null); onSnapshot?.(null)
    },
    observe(value, reportReady) {
      ready = reportReady === true
      const incoming = resultsSnapshot(value)
      if (snapshot?.status === 'generating' && incoming.status === 'not_generated'
        && (!incoming.report_sha256 || incoming.report_sha256 === snapshot.report_sha256)) return
      // Un GET anterior al POST puede llegar después del ready emitido por ese
      // trabajo. El informe es inmutable; stale/failed o un hash distinto ganan.
      if (snapshot?.status === 'ready' && ['not_generated', 'generating'].includes(incoming.status)
        && (!incoming.report_sha256 || incoming.report_sha256 === snapshot.report_sha256)) return
      if (incoming.status === 'ready' || incoming.status === 'stale') {
        epoch++; clear(); abort?.abort(); abort = null; posting = false; reading = false; busy(false)
      }
      snapshot = incoming; onSnapshot?.(snapshot)
      if (!ready || snapshot.status !== 'generating') { clear(); expires = 0 }
      else queue()
    },
    start() {
      if (!ready || !['not_generated', 'failed', 'stale'].includes(snapshot?.status)) return Promise.resolve()
      paused = false; expires = 0
      return request(true)
    },
    resume() { paused = false; expires = 0; return poll() },
    dispose() { disposed = true; epoch++; clear(); abort?.abort(); busy(false) }
  }
}
