import service from './index'

// Revisión del brief con Jev (solo se envían los archivos de texto)
export const checkBrief = (files) => {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  return service.post('/api/brief/check', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000
  })
}

// Entrevista (grill-me): siguiente pregunta o done
export const interviewNext = (data) => service.post('/api/brief/interview/next', data, { timeout: 120000 })

// Entrevista: redactar el brief con la plantilla
export const interviewCompose = (data) => service.post('/api/brief/interview/compose', data, { timeout: 180000 })
