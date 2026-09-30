import service from './index'

// Modo automático: el servidor encadena las cinco etapas aunque se cierre la pestaña.

// Sube el material y arranca el automático (responde enseguida con el project_id)
export const startAutoPipeline = (formData) => service.post('/api/pipeline/auto', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
  timeout: 120000
})

// Estado del automático de un proyecto ({ mode: 'manual' } si nunca se usó)
export const getPipeline = (projectId) => service.get(`/api/pipeline/${projectId}`)

export const cancelPipeline = (projectId) => service.post(`/api/pipeline/${projectId}/cancel`)

// Reanuda uno interrumpido o fallido, o pasa a automático un proyecto que iba paso a paso
export const resumePipeline = (projectId) => service.post(`/api/pipeline/${projectId}/resume`)
