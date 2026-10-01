import { createApp } from 'vue'
import App from './App.vue'
import './assets/koolbrand.css'
import router from './router'
import i18n, { localeReady } from './i18n'

const app = createApp(App)

app.use(router)
app.use(i18n)

// Se pinta cuando el idioma elegido está descargado (el español ya viene dentro, así que casi nunca espera)
localeReady.finally(() => app.mount('#app'))
