import axios from 'axios'
import i18n from '../i18n'
import { pb } from '../lib/pocketbase'
import { noteNetworkFailure, noteServerReached } from '../lib/connection'

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
// Un solo intento de renovar la sesión a la vez (varios sondeos fallan a la vez cuando el token caduca)
let refreshInFlight = null
const refreshSession = () => {
  if (!refreshInFlight) {
    refreshInFlight = pb.collection('users').authRefresh()
      .then(() => 'ok')
      .catch((err) => {
        const status = err?.status ?? err?.response?.status
        return status === 401 || status === 403 ? 'invalid' : 'unreachable'
      })
      .finally(() => { refreshInFlight = null })
  }
  return refreshInFlight
}

// Una frase que la persona pueda leer: la del servidor si la trae («El modelo no está disponible…»), si no una por
// estado. Antes se veía «Request failed with status code 500» o «timeout of 300000ms exceeded».
const friendlyMessage = (error) => {
  const t = i18n.global.t
  const serverText = error?.response?.data?.error
  if (typeof serverText === 'string' && serverText.trim()) return serverText
  const status = error?.response?.status
  if (!status) return error?.code === 'ECONNABORTED' ? t('errors.timeout') : t('errors.network')
  if (status >= 500) return t('errors.http5xx')
  const known = [400, 401, 403, 404, 408, 409, 413, 429]
  return known.includes(status) ? t(`errors.http${status}`) : t('errors.unknown')
}

service.interceptors.response.use(
  response => {
    noteServerReached()
    // Descargas: devolver la respuesta completa (hace falta Content-Disposition)
    if (response.config.responseType === 'blob') {
      return response
    }

    const res = response.data

    // La API siempre responde JSON; un string (p. ej. index.html) es un error
    if (typeof res !== 'object' || res === null) {
      return Promise.reject(new Error(i18n.global.t('errors.unknown')))
    }

    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || i18n.global.t('errors.unknown')))
    }
    
    return res
  },
  async error => {
    console.error('Response error:', error)

    const status = error?.response?.status
    if (error?.response) noteServerReached()
    else if (error?.code !== 'ERR_CANCELED') noteNetworkFailure()

    // 401/403 → la sesión puede estar caducada. Un solo 401 NO es motivo para echar a la persona: el servidor
    // también lo da cuando PocketBase tarda en contestar, y la persona perdía lo que estaba escribiendo. Primero
    // se intenta renovar la sesión y repetir la petición UNA vez; solo si PocketBase mismo la rechaza se limpia
    // y se lleva a /login. La portada es pública: ahí el visitante se queda donde está.
    // Import lazy del router para evitar ciclos (api → router → views → api)
    if ((status === 401 || status === 403) && error.config) {
      const wasLoggedIn = !!pb.authStore.token
      if (wasLoggedIn && !error.config._renewed) {
        const outcome = await refreshSession()
        if (outcome === 'ok') {
          error.config._renewed = true
          return service(error.config)
        }
        if (outcome === 'unreachable') {
          error.detail = error.message
          error.message = friendlyMessage(error)
          return Promise.reject(error)        // PocketBase no contesta: no se sabe si la sesión vale; se deja como está
        }
      }
      import('../router').then(({ default: router }) => {
        const route = router.currentRoute.value
        if (route?.path === '/login') return
        pb.authStore.clear()
        if (route?.meta?.requiresAuth === false) return
        router.push({ path: '/login', query: { redirect: route?.fullPath || '/' } })
      })
    }

    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }

    error.detail = error.message
    error.message = friendlyMessage(error)
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
      // (502/503 = el proxy no llegó a la app). Un 500 significa que la
      // app lo ejecutó y falló: repetirlo duplica trabajo y gasto de LLM.
      const method = (error?.config?.method || 'get').toLowerCase()
      // 504 NO: el proxy se rindió esperando, pero la app pudo seguir y ejecutarlo (duplicaría proyectos o informes)
      const notProcessed = [502, 503].includes(status)
      const unsafeToRepeat = method !== 'get' && !notProcessed
      if (isClientError || unsafeToRepeat || i === maxRetries - 1) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

// Descarga un archivo de la API con el token (window.open no manda Authorization)
// Guarda en disco la respuesta de una descarga (el nombre sale de Content-Disposition)
const saveBlobResponse = (response, fallbackName) => {
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

export const downloadFile = async (url, fallbackName = 'download') => {
  saveBlobResponse(await service.get(url, { responseType: 'blob' }), fallbackName)
}

// Igual, para los documentos que se maquetan a partir de un cuerpo (p. ej. el borrador del brief)
export const downloadFilePost = async (url, body, fallbackName = 'download', timeout = 60000) => {
  saveBlobResponse(await service.post(url, body, { responseType: 'blob', timeout }), fallbackName)
}

export default service
