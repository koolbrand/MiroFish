<template>
  <div class="login-page">
    <div class="login-container">

      <!-- Logo -->
      <div class="login-logo">
        <BrandLogo class="login-wordmark" aria-label="Simuloo" />
        <p class="login-subtitle">{{ t('login.tagline') }}</p>
        <p class="login-byline">by <img class="login-byline-logo" src="/brand/koolbrand-logo-negativo-sin-claim.svg" alt="Koolbrand" /></p>
      </div>

      <!-- Form -->
      <div class="login-card">
        <p v-if="reasonText" class="login-reason">{{ reasonText }}</p>
        <form @submit.prevent="handleLogin" class="login-form">

          <div class="form-group">
            <label class="form-label">{{ t('login.email') }}</label>
            <div class="input-wrapper">
              <svg class="input-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>
              <input
                type="email"
                v-model="email"
                required
                class="form-input"
                placeholder="tu@koolbrand.com"
                :disabled="loading"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">{{ t('login.password') }}</label>
            <div class="input-wrapper">
              <svg class="input-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>
              <input
                type="password"
                ref="passwordEl"
                v-model="password"
                required
                class="form-input"
                placeholder="••••••••"
                :disabled="loading"
              />
            </div>
          </div>

          <div v-if="error" class="login-error" role="alert">
            <span>⚠ {{ error }}</span>
          </div>

          <button type="submit" class="login-btn" :disabled="loading">
            <span v-if="loading" class="btn-spinner">⟳</span>
            <span v-else>{{ t('login.signIn') }}</span>
          </button>

          <button type="button" class="forgot-link" :disabled="loading" @click="handleForgotPassword">
            {{ t('login.forgotPassword') }}
          </button>
          <div v-if="info" class="login-info">
            <span>{{ info }}</span>
          </div>
        </form>
      </div>

      <router-link to="/" class="login-back">← {{ t('login.backHome') }}</router-link>
      <p class="login-footer">{{ t('login.protected') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { pb } from '../lib/pocketbase'
import { safeRedirect } from '../lib/authRedirect'
import { getPendingUpload } from '../store/pendingUpload'
import BrandLogo from '../components/BrandLogo.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

// Por qué se pide iniciar sesión (viene de la portada, que es pública)
const reasonText = computed(() => {
  const reason = route.query.reason
  if (reason === 'launch' && getPendingUpload().isPending) return t('login.reasonLaunch')
  if (reason === 'interview') return t('login.reasonInterview')
  return ''
})

const email = ref('')
const password = ref('')
const error = ref(null)
const info = ref(null)
const loading = ref(false)
const passwordEl = ref(null)

// PocketBase manda el correo con el enlace para poner una contraseña nueva.
// Mensaje neutro aunque el email no exista, para no revelar qué cuentas hay.
const handleForgotPassword = async () => {
  error.value = null
  info.value = null
  if (!email.value) {
    error.value = t('login.forgotNeedsEmail')
    return
  }
  loading.value = true
  try {
    await pb.collection('users').requestPasswordReset(email.value)
    info.value = t('login.resetSent')
  } catch (err) {
    console.error('Password reset failed', err)
    error.value = t('login.resetFailed')
  } finally {
    loading.value = false
  }
}

const handleLogin = async () => {
  error.value = null
  info.value = null
  loading.value = true

  try {
    await pb.collection('users').authWithPassword(email.value, password.value)
    let destination = safeRedirect(route.query.redirect)
    // Lanzar sin el material (recargaron la página) no tiene sentido: vuelve a la portada
    if (destination === '/process/new' && !getPendingUpload().isPending) destination = '/'
    router.push(destination)
  } catch (err) {
    console.error('Login failed', err)
    // «Credenciales incorrectas» solo si PocketBase contestó que lo son (400/401/403). Sin conexión, con el servicio
    // caído o con demasiados intentos (429) la persona revisaba una contraseña que estaba bien
    const status = err?.status ?? err?.response?.status
    if (status === 400 || status === 401 || status === 403) error.value = t('login.invalidCredentials')
    else if (status === 429) error.value = t('errors.http429')
    else if (!status) error.value = t('errors.network')
    else error.value = t('errors.http5xx')
  } finally {
    loading.value = false
    // el formulario se deshabilita mientras entra y el foco se pierde: si falló, vuelve al campo de la contraseña
    if (error.value) { password.value = ''; nextTick(() => passwordEl.value?.focus()) }
  }
}
</script>

<style scoped>
.forgot-link {
  align-self: center;
  background: none;
  border: none;
  color: var(--kb-muted-on-dark);
  font-family: inherit;
  font-size: 0.8rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0.25rem;
}
.forgot-link:hover:not(:disabled) {
  color: var(--kb-accent-solid);
}
.login-reason {
  margin: 0 0 1.25rem;
  padding: 0.65rem 0.8rem;
  border-radius: 0.5rem;
  background: rgba(204, 230, 115, 0.1);
  border: 1px solid rgba(204, 230, 115, 0.25);
  color: var(--kb-line);
  font-size: 0.85rem;
  line-height: 1.45;
  text-align: center;
}
.login-back {
  align-self: center;
  color: var(--kb-muted-on-dark);
  font-size: 0.85rem;
  text-decoration: none;
  padding: 0.25rem 0.5rem;
}
.login-back:hover { color: var(--kb-accent-solid); }
.login-info {
  color: var(--kb-accent-solid);
  font-size: 0.85rem;
  text-align: center;
}
.login-page {
  min-height: 100vh;
  background: var(--kb-text);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  font-family: var(--kb-font-sans);
}

.login-container {
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.login-logo {
  text-align: center;
}

.login-wordmark {
  font-size: 56px;
  color: #ffffff;
  margin-bottom: 0.5rem;
  
}

.login-title {
  font-size: 2rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.1em;
  margin: 0;
}

.login-subtitle {
  color: var(--kb-line-strong);
  font-size: 1.05rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  margin: 0.6rem 0 0;
}

.login-byline {
  color: var(--kb-muted-on-dark);
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  margin: 0.4rem 0 0;
  text-transform: uppercase;
  font-family: var(--kb-font-mono);
}

.login-byline-logo {
  height: 22px;
  vertical-align: -5px;
  margin-left: 0.4em;
}

.login-byline-brand {
  color: var(--kb-accent-solid);
  font-weight: 700;
}

.login-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 1rem;
  padding: 2rem;
  backdrop-filter: blur(10px);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-label {
  font-size: 0.75rem;
  color: var(--kb-muted-on-dark);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.input-wrapper {
  position: relative;
}

.input-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: var(--kb-muted-on-dark);
}

.form-input {
  width: 100%;
  padding: 0.65rem 0.75rem 0.65rem 2.2rem;
  background: var(--kb-text);
  border: 1px solid var(--kb-muted-on-dark);   /* ≥ 3:1 frente a la tarjeta (WCAG 1.4.11); antes, blanco al 10 % = 1,35:1 */
  border-radius: 0.5rem;
  color: var(--kb-line);
  font-size: 0.9rem;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--kb-accent-solid);
  box-shadow: 0 0 0 2px var(--kb-accent-solid);
}

.form-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-input::placeholder {
  color: var(--kb-muted-on-dark);
}

/* el error se dice con texto claro y filete de peligro (el rojo de marca no llega a 4,5:1 sobre tinta) */
.login-error {
  background: rgba(220, 38, 38, 0.14);
  border: 1px solid var(--kb-danger-line);
  border-radius: 0.5rem;
  padding: 0.65rem 0.8rem;
  color: var(--kb-surface);
  font-size: 0.85rem;
  line-height: 1.4;
}

.login-btn {
  width: 100%;
  padding: 0.75rem;
  background: var(--kb-accent-solid);
  border: none;
  border-radius: 0.5rem;
  color: var(--kb-accent-on);
  font-size: 0.9rem;
  font-weight: 700;
  font-family: inherit;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.login-footer {
  text-align: center;
  font-size: 0.75rem;
  color: var(--kb-muted-on-dark);
  letter-spacing: 0.05em;
}
</style>
