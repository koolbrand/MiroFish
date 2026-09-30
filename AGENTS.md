# Simuloo — AGENTS.md

> Auto-cargado por Claude Code / Codex / Cursor. Patrón **Harness Engineering** — el harness vive en este repo.

## 🚀 Pre-flight obligatorio

Antes de cualquier sesión: `bash init.sh`. Valida node ≥18, python ≥3.9, .env con keys requeridas, frontend + backend instalados. Si falla, no arranques.

## 🤖 Subagentes (multi-agente)

| Agente | Para qué |
|---|---|
| `planner` | Orquesta, descompone, delega. No ejecuta código directo |
| `frontend-implementer` | Cambios en `frontend/` (Vue 3 + Vite, JS) |
| `backend-implementer` | Cambios en `backend/` (Python/Flask, LLM, Graphiti + Neo4j) |
| `quality-gate` | Valida build + integración antes de cerrar |

Patrón: `planner` → implementer(s) → `quality-gate` → commit.

## 🎯 Project Overview

> Nombre de producto: **Simuloo** (antes «Mirror» / «MiroFish»). Identificadores internos que **no** se renombran a propósito: servicio `mirofish` y volúmenes `mirofish_*` / `neo4j_data_v2` del compose (datos y enrutado de Coolify), prefijo `mirofish_` de los graph_id, loggers `mirofish.*`, clave `mirofish_tutorial_seen_v1_` del tutorial.

**Simuloo** (fork de MiroFish; repo `koolbrand/MiroFish`, carpeta `mirofish/`) es un motor de predicción de IA de siguiente generación impulsado por tecnología multi-agente. Extrae información semilla del mundo real y construye un mundo digital paralelo donde miles de agentes inteligentes interactúan.

- **GitHub**: https://github.com/koolbrand/MiroFish
- **Status**: En desarrollo
- **Node Version**: ≥18.0.0
- **Python Version**: ≥3.9

## 📁 Project Structure

```
mirofish/
├── frontend/              # Vue 3 + Vite frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── backend/               # Python backend
│   ├── run.py
│   ├── pyproject.toml
│   ├── tests/            # Smoke tests (uv run pytest -q)
│   ├── uploads/          # User uploads
│   └── logs/             # Application logs
├── docker-compose.yml     # Production config
├── Dockerfile            # Multi-stage production build
├── .env.example          # Environment template
├── .env                  # Local configuration (not in git)
├── coolify.json          # Coolify deployment config
└── COOLIFY_DEPLOYMENT.md # Deployment guide
```

## 🚀 Quick Start

### Development

```bash
# Install all dependencies
npm run setup:all

# Start both backend and frontend
npm run dev

# Backend only
npm run backend

# Frontend only
npm run frontend
```

### Production (Docker)

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f mirofish
```

## 🔧 Configuration

### Runtime real

La app corre en **Coolify** (ver `COOLIFY_DEPLOYMENT.md`). Las keys reales viven en el panel de Coolify, no en `.env` local. El `.env` local es opcional — solo si querés correr `npm run dev` contra APIs reales (LLM compatible OpenAI + Neo4j local, ver README). Para refactors/UI no es necesario.

### Environment Variables

Required en producción (Coolify panel) / desarrollo (`.env` local opcional):

```
LLM_API_KEY=<your_llm_api_key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
NEO4J_PASSWORD=<strong_password>
SECRET_KEY=<long_random_value>
POCKETBASE_URL=https://pocketbase.koolgrowth.com
EMBEDDING_MODEL / EMBEDDING_API_KEY / EMBEDDING_BASE_URL  # proveedor con embeddings
```

> La memoria de agentes es **Graphiti + Neo4j** (self-hosted). Los módulos `zep_*.py` conservan el nombre por historia; ya no usan Zep.

Optional:
```
DEBUG=false
PORT=8000
FRONTEND_PORT=5173
```

### External Services

1. **LLM Provider** (Recommended: Aliyun Qwen)
   - Sign up: https://bailian.console.aliyun.com/
   - Get API Key from dashboard

2. **Zep Memory** (for agent memory)
   - Sign up: https://app.getzep.com/
   - Get API Key from dashboard

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t mirofish:latest .
```

### Run Container

```bash
docker run -d \
  --name mirofish \
  -p 8000:8000 \
  --env-file .env \
  -v ./backend/uploads:/app/backend/uploads \
  -v ./backend/logs:/app/backend/logs \
  mirofish:latest
```

## 🔄 Coolify Integration

- See: `COOLIFY_DEPLOYMENT.md` for detailed instructions
- Configuration: `coolify.json` contains Coolify metadata
- Health endpoint: `/health`
- Internal port: `8000`

## 📊 Available Scripts

| Script | Purpose |
|--------|---------|
| `npm run setup:all` | Install frontend + backend deps |
| `npm run dev` | Start both backend & frontend |
| `npm run backend` | Start Python backend only |
| `npm run frontend` | Start React frontend only |
| `npm run build` | Build frontend for production |
| `cd backend && uv run pytest -q` | Smoke tests del backend (sin LLM ni Neo4j) |

## 🔐 Security Notes

- `.env` is in `.gitignore` (never commit secrets)
- Use environment variables for production
- Health checks enabled (30s interval)
- HTTPS recommended for Coolify

