<div align="center">

# MIRROR — by Koolbrand

**Motor de simulación de opinión pública con IA multi-agente.**  
*Predice reacciones de mercado, opinión pública y dinámicas sociales — antes de que ocurran.*

> 🇪🇸 **Interfaz en español · inglés · chino** · Dual-LLM · Memoria de grafo 100 % autoalojada (sin Zep Cloud)

[![GitHub Stars](https://img.shields.io/github/stars/koolbrand/MiroFish?style=flat-square&color=DAA520)](https://github.com/koolbrand/MiroFish/stargazers)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![Coolify](https://img.shields.io/badge/Coolify-One--click-6B46C1?style=flat-square)](https://coolify.io/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Self--hosted-008CC1?style=flat-square&logo=neo4j&logoColor=white)](https://neo4j.com/)

[Proyecto original ↗](https://github.com/666ghj/MiroFish)

</div>

---

## ¿Qué es Mirror?

Mirror te permite subir documentos del mundo real — informes, noticias, campañas — y simular cómo miles de agentes de IA con personalidades, memorias y comportamientos independientes reaccionarían a ellos. El resultado: un informe de predicción detallado sobre dinámicas sociales, opinión pública o respuesta de mercado **antes de que ocurran**.

> Sube documentos → describe tu hipótesis → obtén un informe completo con agentes interactivos

**Ideal para:** equipos de marca, investigadores, analistas de mercado, periodistas y cualquiera que quiera validar decisiones antes de ejecutarlas.

---

## 🚀 Qué añadió Koolbrand a este fork

Este fork toma el motor original MiroFish y lo convierte en una herramienta **lista para producción**, **autoalojada** y **lista para demos con clientes**.

### 🪞 Rebrand — Mirror by Koolbrand

Rediseño completo de identidad visual:
- Logo SVG propio `MIRЯOR` (wordmark con R invertida)
- Hero animado con simulación D3 force-directed en tiempo real (idéntico al grafo de la app)
- Paleta de marca: negro, blanco y naranja `#FF4500`
- Tipografía: Space Grotesk + JetBrains Mono
- Eliminadas todas las referencias a "MiroFish" en UI, locales y prompts LLM

### 🧬 Dual-LLM — reasoning para simulación, structured output para grafo

El proyecto original usa un único LLM para todo. En producción esto falla: los modelos de razonamiento como **MiniMax-M2.7** o **DeepSeek-R1** ignoran `response_format: json_schema`, generando extracciones de grafo con JSON inválido (~50 % de fallos en nuestras pruebas).

Este fork divide el LLM en dos, cada uno optimizado para su tarea:

| Tarea | Por qué necesita lo que necesita | Modelo recomendado |
|---|---|---|
| **Reasoning de simulación** (`LLM_*`) | Los agentes necesitan chain-of-thought, matices, fidelidad de persona | `MiniMax-M2.7`, `DeepSeek-R1`, `gpt-4o`, `qwen-plus` |
| **Extracción de grafo** (`GRAPHITI_LLM_*`) | Graphiti requiere JSON schema estricto — un campo inválido = entidad perdida | `seed-2-0-lite-260228` (BytePlus), `deepseek-chat` v3, `qwen-plus` |

**Impacto real:** ratio aristas/nodos pasó de **0.05 (roto) a ~1.2 (saludable)**.

### 🧠 Memoria de grafo autoalojada (Graphiti + Neo4j)

El proyecto original requiere **Zep Cloud** — servicio externo con límites de uso. Lo reemplazamos completamente con **Graphiti + Neo4j autoalojados**:

- ✅ Sin dependencias de API externas para memoria de grafo
- ✅ Sin límites de uso — simula todo lo que quieras
- ✅ Tus datos permanecen en tu infraestructura
- ✅ Neo4j incluido como servicio Docker — sin configuración adicional

### 💬 Step 5 — Chat con agentes (con fallback LLM)

Modo de interacción profunda después del informe:

- **Chat con el Agente de Informes** — versión conversacional del agente con acceso a 4 herramientas profesionales (InsightForge, PanoramaSearch, QuickSearch, InterviewSubAgent)
- **Chat con cualquier agente simulado** — entrevista a cualquier individuo del mundo virtual
- **Fallback LLM automático** — si la simulación ya terminó o el proceso fue eliminado por OOM, el backend genera respuestas directamente con LLM usando el perfil del agente (timeout reducido a 10s, sin esperas de 2 minutos)
- **Contexto de simulación inyectado** — el LLM recibe el nombre del proyecto, la hipótesis y el resumen de análisis antes de responder, eliminando alucinaciones sobre el producto simulado
- **Encuesta masiva** — envía una pregunta a todos los agentes seleccionados a la vez

### 📊 Informe descargable

Botón `↓ .md` en el header del informe (Step 5) que descarga el informe completo en formato Markdown — portable a Notion, Obsidian, Word, o convertible a PDF con Pandoc.

### 🗂 Proyectos — Acceso rápido al Step 5

En la lista de proyectos (`/projects`), cada proyecto completado con informe generado muestra un botón **`Step 5 →`** que navega directamente a la vista de interacción (`/interaction/:reportId`) — sin tener que recorrer los 5 pasos del wizard.

### 🔐 Autenticación con PocketBase

Autenticación enterprise-ready con [PocketBase](https://pocketbase.io/):
- Login seguro antes de acceder al motor de simulación
- Compatible con cualquier instancia PocketBase (autoalojada o cloud)
- Configurable via `VITE_POCKETBASE_URL`

### 🌍 Soporte multiidioma (es · en · zh)

Traducción completa en español, inglés y chino en los 17 módulos de UI. Las respuestas del backend y los prompts LLM también están en español por defecto.

### 🐳 Docker Compose — despliegue en un click

`docker-compose.yml` completo con:
- Contenedor de la app Mirror
- Contenedor Neo4j con plugin APOC
- Health checks y restart automáticos
- Compatible con [Coolify](https://coolify.io/) para self-hosting sin operaciones

### 🔒 Seguridad de logs

- **Sanitización de request body** — campos sensibles (`api_key`, `token`, `password`…) se redactan como `***` antes de loguear
- **Limpieza automática** — logs con más de 30 días se eliminan al iniciar el servidor
- **RotatingFileHandler** — archivos de máx. 10MB × 5 backups por día

### 🛠 Otras mejoras técnicas

- **Extracción JSON robusta** — 3-pass parser en `LLMClient.chat_json()`: strip de fences → busca bloque ```json embebido → extrae `{}` externo. Nunca falla por respuestas LLM en markdown
- **Recuperación post-OOM** — si el proceso de simulación fue eliminado por OOM, el backend detecta el estado corrupto y permite generar el informe con los datos parciales disponibles
- **Graph building recovery** — detecta estado `graph_building` atascado en reinicios de servidor y recupera el progreso real del grafo
- **Gestión de proyectos** — pantalla de administración con filtros, selección masiva y borrado en cascada (proyecto → simulaciones → informes)
- **Stop simulation** — botón de parada en la vista de ejecución; acceso a resultados parciales
- **Edge labels humanizados** — `GENERATED_PROFESSIONAL_BRAND_KIT_FOR` → `Generated professional...` con truncado a 18 chars
- **Badge de versión y fecha** — visible en todas las vistas para tracking de despliegues

---

## 🏗 Arquitectura

```
Browser → Vue 3 + vue-i18n (es/en/zh) + D3.js
         ↓ PocketBase auth guard
Flask API (Python 3.11)
         ↓
   ┌──────────────┐    ┌──────────────────┐
   │  LLM Client  │    │  Graphiti Core   │
   │  (reasoning) │    │  (graph memory)  │
   │              │    │        ↕         │
   │  Graph LLM   │    │     Neo4j        │
   │  (structured)│    └──────────────────┘
   └──────────────┘
         ↓
   OASIS Simulation Engine (CAMEL-AI)
         ↓
   Report Agent (5 secciones, 4 herramientas)
         ↓
   Step 5 — Chat interactivo + Fallback LLM
```

---

## ⚡ Quick Start

### Prerrequisitos

| Herramienta | Versión |
|------|---------|
| Docker + Docker Compose | Latest |
| LLM API key | Cualquier proveedor compatible con OpenAI |

### 1. Clonar y configurar

```bash
git clone https://github.com/koolbrand/MiroFish.git
cd MiroFish
cp .env.example .env
```

Edita `.env`:

```env
# ===== LLM de simulación — modelo de razonamiento para agentes =====
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.minimaxi.chat/v1       # o OpenAI, Qwen, DeepSeek…
LLM_MODEL_NAME=MiniMax-M2.7

# ===== LLM de extracción de grafo — necesita soporte json_schema =====
# Opcional: si no se configura, usa los LLM_* anteriores.
GRAPHITI_LLM_API_KEY=your_byteplus_key
GRAPHITI_LLM_BASE_URL=https://ap-southeast.bytepluses.com/api/v3
GRAPHITI_LLM_MODEL_NAME=seed-2-0-lite-260228

# ===== Embeddings (usados por Graphiti) =====
EMBEDDING_MODEL=text-embedding-3-small

# ===== Neo4j — iniciado automáticamente por docker-compose =====
NEO4J_PASSWORD=change_me_please

# ===== PocketBase (opcional — para autenticación) =====
# VITE_POCKETBASE_URL=https://your-pocketbase.example.com
```

### 2. Arrancar todo

```bash
docker compose up -d
```

Esto inicia **dos contenedores**: la app Mirror (puerto 8000) y Neo4j. Espera ~40s para que Neo4j inicialice, luego abre:

```
http://localhost:8000
```

### 3. Ejecutar una simulación (5 pasos)

1. **Sube** un documento (PDF, MD o TXT) — un artículo, informe, dossier de producto
2. **Describe** qué quieres predecir en lenguaje natural
3. **Revisa** la ontología de entidades generada automáticamente
4. **Construye** el grafo de conocimiento (Graphiti + Neo4j)
5. **Ejecuta** la simulación multi-agente y lee el informe de predicción
6. **Interactúa** con cualquier agente del mundo virtual en el Step 5

---

## 🛠 Desarrollo local

```bash
# Instalar todas las dependencias
npm run setup:all

# Iniciar backend (puerto 8000) y frontend (puerto 3000) en modo dev
npm run dev
```

El backend requiere Python 3.11 y [`uv`](https://docs.astral.sh/uv/).

---

## 🌐 Despliegue en Coolify (recomendado)

1. Añade un recurso **Docker Compose** en Coolify
2. Apunta a `https://github.com/koolbrand/MiroFish`
3. Configura las variables de entorno
4. Despliega — Coolify gestiona todo

Guía completa: [COOLIFY_DEPLOYMENT.md](./COOLIFY_DEPLOYMENT.md)

---

## 🔧 Variables de entorno

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `LLM_API_KEY` | ✅ | — | API key — LLM de **simulación** (modelo de razonamiento) |
| `LLM_BASE_URL` | ✅ | — | Base URL — LLM de simulación (compatible con OpenAI) |
| `LLM_MODEL_NAME` | ✅ | — | Modelo de simulación (ej. `MiniMax-M2.7`, `gpt-4o`) |
| `GRAPHITI_LLM_API_KEY` | ❌ | = `LLM_API_KEY` | API key — LLM de **extracción de grafo** |
| `GRAPHITI_LLM_BASE_URL` | ❌ | = `LLM_BASE_URL` | Base URL — LLM de grafo |
| `GRAPHITI_LLM_MODEL_NAME` | ❌ | = `LLM_MODEL_NAME` | Modelo de grafo (debe soportar `json_schema`) |
| `EMBEDDING_MODEL` | ❌ | `text-embedding-3-small` | Modelo de embeddings para búsqueda en grafo |
| `EMBEDDING_API_KEY` | ❌ | = `LLM_API_KEY` | API key para embeddings |
| `EMBEDDING_BASE_URL` | ❌ | = `LLM_BASE_URL` | Base URL para embeddings |
| `NEO4J_PASSWORD` | ✅ | `mirofish2026` | Contraseña Neo4j — **cambiar en producción** |
| `NEO4J_URI` | ❌ | `bolt://neo4j:7687` | URI Bolt de Neo4j |
| `VITE_POCKETBASE_URL` | ❌ | — | URL de instancia PocketBase para autenticación |
| `DEBUG` | ❌ | `false` | Modo debug de Flask |

---

## 📋 Comparativa vs original

| Característica | Original | Este fork |
|---|---|---|
| Identidad visual | MiroFish genérico | Mirror by Koolbrand — logo + hero D3 ✅ |
| Arquitectura LLM | LLM único | Dual-LLM — reasoning + structured-output ✅ |
| Calidad extracción grafo | ~50 % JSON inválido | Parser robusto 3-pass + modelo separado ✅ |
| Memoria de grafo | Zep Cloud (externo, limitado) | Graphiti + Neo4j autoalojado ✅ |
| Autenticación | Ninguna | PocketBase ✅ |
| Idiomas | Chino + inglés | + Español (es, default) ✅ |
| Docker Compose | Contenedor único | Multi-servicio (app + Neo4j) ✅ |
| Step 5 — Chat con agentes | ❌ | ✅ con fallback LLM (sin OOM hang) |
| Contexto de simulación en chat | ❌ | ✅ elimina alucinaciones |
| Descarga de informe | ❌ | ✅ formato Markdown |
| Acceso rápido Step 5 | ❌ | ✅ botón en lista de proyectos |
| Seguridad de logs | Body completo logueado | Campos sensibles redactados ✅ |
| Retención de logs | Ilimitada | Auto-cleanup >30 días ✅ |
| Stop simulation | ❌ | ✅ |
| Recuperación post-OOM | ❌ | ✅ |
| Gestión de proyectos | ❌ | ✅ con borrado en cascada |
| Edge labels | SCREAMING_SNAKE_CASE | Humanizados y truncados ✅ |
| URLs API en producción | localhost hardcodeado | Relativas (funciona en cualquier host) ✅ |
| Badge de versión | ❌ | ✅ |

---

## 🤝 Comunidad y contribuciones

Este fork es mantenido por **[KoolBrand](https://koolbrand.com)** — un estudio construyendo herramientas de inteligencia de marca con IA para el mercado hispanohablante y más allá.

Si usas este fork, nos encantaría saber qué estás construyendo. Abre un issue, inicia una discusión, o escríbenos a **hola@koolbrand.com**.

**PRs bienvenidos.** Si añades una funcionalidad, documéntala.

---

## 📄 Créditos

- Motor original **MiroFish** por [666ghj](https://github.com/666ghj/MiroFish) — incubado por [Shanda Group](https://www.shanda.com/)
- Núcleo de simulación: **[OASIS](https://github.com/camel-ai/oasis)** by CAMEL-AI
- Memoria de grafo: **[Graphiti](https://github.com/getzep/graphiti)** by Zep
- Self-hosting: **[Coolify](https://coolify.io/)**

---

<div align="center">

**Built with ❤️ by [KoolBrand](https://koolbrand.com)**

*Primero ensaya. Después decide.*

</div>
