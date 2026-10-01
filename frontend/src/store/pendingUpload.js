/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'
import { DEFAULT_ROUNDS, normalizeRounds } from '../lib/rounds'

const state = reactive({
  files: [],
  simulationRequirement: '',
  projectName: '',
  mode: 'manual',        // 'manual' (paso a paso) o 'auto' (el servidor sigue hasta el informe)
  webResearch: false,    // investigar en internet antes de la ontología (opcional)
  rounds: DEFAULT_ROUNDS, // rondas de la simulación en modo automático (20 / 40 / 72)
  isPending: false,
  launching: false       // la pantalla del proceso está enviando el material ahora mismo (la portada no debe permitir lanzar otra vez)
})

export function setPendingUpload(files, requirement, projectName = '', mode = 'manual', webResearch = false, rounds = DEFAULT_ROUNDS) {
  state.files = files
  state.simulationRequirement = requirement
  state.projectName = projectName
  state.mode = mode === 'auto' ? 'auto' : 'manual'
  state.webResearch = !!webResearch
  state.rounds = normalizeRounds(rounds)
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    projectName: state.projectName,
    mode: state.mode,
    webResearch: state.webResearch,
    rounds: state.rounds,
    isPending: state.isPending
  }
}

// Reactivo: la portada lo lee para no dejar lanzar una segunda vez mientras la primera sigue en vuelo
export function setLaunching(value) {
  state.launching = !!value
}

export function isLaunching() {
  return state.launching
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.projectName = ''
  state.mode = 'manual'
  state.webResearch = false
  state.rounds = DEFAULT_ROUNDS
  state.isPending = false
}

export default state
