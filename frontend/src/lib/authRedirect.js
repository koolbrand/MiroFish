// Destino tras iniciar sesión (?redirect=): solo rutas internas de la app,
// nunca una URL externa ni la propia pantalla de login.
export function safeRedirect(value, fallback = '/') {
  if (typeof value !== 'string' || !value.startsWith('/')) return fallback
  if (value.startsWith('//') || value.includes('\\')) return fallback
  if (value === '/login' || value.startsWith('/login?')) return fallback
  return value
}
