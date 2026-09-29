import axios from 'axios'
import i18n from '../i18n'
import { pb } from '../lib/pocketbase'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    config.headers['Accept-Language'] = i18n.global.locale.value
    const token = pb.authStore.token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（容错重试机制）
service.interceptors.response.use(
  response => {
    // Descargas: devolver la respuesta completa (hace falta Content-Disposition)
    if (response.config.responseType === 'blob') {
      return response
    }

    const res = response.data

    // La API siempre responde JSON; un string (p. ej. index.html) es un error
    if (typeof res !== 'object' || res === null) {
      return Promise.reject(new Error('Respuesta inesperada del servidor'))
    }

    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)

    const status = error?.response?.status

    // 401/403 → sesión inválida: limpiar store y enviar a /login
    // Import lazy del router para evitar ciclos (api → router → views → api)
    if (status === 401 || status === 403) {
      import('../router').then(({ default: router }) => {
        const onLoginRoute = router.currentRoute.value?.path === '/login'
        if (!onLoginRoute) {
          pb.authStore.clear()
          router.push('/login')
        }
      })
    }

    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }

    // 处理网络错误
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }

    return Promise.reject(error)
  }
)

// 带重试的请求函数
// Retries network errors and 5xx responses. Does NOT retry 4xx —
// those are deterministic rejections from the server (validation,
// 409 conflict, 404 not found) and retrying them just spams the log.
// Tampoco reintenta un POST/PATCH/DELETE que el servidor pudo haber procesado
// (timeout, red caída o 500): duplicaría proyectos, simulaciones o informes.
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      const status = error?.response?.status
      const isClientError = typeof status === 'number' && status >= 400 && status < 500
      // Un POST solo se repite si el servidor seguro que no lo procesó
      // (502/503/504 = el proxy no llegó a la app). Un 500 significa que la
      // app lo ejecutó y falló: repetirlo duplica trabajo y gasto de LLM.
      const method = (error?.config?.method || 'get').toLowerCase()
      const notProcessed = [502, 503, 504].includes(status)
      const unsafeToRepeat = method !== 'get' && !notProcessed
      if (isClientError || unsafeToRepeat || i === maxRetries - 1) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

// Descarga un archivo de la API con el token (window.open no manda Authorization)
export const downloadFile = async (url, fallbackName = 'download') => {
  const response = await service.get(url, { responseType: 'blob' })
  const disposition = response.headers['content-disposition'] || ''
  const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const plainName = disposition.match(/filename="?([^";]+)"?/i)
  const filename = utf8Name ? decodeURIComponent(utf8Name[1]) : (plainName ? plainName[1] : fallbackName)

  const objectUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

export default service
