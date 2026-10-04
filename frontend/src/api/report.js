import service, { requestWithRetry, downloadFile } from './index'

/**
 * 开始报告生成
 * @param {Object} data - { simulation_id, force_regenerate? }
 */
export const generateReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/generate', data), 3, 1000)
}

/**
 * 获取报告生成状态
 * @param {Object} data - { task_id?, simulation_id? }
 */
export const getReportStatus = (data) => {
  return service.post('/api/report/generate/status', data)
}

/**
 * Descarga el informe en Markdown (con el token de sesión)
 * @param {string} reportId
 */
export const downloadReport = (reportId) => {
  return downloadFile(`/api/report/${reportId}/download`, `${reportId}.md`)
}

/**
 * Descarga el informe en PDF con la identidad de Simuloo (se maqueta en el servidor)
 * @param {string} reportId
 */
export const downloadReportPdf = (reportId) => {
  return downloadFile(`/api/report/${reportId}/download?format=pdf`, `${reportId}.pdf`)
}

/**
 * 获取 Agent 日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getAgentLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })
}

/**
 * 获取控制台日志（增量）
 * @param {string} reportId
 * @param {number} fromLine - 从第几行开始获取
 */
export const getConsoleLog = (reportId, fromLine = 0) => {
  return service.get(`/api/report/${reportId}/console-log`, { params: { from_line: fromLine } })
}

/**
 * 获取报告详情
 * @param {string} reportId
 */
/**
 * ¿Tiene informe esta simulación y en qué estado está? (responde 200 aunque no haya informe)
 * @param {string} simulationId
 * @returns {Promise<{data:{has_report:boolean, report_status:string|null, report_id:string|null, interview_unlocked:boolean}}>}
 */
export const checkReportForSimulation = (simulationId) => {
  return service.get(`/api/report/check/${simulationId}`)
}

export const getReport = (reportId) => {
  return service.get(`/api/report/${reportId}`)
}

// Preparar SOLO la apertura del informe ya terminado. Sin body ni reintentos
// automáticos: el servidor reutiliza la síntesis vigente o el trabajo en curso.
export const generateReportResults = (reportId, { signal } = {}) => {
  return service.post(`/api/report/${reportId}/results`, undefined, { timeout: 15000, signal })
}

// Sondeo corto de solo lectura, independiente del timeout de trabajos largos.
export const getReportResults = (reportId, { signal } = {}) => {
  return service.get(`/api/report/${reportId}`, { timeout: 15000, signal })
}

/**
 * 与 Report Agent 对话
 * @param {Object} data - { simulation_id, message, chat_history? }
 */
export const chatWithReport = (data) => {
  return requestWithRetry(() => service.post('/api/report/chat', data), 3, 1000)
}
