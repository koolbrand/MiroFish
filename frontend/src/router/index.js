import { createRouter, createWebHistory } from 'vue-router'
import { pb } from '../lib/pocketbase'
import { safeRedirect } from '../lib/authRedirect'

// Cada pantalla es su propio trozo de código y solo se descarga al entrar: el paquete único pesaba 941 kB (313 kB
// comprimido) incluso para ver la portada. Medido: la portada baja a ~590 kB con solo esto.
const Home = () => import('../views/Home.vue')
const Process = () => import('../views/MainView.vue')
const SimulationView = () => import('../views/SimulationView.vue')
const SimulationRunView = () => import('../views/SimulationRunView.vue')
const ReportView = () => import('../views/ReportView.vue')
const InteractionView = () => import('../views/InteractionView.vue')
const LoginView = () => import('../views/LoginView.vue')
const ProjectsListView = () => import('../views/ProjectsListView.vue')

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    // Portada pública: el inicio de sesión se pide al lanzar la simulación
    meta: { requiresAuth: false }
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true,
    meta: { requiresAuth: true }
  },
  {
    path: '/projects',
    name: 'ProjectsList',
    component: ProjectsListView,
    meta: { requiresAuth: true }
  },
  // Una dirección que no existe lleva a la portada (antes: pantalla en blanco, sin ningún enlace)
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard — lo privado pide sesión y, tras iniciarla, vuelve a donde se iba
router.beforeEach((to) => {
  const requiresAuth = to.meta.requiresAuth !== false
  const isAuthenticated = pb.authStore.isValid

  if (requiresAuth && !isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && isAuthenticated) {
    return safeRedirect(to.query.redirect)
  }
})

// Tras un despliegue los trozos de código tienen otro nombre: quien tenía la app abierta pide uno que ya no existe y la
// navegación falla. Se recarga la página una vez para coger la versión nueva (con tope, para no entrar en bucle).
router.onError((error, to) => {
  const stale = /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i
  if (!stale.test(String(error?.message || error))) return
  const key = 'simuloo_reload_after_deploy'
  try {
    if (sessionStorage.getItem(key) === to.fullPath) return          // ya se intentó con esta dirección
    sessionStorage.setItem(key, to.fullPath)
  } catch (_) { /* sin almacenamiento: se recarga igualmente una vez */ }
  window.location.assign(to.fullPath)
})

export default router
