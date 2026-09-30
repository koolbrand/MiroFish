/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  projectName: '',
  mode: 'manual',        // 'manual' (paso a paso) o 'auto' (el servidor sigue hasta el informe)
  isPending: false
})

export function setPendingUpload(files, requirement, projectName = '', mode = 'manual') {
  state.files = files
  state.simulationRequirement = requirement
  state.projectName = projectName
  state.mode = mode === 'auto' ? 'auto' : 'manual'
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    projectName: state.projectName,
    mode: state.mode,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.projectName = ''
  state.mode = 'manual'
  state.isPending = false
}

export default state