## 📝 Key Files to Know

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage production build |
| `docker-compose.yml` | Local/production orchestration |
| `.env.example` | Environment template |
| `backend/pyproject.toml` | Python dependencies |
| `frontend/package.json` | Node.js dependencies |
| `coolify.json` | Coolify integration config |
| `frontend/src/views/Home.vue` | Portada pública: muro de Biankas, formulario en 3 pasos, «cómo funciona», informe de ejemplo, cifras, historial (solo con sesión) y cierre |
| `frontend/src/components/BiankaCrowd.vue` | Muro de Biankas (canvas): color = opinión, conversan en bocadillos, marcador de 10 rondas (cuelga de la tarjeta como su pie: una sola pieza enmarcada) |
| `frontend/src/components/OpinionCrowd.vue` | Apartado «La multitud»: 120 Biankas de ejemplo que cambian de opinión ronda a ronda + «lo que van diciendo» (mismo final que el gráfico de `OpinionChart`) |
| `frontend/src/lib/biankaSprite.js` | Motor de sprites de la Bianka (conejo en pixel art), compartido por el muro, las escenas y los avatares |
| `frontend/src/components/Bianka{Scene,Row,Avatar}.vue`, `ReportExample.vue` | Escenas de «cómo funciona», filas que asoman, avatar con semilla y el informe de ejemplo |
| `backend/app/services/auto_pipeline.py`, `pipeline_state.py`, `api/pipeline.py` | Modo automático en el servidor: encadena las cinco etapas con los mismos parámetros que la pantalla (40 rondas de tope); estado en `uploads/projects/<id>/pipeline.json`; al arrancar, lo que estaba en marcha pasa a `interrupted` y no se reanuda solo |
| `frontend/src/composables/usePipeline.js`, `components/AutoPipelineBanner.vue` | Estado del automático compartido en pantalla y aviso en las cinco pantallas del proceso (detener, reanudar, seguir la etapa) |
| `backend/scripts/recsys_memory.py` | Parche de memoria del recomendador de OASIS (evita el kill -9 por OOM en simulaciones largas); `RECSYS_MEMORY_PATCH=0` lo desactiva |
| `backend/app/utils/recsys_prewarm.py` | Precarga del modelo del recomendador al arrancar (caché en el volumen `mirofish_hf_cache`) |

### Al tocar las pantallas del proceso

- **Una etapa ya hecha es de solo lectura**: abrirla no puede crear, preparar, lanzar, detener ni regenerar nada. Ojo con lo que dispara el montaje: el paso 2 prepara si la simulación no lo está, y el paso 3 **la lanza** si nunca se ejecutó (`runner_status: idle`). El indicador de etapas solo abre lo que ya ha ocurrido.
- En automático la pantalla observa: no lanza el grafo, la preparación, la simulación ni el informe (lo hace el servidor).
- Las pruebas sin interfaz de estas pantallas deben **abortar toda petición que no sea GET** (salvo lo que se compruebe a propósito): abrir una etapa a medias gasta LLM de verdad.

### Al tocar la portada

- Comprobar a **320, 360, 390, 768, 1000, 1366×768, 1440×900 y 1920** px, en es/en/zh y con «reducir movimiento»: sin scroll horizontal, el marcador cuelga pegado bajo la tarjeta (nunca la pisa, y los portátiles de 720–800 px de alto son el caso que falla) y ningún bocadillo corta texto.
- **La portada es pública** (`/` con `requiresAuth: false`): sin sesión no llama a la API (ni historial ni entrevista/revisión del brief) y el inicio de sesión se pide al pulsar «Iniciar simulación», con el material guardado en memoria (`store/pendingUpload.js`) y `?redirect=` de vuelta (solo rutas internas, `lib/authRedirect.js`). Cualquier pantalla nueva que llame a la API desde la portada debe comprobar la sesión antes.
- Las pruebas sin interfaz funcionan con una sesión de PocketBase **falsa solo en el navegador** (`localStorage.pocketbase_auth`) y **cortando las peticiones a PocketBase** (si llegan, rechaza el token falso y borra la sesión); en producción, además, `API_AUTH_TOKEN` temporal y borrarlo al acabar.
- Backend local: `NEO4J_URI=bolt://localhost:7687` (el valor por defecto `neo4j:7687` es el nombre de Docker Compose y da 500 en `/api/graph/data`).
- Los gráficos van animados (petición expresa) y nada de interfaz debe superar 700 ms.
- Los campos, chips y botones de contorno usan `--kb-control-line` (#858585, ≥ 3:1 sobre blanco y crema, WCAG 1.4.11); `--kb-line` y `--kb-line-strong` son para divisores, no para controles.
- Lo que hay tras pulsar «Iniciar simulación» también cuenta: `MainView.vue` muestra un aviso claro con «Reintentar» y «Volver al inicio» si falla el análisis o la construcción del mapa (antes quedaba un «generando…» eterno), y las cinco pantallas del proceso abren en «Mesa de trabajo» y reparten el encabezado en filas por debajo de 900 px.
- La nota de duración del formulario («20–30 min») y las cifras de la portada salen de ejecuciones medidas (18, 26 y 35 min; 19, 23 y 113 personas): si cambia el motor, se vuelven a medir.

## 🔗 Useful Resources

- [Simuloo en GitHub](https://github.com/koolbrand/MiroFish)
- [Aliyun Qwen API](https://bailian.console.aliyun.com/)
- [Zep Memory](https://app.getzep.com/)
- [Coolify Documentation](https://coolify.io/)

## 📌 Current Status

✅ En producción: https://simuloo.koolgrowth.com (Coolify, app `cim0v35ajeisb61vhm4bnn4o`)
✅ Flujo completo validado de extremo a extremo (brief → grafo → simulación → informe → chat)
✅ Portada con identidad Koolbrand (muro de Biankas) y memoria del recomendador acotada
⏳ Pendiente de decisión (Adrián): una simulación larga (72 rondas) en producción y relanzar la de un cliente que murió por memoria

---

**Last Updated**: 2026-09-30
**Maintained by**: Adrian (adrian@koolbrand.com)
