<template>
  <div class="login-page">
    <div class="login-container">

      <!-- Logo -->
      <div class="login-logo">
        <BrandLogo class="login-wordmark" aria-label="Mirror" />
        <p class="login-subtitle">Swarm Intelligence Engine</p>
        <p class="login-byline">by <span class="login-byline-brand">Koolbrand</span></p>
      </div>

      <!-- Form -->
      <div class="login-card">
        <form @submit.prevent="handleLogin" class="login-form">

          <div class="form-group">
            <label class="form-label">{{ t('login.email') }}</label>
            <div class="input-wrapper">
              <span class="input-icon">✉</span>
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
              <span class="input-icon">🔒</span>
              <input
                type="password"
                v-model="password"
                required
                class="form-input"
                placeholder="••••••••"
                :disabled="loading"
              />
            </div>
          </div>

          <div v-if="error" class="login-error">
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

      <p class="login-footer">{{ t('login.protected') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { pb } from '../lib/pocketbase'
import BrandLogo from '../components/BrandLogo.vue'

const { t } = useI18n()
const router = useRouter()

const email = ref('')
const password = ref('')
const error = ref(null)
const info = ref(null)
const loading = ref(false)

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
    router.push('/')
  } catch (err) {
    console.error('Login failed', err)
    error.value = t('login.invalidCredentials')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.forgot-link {
  align-self: center;
  background: none;
  border: none;
  color: #888;
  font-family: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0.25rem;
}
.forgot-link:hover:not(:disabled) {
  color: #00ff88;
}
.login-info {
  color: #00ff88;
  font-size: 0.8rem;
  text-align: center;
}
.login-page {
  min-height: 100vh;
  background: #0a0a0a;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  font-family: 'Courier New', monospace;
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
  filter: drop-shadow(0 0 20px rgba(0, 255, 136, 0.25));
}

.login-title {
  font-size: 2rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.1em;
  margin: 0;
}

.login-subtitle {
  color: #666;
  font-size: 0.8rem;
  letter-spacing: 0.15em;
  margin: 0.25rem 0 0;
  text-transform: uppercase;
}

.login-byline {
  color: #444;
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  margin: 0.4rem 0 0;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}

.login-byline-brand {
  color: #ff4500;
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
  color: #888;
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
  font-size: 0.9rem;
  pointer-events: none;
  opacity: 0.5;
}

.form-input {
  width: 100%;
  padding: 0.65rem 0.75rem 0.65rem 2.2rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.5rem;
  color: #e0e0e0;
  font-size: 0.9rem;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: rgba(0, 255, 136, 0.5);
  box-shadow: 0 0 0 2px rgba(0, 255, 136, 0.1);
}

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-input::placeholder {
  color: #444;
}

.login-error {
  background: rgba(255, 80, 80, 0.1);
  border: 1px solid rgba(255, 80, 80, 0.2);
  border-radius: 0.5rem;
  padding: 0.6rem 0.75rem;
  color: #ff6b6b;
  font-size: 0.8rem;
}

.login-btn {
  width: 100%;
  padding: 0.75rem;
  background: linear-gradient(135deg, #00ff88, #00cc6a);
  border: none;
  border-radius: 0.5rem;
  color: #0a0a0a;
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
  font-size: 0.7rem;
  color: #333;
  letter-spacing: 0.05em;
}
</style>
