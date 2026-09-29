// Revelado al entrar en pantalla: añade la clase `is-in` una sola vez.
// Con «reducir movimiento» activado el contenido aparece directamente.
//
//   <div v-reveal>…</div>
//   <div v-reveal="() => arrancar()">…</div>   (callback al revelarse)

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export const onceInView = (el, cb, threshold = 0.25) => {
  if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
    cb()
    return () => {}
  }
  const obs = new IntersectionObserver((entries) => {
    if (entries.some(e => e.isIntersecting)) {
      obs.disconnect()
      cb()
    }
  }, { threshold })
  obs.observe(el)
  return () => obs.disconnect()
}

export const vReveal = {
  mounted(el, binding) {
    el.classList.add('reveal')
    el._revealStop = onceInView(el, () => {
      el.classList.add('is-in')
      if (typeof binding.value === 'function') binding.value()
    })
  },
  unmounted(el) {
    el._revealStop?.()
  },
}
