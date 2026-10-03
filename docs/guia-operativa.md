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
- Health endpoint: `/health` (contenedor) y `/health/ready` (monitor externo: Neo4j + disco; 503 si falla)
- Internal port: `8000`
- Copias de seguridad: `ops/backup.sh` (ver «Copias de seguridad» en `COOLIFY_DEPLOYMENT.md`)

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
| `backend/app/services/auto_pipeline.py`, `pipeline_state.py`, `api/pipeline.py` | Modo automático en el servidor: encadena las cinco etapas con los mismos parámetros que la pantalla (rondas a elegir en la portada: 20 / 40 / 72, por defecto 40; `max_rounds` del formulario, validado entre 10 y 100 y guardado en `pipeline.json` para que reanudar respete la elección); estado en `uploads/projects/<id>/pipeline.json`; al arrancar, lo que estaba en marcha pasa a `interrupted` y no se reanuda solo |
| `backend/app/services/type_labels.py`, `POST /api/graph/type-labels`, `frontend/src/lib/typeLabels.js` | **Tipos de la ontología en el idioma de la interfaz** (`SmallBusinessOwner` → «Dueño de pequeño negocio», `WORKS_FOR` → «trabaja para»). Solo para mostrar: los identificadores en inglés no cambian en ningún sitio. Diccionario **compartido por todos los proyectos** en `uploads/type_labels.json` (cada nombre se traduce una vez por idioma con una llamada pequeña al modelo; `en` no se traduce, solo se separa en palabras). La interfaz usa `typeLabel(name, 'entity'\|'relation'\|'attribute')` en plantillas y código: devuelve al instante el identificador en palabras y se repinta sola cuando llega la traducción (lotes de 150 ms). Solo se traducen identificadores (sin espacios ni acentos): la prosa que ya trae el grafo se deja tal cual. Al generar una ontología se calienta en segundo plano (`warm_async`); un proyecto antiguo tarda ~25 s la primera vez (modelo de razonamiento). En el lienzo del grafo, `renderer.setStrings({relation})` + `typeLabelsVersion`. Si se añade un sitio nuevo que muestre un tipo, pasarlo por `typeLabel` |
| `frontend/src/components/TourOverlay.vue` | Tutorial guiado. La capa oscura es **un solo elemento** (la sombra de un hueco, `--tour-dim`, 0,38 de tinta: lo justo para destacar sin tapar la web); cada paso se coloca **antes** de enseñarse (la tarjeta se oculta, la página se desplaza bajo la pantalla oscura, y texto + hueco + tarjeta entran a la vez). No volver a 4 paneles con `transition: all` ni a cambiar el texto antes de medir: eso era el parpadeo. Un desplazamiento de más de 1,5 pantallas es instantáneo; `prefers-reduced-motion` sin animaciones |
| `backend/app/__init__.py` (arranque) | Recuperación al arrancar: proyectos en `graph_building` → `failed`; **informes en `pending/planning/generating` → `failed`** (`ReportManager.fail_unfinished`; sin esto el informe se queda «generándose» para siempre); pipelines `running` → `interrupted`. El servidor es de un solo proceso (`python backend/run.py`): si algún día hay más de uno, estas barridas matarían trabajo vivo del otro |
| `backend/app/services/web_research.py` | Investigación en internet opcional antes de la ontología (`web_research=true` en `ontology/generate` y `pipeline/auto`; etapa «research» del automático). Búsqueda web de MiniMax forzada (`tool_choice: any`) y redacción aparte con los resultados numerados: sin forzar, M3 contesta de memoria con citas inventadas; forzado, busca hasta `pause_turn` sin escribir (medido el 1-oct-2026). Si encuentra algo entra en el material como `files/investigacion-internet.md`; si falla o no encuentra nada, el proyecto sigue sin ella |
| `frontend/src/composables/usePipeline.js`, `components/AutoPipelineBanner.vue` | Estado del automático compartido en pantalla y aviso en las cinco pantallas del proceso (detener, reanudar, seguir la etapa) |
| `backend/app/services/web_research.py` | Investigación opcional en internet antes de la ontología (búsqueda web de MiniMax en servidor); fase 1 busca, fase 2 redacta con los resultados numerados por nosotros; toda viñeta sin referencia [n] se quita; si no encuentra nada o falla, el proyecto sigue sin ella |
| `frontend/src/lib/exampleCases.js`, `components/ExampleTabs.vue` | Cinco ejemplos de la portada (pádel, B2B, precio, crisis, decisión pública): «La multitud» y el informe de ejemplo cambian a la vez; la multitud acaba donde dice el gráfico; textos en `home.cases.<id>.*` |
| `frontend/src/components/GraphPanel.vue`, `lib/graphRender.js`, `GraphTypeSwatch.vue` | Panel del grafo en canvas 2D (d3-force): tipos por forma y tono de marca, etiquetas sin cortar, teclado y lista accesible, «reducir movimiento». **Tres capas en caché** (aristas, nodos, etiquetas) y, entre nodos y etiquetas, la **capa viva** que se pinta cada fotograma: flujo de partículas por cada relación, cometas con reacción en cadena (al llegar a un nodo destella y puede lanzar otros), latido de los nodos principales, centelleo y un barrido tipo sonar. Va POR DELANTE de los nodos (antes iba por detrás y los nodos opacos la tapaban) y por detrás del texto |
| `frontend/src/lib/miniMarkdown.js` | Markdown mínimo SIN HTML para lo que escriben las personas simuladas y el modelo (posts, chat, encuestas). No uses `v-html` con texto de la API |
| `backend/scripts/recsys_memory.py` | Parche de memoria del recomendador de OASIS (evita el kill -9 por OOM en simulaciones largas); `RECSYS_MEMORY_PATCH=0` lo desactiva |
| `backend/app/utils/recsys_prewarm.py` | Precarga del modelo del recomendador al arrancar (caché en el volumen `mirofish_hf_cache`) |
| `backend/app/services/report_pdf.py`, `backend/app/assets/fonts/` | PDF del informe con la marca de Simuloo (WeasyPrint + Markdown): portada con cifras, pie con página y fuentes Inter Tight / JetBrains Mono embebidas. Se pide con `GET /api/report/<id>/download?format=pdf` (sin `format`, sigue el `.md`) |
| `backend/app/utils/docx_io.py`, `backend/scripts/generar_plantilla_docx.py`, `backend/app/assets/brief/` | **Word (.docx)**: leer (sin librería: zip + lxml; defensas contra bombas de descompresión y de entidades, XXE y zips raros; cambios sin aceptar: se lee lo insertado, no lo borrado; títulos → `#`, listas → `-`, tablas → `a \| b`) y escribir (`build_docx` desde Markdown básico: títulos reales de Word, viñetas, citas, negrita/cursiva). Sube `.docx` (`FileParser`, `Config.ALLOWED_EXTENSIONS`, firma en `security.py`, también en `/api/brief/check`); `POST /api/brief/draft-file` devuelve el borrador del brief en Word o PDF (`render_brief_pdf`: misma maqueta, etiqueta «Brief inicial» y sin la nota del informe). La plantilla de brief es `frontend/public/plantilla-brief-simuloo.docx`, **generada** desde `assets/brief/plantilla-brief-simuloo.md` (un test falla si se desincronizan). **Identidad de marca en Word** (pedida por Adrián el 2-oct-2026): lima/tinta, Inter Tight y JetBrains Mono con sustituta (`fontTable.xml`: Arial/Consolas), título con bloque lima (sombreado de carácter), cita como nota con barra lima, cabecera con la marca y el tipo de documento y pie con «Página X de Y» (campos `PAGE`/`NUMPAGES`); `build_docx(md, locale=, kind='template'|'draft')`. La marca va en cabecera, pie y estilos, **no en el cuerpo**, y el lector no los lee (no se cuela en el brief). **Probar un `.docx` en Word de verdad:** el sandbox de Word solo abre sin pedir permiso lo que esté en `~/Library/Containers/com.microsoft.Word/Data/Documents/` (con otra ruta, p. ej. iCloud, sale «Conceder acceso al archivo» y la herramienta se cuelga hasta pulsar Aceptar); desde ahí `open_document` y `export_pdf` dibujan el documento como Word `.doc` antiguo y `.docx` con contraseña (contenedor OLE) → mensaje «guárdalo como .docx» (`api.docxOld`) |
| `frontend/src/components/ReportDownloads.vue` | Botones PDF (lima, con estado ocupado) y `.md` del informe, en los pasos 4 y 5; muestra el error que devuelve el servidor |

### Aislamiento por usuario (`utils/access.py`)

- **Cada usuario ve solo sus proyectos.** `Project.owner_id` = id del usuario de PocketBase que lo creó. Simulaciones e informes no guardan dueño: lo heredan por la cadena informe → simulación → proyecto (`owner_of_*`, leyendo el JSON del disco sin crear carpetas).
- **Un único control central** (`authorize_request`, en el `before_request` de `__init__.py`) mira todos los ids que nombra la petición —URL, query, JSON y formulario: `project_id`, `simulation_id`, `report_id`, `graph_id`, `task_id`— y responde 404 («No encontrado», nunca 403) si no son del usuario. Una ruta nueva con ids queda cubierta sola; solo hay que filtrar a mano **los listados** (`can_see`, `visible_project_id`, `visible_simulation_id`, `visible_task`) y **filtrar antes de cortar con `limit`**.
- **Identidades**: usuario de PocketBase (ve lo suyo) · clave estática `API_AUTH_TOKEN` o desarrollo sin auth (admin, ve todo) · secreto interno del modo automático (ve todo) · ninguna (nada). `identify_bearer` saca el id del `record` de `auth-refresh` (o del claim `id` del JWT) y lo cachea 5 min.
- **Sin dueño** (anteriores a este cambio o creados con la clave de emergencia): solo el admin, salvo `LEGACY_OWNER_ID` = id de un usuario de PocketBase, que los hereda. Tareas: llevan `owner_id` en `metadata`; una tarea sin dueño pasa por id (no se adivina) pero no sale en los listados.
- **Cambiar el dueño**: `PUT /api/graph/project/<id>/owner` con `{"owner_id": "<id de PocketBase>"}` (o `null` para dejarlo sin dueño). **Solo la clave estática (admin)**: un usuario recibe 403 aunque sea el dueño, y el secreto interno también. Existe porque los proyectos creados antes del aislamiento quedaron sin dueño y `LEGACY_OWNER_ID` los reparte todos a una sola persona (Earmod, de Víctor, lo veía solo Adrián). Los ids de PocketBase son de 15 caracteres alfanuméricos; el endpoint admite 8–32. Se loguea cada cambio. Para usarlo en producción hace falta el ciclo de clave temporal (`API_AUTH_TOKEN`).
- **Pendiente (paso 2)**: organización + «compartir» y rol admin para usuarios. El esquema ya lo admite: añadir `org_id`/`visibility` al proyecto y ampliar `can_see`.
- Tests: `tests/test_access.py` (dos usuarios cruzados y el cambio de dueño; desactivando el control fallan 12 de 23).

### Al tocar el estado en disco (`utils/fs.py`, `models/project.py`, `ReportManager`, `SimulationManager`)

Auditoría del 1-oct-2026 (cinco revisores en paralelo; cada hallazgo se reprodujo antes de arreglarlo). Reglas que salieron:

- **Todo JSON de estado se escribe con `atomic_write_json`/`atomic_write_text`** (temporal en la misma carpeta + `os.replace`), nunca con `open(path, 'w')`: truncar al abrir deja a un lector concurrente con un JSON vacío o a medias y un corte lo deja roto para siempre. Con `create_dir=False` (lo que usan `save_project`, `_save_simulation_state`, `_save_run_state`, `ReportManager`) un hilo que sigue vivo **no resucita** la carpeta de algo que se acaba de borrar.
- **Todo JSON de estado se lee con `read_json_or_none`**: ilegible = «no existe» + una línea en el log, y un listado salta ese elemento en vez de dar 500 a todos los usuarios. La excepción es el control de acceso (`utils/access.py`): un archivo que **existe pero no se lee** cuenta como «existe, sin dueño» (solo admin), nunca como «no existe» (eso dejaba pasar a cualquiera).
- **Un hilo largo no guarda el objeto que leyó al empezar**: usa `ProjectManager.update_project(id, mutator)`, que relee la copia más reciente bajo el candado del proyecto y toca solo sus campos. Antes la construcción del grafo restauraba en silencio el nombre y el dueño viejos al terminar.
- **Borrar es completo o no es**: `DELETE /project` aborta con 500 si falla la cascada (antes seguía y dejaba huérfanos) y borra el grafo de Neo4j (también `reset` y la reconstrucción forzada). `ReportManager._deleted_ids` evita que el hilo que escribía un informe borrado lo recree.
- **Arranque** (`app/__init__.py`): proyectos en `graph_building` → `failed`; informes sin terminar → `failed`; **simulaciones en marcha → `failed`** (`services/boot_recovery.py`; conserva contadores y `actions.jsonl`); pipelines `running` → `interrupted`. Cada paso va en su propio `try`.
- `ReportConsoleLogger` filtra por hilo: los loggers son globales y sin el filtro el `console_log.txt` de cada informe recogía las consultas de los demás usuarios.
- `ReportManager.get_report_by_simulation` devuelve el informe que se está escribiendo, si no el último terminado, si no el último fallido (cada «generar» crea uno nuevo; devolver «el primero del listado» enseñaba uno fallido viejo).
- `/api/graph/build` valida `chunk_size` (100–5000) y `chunk_overlap` (0–mitad); `split_text_into_chunks` siempre avanza. Los vectores `*_embedding` no salen del adaptador de Neo4j (pesaban 17 KB por nodo y por relación, en la pantalla y en cada prompt de perfil).

### Al tocar el ciclo de vida de las simulaciones (`simulation_runner.py`, `scripts/run_parallel_simulation.py`)

- **El subproceso de OASIS NO termina al acabar la simulación**: entra en «modo de espera de comandos» para contestar entrevistas (informe y chat del paso 5) y, hasta ahora, solo salía con `close_env` o al apagar el servidor — nadie lo enviaba. Cada uno ocupa ~1 GB (BERT + agentes) y el contenedor tiene 4. Mientras vive, `runner_status` ya es `completed`: **estado y proceso son cosas distintas** (`SimulationRunner.live_processes()` es lo que cuenta para la memoria).
- Por eso: (1) el script se cierra solo tras `SIM_IDLE_TIMEOUT_SECONDS` (1200) sin entrevistas; (2) `Config.MAX_CONCURRENT_SIMULATIONS` (2) procesos vivos como máximo: antes de lanzar otro, `_ensure_capacity` cierra los que ya terminaron y, si aun así no cabe, responde con el mensaje `api.simTooManyRunning` (nunca mata una que esté trabajando); (3) borrar una simulación o un proyecto, o reiniciar con `force`, mata el proceso aunque esté `completed` (`terminate_if_alive`). Un proceso cerrado a propósito tras terminar queda `completed`, no `failed` (`_closed_when_done`).
- `start_simulation` toma un candado por simulación: dos «iniciar» a la vez lanzaban dos procesos sobre la misma carpeta. El monitor de un proceso **cede** si otro lo sustituyó (`_processes[sim] is process`): antes, tras «reiniciar con force», el monitor viejo borraba el registro del proceso nuevo y este quedaba imparable. Solo reescribe `run_state.json` si algo cambió (o cada 30 s).
- `check_env_alive` exige además que el proceso esté vivo (`env_status.json` se queda en «alive» si muere de golpe) y `interview_agents_batch` cae al modelo también ante `TimeoutError`: antes cada entrevista esperaba 180 s a un entorno muerto.
- `ZepGraphMemoryUpdater`: el envío a Neo4j/modelo se hace **fuera** de `_buffer_lock` y del candado global del gestor; `stop()` tiene plazo (60 s; 5 s al apagar) y vuelca el atraso en trozos de 25 (antes, un solo episodio gigante con el candado cogido: parar una simulación bloqueaba las demás).
- Modelo: `LLM_TIMEOUT_SECONDS` (240) y `LLM_MAX_RETRIES` (2) en los tres clientes (antes 600 s × 3 = 30 min por llamada). El informe reintenta cada sección 3 veces con espera de 15 y 45 s. Neo4j: se reintentan `ServiceUnavailable`/`SessionExpired`/`TransientError` (no heredan de `OSError`).
- `TaskManager` se limpia solo (cada 30 min al crear tareas) y también los registros rotados `.log.N`.
- **Publicaciones iniciales (semillas) y el cursor del registro** (2-oct-2026, a raíz de «muchos comentarios repetidos» de Víctor): el registro de acciones (`actions.jsonl`, lo que enseña el paso 3 y lo que cuentan los totales) se alimenta leyendo la tabla `trace` desde `last_rowid`. Las semillas se anotan a mano en la ronda 0 **y** quedan en `trace`; si `last_rowid` sigue en 0 al empezar el bucle, la primera ronda con actividad las vuelve a leer y las anota de nuevo (en las 18 semillas de dos simulaciones reales pasaba con todas, a la vez y una vez por plataforma: el 14 % de lo que veía Víctor). Tras sembrar hay que hacer `last_rowid = get_last_trace_rowid(db_path)`. Segundo fallo en el mismo bloque: en Twitter las semillas iban a un diccionario con el agente como clave, así que un agente con 2 o 3 semillas publicaba solo la última (de 12 semillas se publicaban 5; las otras 7 constaban como publicadas sin existir). Ahora ambas plataformas usan `add_action_for_agent`. Prueba real antes/después con 12 rondas de la misma simulación: copias sobrantes 17 → 0, semillas publicadas en Twitter 5 → 12 de 12, y la base de datos cuadra con el registro (51 = 12 + 39; 73 = 12 + 61). Tests en `tests/test_simulation_trace.py`. **En la pantalla (paso 3, `Step3Simulation.vue`)**: los mensajes iniciales (CREATE_POST de la ronda 0) salen en UNA tarjeta («Mensaje inicial · publicado en las dos plataformas», con «Las dos plataformas» en la cabecera de la tarjeta); en las simulaciones guardadas antes del arreglo, las copias del fallo (mismo agente, plataforma y texto que una semilla, en una ronda posterior) **no se enseñan ni se cuentan**, y las cifras de las dos tarjetas verdes se descuentan igual; «Se repite N veces» + interruptor queda solo para un agente que de verdad repite un mensaje (0 casos medidos). **Lo que NO era**: los agentes no se repetían a sí mismos (0 casos en 424 publicaciones/comentarios de dos simulaciones); las simulaciones ya guardadas conservan sus copias en el registro (la pantalla las agrupa).
- **Quién escribe cada mensaje inicial** (3-oct-2026, caso de una zona de bajas emisiones): `poster_agent_id` salía del TIPO de entidad y se repartía por turnos entre los del mismo tipo, así que «El gremio del taxi aclara…» lo publicaba la plataforma ciclista, «Soy vecina de 72 años» «familias con niños» y «Como comerciante del centro» «autónomos con furgoneta» (5 de 12 mensajes de una ejecución real, con 2–4 agentes por tipo). Ahora (`simulation_config_generator.py`): el prompt enseña **todos** los agentes con su id (antes 3 nombres por tipo y ningún id) y pide `poster_name` + `poster_agent_id` por mensaje; el autor se resuelve **por nombre** (sin acentos/mayúsculas, tolera «Nombre (Tipo)» si casa con uno solo), si no por id (solo si el tipo dicho no lo contradice) y por tipo **solo si hay un único agente de ese tipo**; lo que no se resuelve se pregunta aparte con una segunda llamada pequeña (`_ask_authors`) y, si tampoco, **el mensaje se descarta** (mejor sin él que con el autor equivocado; queda en el log). `poster_type`/`poster_name` del config son los del agente real. Los ejemplos del prompt son genéricos a propósito: con el caso de la ZBE dentro, el modelo los repetiría en cualquier simulación. Probado con MiniMax-M3 (el de producción): 10 de 10 mensajes con su autor. **Las simulaciones ya preparadas conservan su `simulation_config.json` con los autores viejos**: hay que volver a preparar para corregirlas. Tests: `tests/test_initial_posts_author.py`.
- **No resuelto (propuesto)**: una caída del proveedor durante la simulación produce rondas sin acciones y la simulación «completa» (OASIS captura el error de cada agente); `plan_outline` cae a un índice genérico sin avisar; no hay reanudación de un informe a medias.

### Al tocar la superficie HTTP (`app/__init__.py`, rutas de `api/`)

- **Topes de cuerpo por ruta**: `MAX_BODY_BYTES` (1 MB) para todo; solo `UPLOAD_PATHS` (`/api/graph/ontology/generate`, `/api/pipeline/auto`, `/api/brief/check`) admiten 50 MB. Se fija en el `before_request` **antes de leer nada**. Con 50 MB para todo, 20 POST anónimos de 42 MB agotaban los 4 GB del contenedor.
- **Primero se autentica, luego se mira el cuerpo**: antes se parseaba y volcaba al log (DEBUG) el cuerpo JSON de cualquier POST, también anónimo y a rutas inexistentes. Ahora el log solo lleva la **forma** (`message: str[120]`) y los ids, nunca el contenido (briefs, chats y prompts quedaban en `backend/logs`).
- **Errores 500**: el cliente no recibe rutas, hosts ni trazas. `_looks_internal` detecta mensajes con rutas/URLs, `host:puerto` o trazas y los sustituye por «Ha ocurrido un error en el servidor (ref xxxx)» (el original queda en el log con la misma ref); los mensajes pensados para la persona («El LLM no respondió») se respetan. La tarea de construcción del grafo ya no guarda el traceback. Cabeceras `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy` y `Cache-Control: no-store` en `/api/*` (sin CSP: la app usa estilos en línea y fuentes de Google).
- **`API_AUTH_REQUIRED` es estricto** (`env_flag_on_by_default`): solo `false/0/no/off` lo apagan. Con `== 'true'`, un `1`, `yes` o ` true` dejaba la API **abierta** (todos admin) sin avisar.
- **Topes de coste de UNA petición** (el límite de tasa cuenta peticiones, no llamadas al modelo): ≤10 archivos, ≤8 imágenes (cada una es una llamada al modelo de visión; eran 3 y el material real de northkin trae 6, lo que rechazaba una subida normal: el límite se eligió sin datos), ≤1.000.000 caracteres de texto en total (el grafo gasta un episodio por ~500), imágenes ≤25 Mpx (una «bomba» de 140 KB declaraba 12.000 × 12.000), ≤20 entrevistas de ≤2.000 caracteres, plazos de las órdenes al entorno de 5–120 s, ≤8 perfiles en paralelo, mensaje y historial del chat acotados y **sin rol `system`** (el cliente mandaba el historial tal cual al modelo), y como mucho 3 pipelines automáticos vivos (2 por persona) → 429.
- Un nodo solo se lee desde SU grafo (`GraphitiNodeClient.in_graph`): `get_entity_with_context` buscaba el uuid en toda la base y el control de acceso solo mira el `graph_id` de la ruta.
- El proceso de simulación no hereda `API_AUTH_TOKEN`, `SECRET_KEY` ni `NEO4J_PASSWORD` (solo necesita las claves del modelo).
- Sin resolver (propuesto): límite de tasa por usuario y no solo por IP; cuota de disco por persona; servidor de producción (hoy `app.run(threaded=True)` de Werkzeug; el estado vive en memoria, así que tendría que seguir siendo un solo proceso: waitress/gunicorn `gthread` con 1 worker).

### Al tocar la interfaz: errores, sondeos y carga (`frontend/src/api/index.js`, `lib/connection.js`, `i18n/`, `router/`)

- **Cliente HTTP** (`api/index.js`): `error.message` ya es una frase para la persona (la del servidor si la trae; si no, una por estado en `errors.*`; el texto técnico queda en `error.detail`). **Un 401 suelto no echa a nadie**: se renueva la sesión (una sola vez a la vez) y se repite la petición; solo si PocketBase la rechaza se limpia y se lleva a `/login`; si PocketBase no contesta, no se toca la sesión. Un 504 de un POST no se reintenta (el proxy se rindió pero la app pudo ejecutarlo).
- **«Sin conexión»**: `lib/connection.js` cuenta fallos de red seguidos (3 = sin conexión) y `ConnectionBanner.vue` lo dice; la primera respuesta del servidor lo quita. Antes un servidor caído dejaba los sondeos fallando en silencio.
- **Informe** (`Step4Report.vue`): un informe fallido o inexistente es un **estado terminal** con motivo y botón «Volver a generar». Se reconoce la acción `error` del registro (la que de verdad escribe el servidor), el `status: failed` del informe (se mira al abrir y cada ~10 s) y el 404. Antes se quedaba en «Generando…» para siempre.
- **Entrevista del brief** (`BriefAssistant.vue`): si el modelo falla, la pregunta y lo escrito vuelven a su sitio y hay «Reintentar»; cerrar y reabrir tras un fallo vuelve a preguntar; Esc cierra y el foco no se sale del diálogo.
- **Salir mientras se analiza el material** (`MainView.vue`): tras cada `await` largo se mira `unmounted`; la persona no es «teletransportada» a un proyecto al terminar. `pendingUpload.launching` hace que la portada no deje lanzar otra vez y, al terminar, vacía el formulario (si no, un segundo «Iniciar» duplicaba el proyecto). Los sondeos (`startGraphPolling`, `startPollingTask`) paran el anterior antes de empezar y no arrancan en una pantalla cerrada.
- **Chat del paso 5**: cada respuesta se escribe en la conversación **de la pregunta** (`appendToThread(threadKey, …)`), no en la que esté a la vista. Abrir el menú de individuos ya no cambia `chatTarget` (guardaba la conversación del informe en la clave equivocada). El explorador numera sus cargas para que una respuesta tardía no pise la selección.
- **Paso 3**: el feed se ordena por ronda y hora al fusionar (el servidor las manda de la más nueva a la más antigua) y pinta las últimas 300 tarjetas (`FEED_LIMIT`). `run-status/detail` ya no manda `twitter_actions`/`reddit_actions` (triplicaban el tamaño).
- **Carga**: rutas con `import()` y `es` como único idioma dentro del paquete (`i18n/index.js`; `en`/`zh` se descargan al elegirlos, `setLocale()`): el paquete de entrada pasó de **941 kB (313 kB comprimido) a 295 kB**. Tras un despliegue, un trozo con el nombre viejo ya no existe: `router.onError` recarga la página una vez (con tope). Una dirección inexistente lleva a la portada.
- **Almacenamiento bloqueado** (navegación privada, política del equipo): `i18n`, `index.html` y el almacén de sesión de PocketBase (`lib/pocketbase.js` usa uno en memoria) ya no tiran la app. **Todo acceso a `localStorage`/`sessionStorage` va en `try/catch`.**
- Logotipo de las pantallas del proceso = enlace real a `/` (`.brand-link`); casillas de `/projects` con nombre accesible; Enter con un método de entrada de texto (IME) no envía el chat; el login distingue «credenciales incorrectas» de «sin conexión» y de «demasiados intentos».
- **Sin resolver (propuesto)**: un `usePolling` común con backoff, pausa con la pestaña oculta y plazo corto (los sondeos comparten el plazo de 5 min de las peticiones largas); reanudar un informe a medias en vez de empezar de cero; reiniciar el estado de las vistas al cambiar solo el parámetro de la ruta.

### Al tocar la operación: despliegue, configuración, logs y CI (`Dockerfile`, `docker-compose.yml`, `config.py`, `utils/logger.py`, `.github/`)

Auditoría de operación del 1-oct-2026; lo que se midió y lo que se decidió:

- **Las variables de entorno se leen con `env_int/env_float/env_bool/env_str`** (`config.py`), nunca con `int(os.environ.get(...))`: una variable **vacía** (compose pasa `VAR=` cuando no está definida; Coolify también) o con un typo (`30s`) tumbaba la app al importar y el contenedor entraba en bucle de reinicios. Vacío = «sin definir»; inválido o fuera de rango = aviso por stderr y valor por defecto. Fuera de `config.py` (scripts de la simulación, `run.py`) lo mismo, con una función local. Test: `test_config_env.py` (importa `Config` en un proceso limpio con valores basura).
- **Coolify reescribe el compose y añade `env_file: .env` a los dos servicios** (comprobado con la API el 1-oct-2026): cualquier variable definida en su panel llega al contenedor aunque no esté en `docker-compose.yml`. El informe de operación decía «el compose no pasa 16 variables»: con Coolify no es cierto, no se han añadido. Sin Coolify (`docker compose up` a pelo) sí hay que listarlas. Coolify usa **`docker-compose.yml`** (`docker_compose_location`); el `.yaml` era un duplicado idéntico y se borró.
- **Salud en dos niveles, a propósito separados**: `/health` (Flask vivo; la sonda del contenedor) y `/health/ready` (`utils/health.py`: Neo4j con `verify_connectivity` + escritura/espacio en el disco de datos, `MIN_FREE_DISK_MB`; caché de 10 s; solo booleanos). El servicio de la app **no** espera `depends_on: service_healthy` de Neo4j: con Neo4j caído, un redespliegue dejaría sin servicio también el login y los informes ya hechos. El healthcheck de Neo4j (`wget` al 7474) solo informa.
- **Apagado**: `init: true` (tini recoge los procesos de simulación huérfanos) y `stop_grace_period: 60s` en la app y en Neo4j. El manejador de SIGTERM ya existía (`register_cleanup`: para los actualizadores de memoria y termina los procesos); con los 10 s por defecto Docker la mataba a medias. Lo que quede en «running» lo marca fallido `boot_recovery` al arrancar.
- **Un solo manejador de archivo de log**: cada `get_logger('mirofish.x')` abría su propio `RotatingFileHandler` sobre el mismo archivo (26 a la vez) y al rotar se pisaban. Ahora los `mirofish.*` no tienen manejadores y propagan al principal (`mirofish`); un logger nuevo debe llamarse `mirofish.<algo>` o no escribirá en el archivo. Test: `test_logging_setup.py`.
- **Dependencias**: `pip-audit` daba **317 avisos en ~30 paquetes** y `npm audit` 4 altos. Se subió lo que se podía sin romper nada (Flask 3.1.3, Werkzeug 3.1.9, urllib3 2.8, requests, cryptography, pyjwt, pypdf, python-multipart, starlette...; frontend `npm audit fix` → 0) y **Pillow se fuerza a ≥12.3** (`override-dependencies`: camel-ai pedía `<11`; Pillow lee imágenes de usuarios). `Image.open(..., formats=[PNG,JPEG,WEBP,GIF])` y una imagen truncada da un 400 claro (`api.imageUnreadable`), antes un 500. **Sigue sin resolverse** lo que bloquean camel-ai/OASIS: `graphiti-core 0.11.6` (`pip-audit` lo da por corregido en 0.28.2; no se sube porque 0.28.2 exige `neo4j>=5.26` y `camel-oasis 0.2.5` fija `neo4j==5.23.0`, comprobado en los metadatos de PyPI el 1-oct-2026), `transformers 4.57`, `unstructured 0.13`, `nltk`. Se revisa con el job `audit` de CI (informativo).
- **PyTorch solo CPU en Linux**: la imagen llevaba `torch 2.9.1+cu128` con `nvidia/` (4,3 GB) y `triton` (0,6 GB) en un servidor sin GPU. El `torch-backend = "cpu"` que había en `pyproject.toml` solo vale para `uv pip`, no para `uv sync`. Ahora `torch==2.9.1` es dependencia **directa** (uv solo aplica `[tool.uv.sources]` a las directas) con el índice CPU de PyTorch solo para Linux (en macOS PyPI ya da CPU/MPS). `uv sync --frozen --no-editable --no-dev` en el Dockerfile (`pytest` queda dentro igualmente: lo exige `camel-oasis`). Resultado medido: imagen de **4,33 GB → 430 MB**, `torch 2.9.1+cpu`, sin `nvidia/` ni `triton`.
- **CI** (`.github/workflows/ci.yml`): pytest en Python 3.11 con las librerías del PDF (WeasyPrint) instaladas, `uv lock --check`, build del frontend, `docker compose config` + build de la imagen sin publicar, y un job `audit` informativo. `docker-image.yml` lo exige (`needs: ci`) antes de publicar `latest`. `test_locales_parity.py` compara claves y `{variables}` de es/en/zh.
- **Copias**: dos vías. (1) `ops/backup.sh` en el servidor (ficheros en caliente; grafo parando Neo4j unos segundos), probada de punta a punta con volúmenes de prueba, pero **al servidor de Coolify no se llega por SSH** (`kooldock`/`koollab` rechazan las claves del MacBook y del Mac mini) y no está programada. (2) **Copia automática por tirón** (`GET /api/backup/export`, `services/backup_export.py`, `api/backup.py`): credencial propia `BACKUP_TOKEN` (cabecera `X-Backup-Token`, ≥ 32 caracteres, **solo lectura y solo vale para esa ruta**; sin ella la ruta da 404), un `.tar.gz` de `uploads/` con los documentos originales, SQLite por la API de respaldo (coherente aunque se esté escribiendo) y `MANIFIESTO.json` con sha256 por fichero; el Mac mini la recoge cada noche (`ops/backup_remoto.sh` + launchd `com.koolbrand.simuloo-backup`, 04:15), la verifica (sha256, `gzip -t`, manifiesto, tamaño en el NAS) y la guarda en `Koolbrand/Bianka/entregables/003 - Simuloo/_copias-automaticas/` con rotación de 21. **Sin aviso automático si falla** (`--comprobar` existe; el vigilante de la casa no se ha tocado). El grafo no va en esta copia (se reconstruye desde los originales). **Instalada y verificada en producción el 2-oct-2026** (Mac mini, `~/.koolbrand/bin/simuloo-backup.sh`, token en `~/.koolbrand/secrets/`, launchd cargado y lanzado una vez con `launchctl kickstart`): 3 proyectos, 59 ficheros, 40 MB (10,8 MB comprimidos), 3 s. **Simulacro de restauración hecho**: traída desde el NAS, 59 ficheros con el sha256 del manifiesto, las 4 bases SQLite con `integrity_check = ok`, Earmod con su dueño. Matriz de seguridad comprobada en producción: sin token, token malo, clave de administrador (como Bearer y como cabecera de copia), token de copia en otras rutas y POST → 401/405/404; solo el token de copia entra.
- **Sin resolver (propuesto)**: servidor de producción (hoy el de desarrollo de Werkzeug; el estado vive en memoria, así que sería gunicorn/waitress con **1 worker** y varios hilos); usuario no root en el contenedor (los volúmenes existentes son de root: haría falta un `chown` único); `pids_limit`/`cpus`; alertas (nadie mira `/health/ready` todavía); fijar la revisión del modelo de HuggingFace en `recsys_prewarm.py` (hoy se baja sin fijarla).

### Al tocar el grafo (`graphRender.js`)

- **Orden de capas**: aristas → nodos → capa viva (`_flow`, `_bloom`, `_sweepFx`, `_pulses`, `_flashFx`) → etiquetas → anillos de selección. Lo que se mueva siempre va en la capa viva (dos `drawImage` + trazos baratos); nada animado dentro de las capas en caché, que se repintan enteras.
- **Se autolimita**: `_fxAdapt` baja a la mitad de partículas si la animación cuesta > 6 ms de media, y `_flow` pone la mitad mientras se repinta la escena (arrastre, zoom, física). Con «reducir movimiento» no se pinta nada de la capa viva y el bucle se para (0 % de píxeles cambian).
- **Probarlo**: banco con grafo sintético de N nodos en la sesión (`grafo/h.js`, `perf.js`, `secuencia.js`). Medido el 1-oct-2026 con 460 nodos / 610 aristas SIN GPU: 60 fps en reposo y 57–58 arrastrando (antes 46–51).
- **Trampa que costó descubrir**: al cambiar de vista el panel se ensancha en ~0,7 s y `fit(true)` lanza una animación con el ancho de entonces; si termina después del último `resize`, pisa el ajuste bueno y el grafo queda descentrado a medio tamaño. `resize()` cancela esa animación (`zoomTween`) cuando el usuario no ha tocado nada. Comprobarlo: 10 cargas seguidas, centro del grafo = W/2 (`diag2.js`).

### Al tocar el agente de informes (`report_agent.py`)

- El modelo a veces escribe la llamada a herramienta sin el `<` inicial (`tool_call>`) o sin cerrar (medido el 1-oct-2026: 3 de 6 respuestas de una sección). `_parse_tool_calls` lo tolera y `_clean_section_text` decide si un texto vale como sección: **nada con restos de `tool_call` o con forma de llamada se guarda como contenido**; se pide de nuevo y, si el cierre forzado tampoco da texto, la sección sale como «no pudo redactarse» (`report.sectionGenLeakContent`) y queda en los avisos del informe. Tests en `backend/tests/test_report_tool_call.py`.

### Al tocar el PDF del informe

- **Fuentes**: archivos `.ttf` en `backend/app/assets/fonts/` (subconjuntos latinos, licencia OFL en `LICENSE.txt`). Una familia de WeasyPrint por peso (`IT-400/500/700/800`, `JBM-400/500/700`): los nombres internos de los TTF no coinciden con sus pesos, y mezclarlos en una sola familia hacía caer a una fuente del sistema. Lo que no está en el subconjunto (→, ✓, ≥) cae a DejaVu y el chino a WenQuanYi (por eso están en el `Dockerfile`).
- **Seguridad**: el texto del informe lo escribe un modelo. Se escapa el HTML (`<` y `&`), las imágenes se sustituyen por su texto alternativo y solo se dejan enlaces `http`/`https`/`mailto`. El `URLFetcher` de `render_pdf` solo deja cargar `data:` y los `.ttf` de `FONT_DIR`: nada de red ni de archivos del servidor.
- **Coste**: ~1–3 s por informe y unos 150 KB. Máximo dos PDFs a la vez (`threading.BoundedSemaphore(2)`); si falta pango responde 501 `api.pdfUnavailable` y la app sugiere el Markdown.
- **WeasyPrint ≥ 70** (la API de `URLFetcher` cambió) y necesita pango/harfbuzz del sistema. En macOS: `brew install pango` y arrancar el backend con `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`, **directamente y sin `nohup`** (el binario protegido por SIP descarta las variables `DYLD_*`). Los tests de PDF se saltan solos si falta pango.
- Al cambiar la maqueta, mirar el PDF de verdad (PyMuPDF: `fitz.open(...)[n].get_pixmap(dpi=60).save(...)`), no solo el HTML: portada, una página larga, tablas y un informe en chino.

### Auditoría UX/UI (1-oct-2026) — reglas que salieron de medir

- **Color**: solo tokens de `koolbrand.css`. Sobre tinta, el texto gris es `--kb-muted-on-dark` (#8A8A8A: 5,5:1; el #6E6E6E daba 3,7); sobre `--kb-soft` (#ECECEC), `--kb-text-on-soft` (#2A2A2A); «bien» = `--kb-ok-*` (lima oscuro), «mal» = `--kb-danger-*`. Nada de verdes, ámbares ni violetas de MiroFish: lo que se distinguía por color se distingue también por texto, forma o icono.
- Borde de campos y controles `--kb-control-line` (#858585, ≥ 3:1); foco visible de 2 px; objetivos ≥ 24 px; texto ≥ 12 px (rótulos mono de ≤ 12 caracteres, 11 px).
- Antes → después medido con `probar-ui.js` en 12 pantallas: fallos de contraste 871 → 0, fallos 2.5.8 de 1 a 0, color de marca 85–95 % → 99–100 %. Medir de nuevo al tocar una pantalla.
- Diálogos: `role="dialog"`/`alertdialog`, foco dentro al abrir, Tab atrapado, Escape cierra y el foco vuelve a quien lo abrió.

### Lo que ve la gente: nada de «.md»
- **Un `.md` no le dice nada a quien no es técnico** (lo señaló Adrián el 1-oct-2026). A la vista solo hay **PDF, Word (.docx), TXT e imágenes**; el backend sigue aceptando `.md`. El texto pegado se guarda como `texto-pegado.txt`; el borrador de la entrevista, como `brief-simuloo.txt` al añadirlo al material y Word/PDF al descargarlo; la plantilla, en Word. El botón del informe en texto dice «Descargar el texto del informe» (no «.md») y el PDF es el principal. **Sigue sin leerse PowerPoint** ni `.doc` antiguo: la app dice cómo arreglarlo (pegar el texto o exportar a PDF).
- Al añadir un formato nuevo, tocar los CUATRO sitios: `FileParser.SUPPORTED_EXTENSIONS`, `Config.ALLOWED_EXTENSIONS`, la firma en `security._BINARY_MAGIC_SIGNATURES` y las listas del frontend (`Home.vue`: `accept` y `readable`; `BriefAssistant.vue`: `TEXT_EXT`), más `home.supportedFormats` en los tres idiomas.

### Textos y avisos de la interfaz (1-oct-2026, a raíz de lo que vio Adrián)
- **Límites de subida avisados al añadir, no al lanzar**: `frontend/src/lib/uploadLimits.js` es el ESPEJO de `MAX_UPLOAD_FILES` (10) y `MAX_UPLOAD_IMAGES` (8) del servidor; `Home.vue` rechaza lo que sobra con un aviso («máximo 8 imágenes, 2 no se han añadido; quita alguna»). Si se cambia el tope en el servidor, cambiarlo aquí (el servidor sigue mandando). Antes el tope de imágenes era 3, **elegido sin datos**, y rechazaba el material real de northkin (6 imágenes): la persona solo veía «el análisis ha fallado».
- **Un rechazo del servidor que la persona puede resolver (400/413/415/422) se enseña con SU mensaje** en el banner de fallo de `MainView.vue`, sin «Reintentar» (fallaría igual) y con «Volver al inicio» (el formulario conserva los archivos). Los demás fallos siguen con el texto general y el mensaje en «Detalle técnico».
- **«Ronda» se explica en la portada** (`home.roundsWhat`): un turno de la conversación, normalmente una hora simulada (`minutes_per_round`, que el generador puede ajustar entre 30 y 120); 20 rondas ≈ casi un día, 72 ≈ tres.
- **El razonamiento de la configuración** (paso 2) llega como texto del modelo: `lib/reasoningText.js` lo parte en título + párrafos de 2–3 frases + lista (para «(1)… (2)…»), siempre como DATOS (nunca HTML), sin lookbehind (Safari < 16.4) y a ~66 caracteres por línea.
- **El detalle técnico del informe** (iteraciones del modelo, llamadas a herramientas, parámetros JSON) solo se pinta con el conmutador global de «detalles técnicos» (`useTechDetails`, el «Ver registro» de la barra inferior), igual que el resto de lo técnico; ya no sale la cifra de «Herramientas». La barra inferior «Registro técnico» sigue visible: si se quiere, esconderla y activarla con un parámetro de la URL.

### Al tocar las pantallas del proceso

- **Una etapa ya hecha es de solo lectura**: abrirla no puede crear, preparar, lanzar, detener ni regenerar nada. Ojo con lo que dispara el montaje: el paso 2 prepara si la simulación no lo está, y el paso 3 **la lanza** si nunca se ejecutó (`runner_status: idle`). El indicador de etapas solo abre lo que ya ha ocurrido.
- En automático la pantalla observa: no lanza el grafo, la preparación, la simulación ni el informe (lo hace el servidor).
- **Texto largo sin espacios** (nombres que genera el modelo, URL, hashes): `overflow-wrap: anywhere` (no `break-word`, que no reduce el ancho mínimo en flex/grid) en todo título, nombre y párrafo que salga de la API; una tarjeta de rejilla o de flex lleva además `min-width: 0`. Medido el 1-oct-2026 alargando las respuestas de la API en el navegador (nombre de 96 letras pegadas y frases de 360 caracteres): fallaban el historial de la portada (+130 px de scroll horizontal) y los títulos de los pasos 4 y 5; a 390–1440 px ya no queda nada, a **320 px** quedan cabecera de estado, chips de archivos y etiquetas del paso 1–3 (pendiente). El script del barrido vive en la sesión (`_largo.js`): rehacerlo con la misma idea si se toca una pantalla con texto generado.
- Las pruebas sin interfaz de estas pantallas deben **abortar toda petición que no sea GET** (salvo lo que se compruebe a propósito): abrir una etapa a medias gasta LLM de verdad.

### Al tocar la portada

- Comprobar a **320, 360, 390, 768, 1000, 1366×768, 1440×900 y 1920** px, en es/en/zh y con «reducir movimiento»: sin scroll horizontal, el marcador cuelga pegado bajo la tarjeta (nunca la pisa, y los portátiles de 720–800 px de alto son el caso que falla) y ningún bocadillo corta texto.
- **La portada es pública** (`/` con `requiresAuth: false`): sin sesión no llama a la API (ni historial ni entrevista/revisión del brief) y el inicio de sesión se pide al pulsar «Iniciar simulación», con el material guardado en memoria (`store/pendingUpload.js`) y `?redirect=` de vuelta (solo rutas internas, `lib/authRedirect.js`). Cualquier pantalla nueva que llame a la API desde la portada debe comprobar la sesión antes.
- Las pruebas sin interfaz funcionan con una sesión de PocketBase **falsa solo en el navegador** (`localStorage.pocketbase_auth`) y **cortando las peticiones a PocketBase** (si llegan, rechaza el token falso y borra la sesión); en producción, además, `API_AUTH_TOKEN` temporal y borrarlo al acabar.
- Backend local: `NEO4J_URI=bolt://localhost:7687` (el valor por defecto `neo4j:7687` es el nombre de Docker Compose y da 500 en `/api/graph/data`).
- Los gráficos van animados (petición expresa) y nada de interfaz debe superar 700 ms.
- Los campos, chips y botones de contorno usan `--kb-control-line` (#858585, ≥ 3:1 sobre blanco y crema, WCAG 1.4.11); `--kb-line` y `--kb-line-strong` son para divisores, no para controles.
- Lo que hay tras pulsar «Iniciar simulación» también cuenta: `MainView.vue` muestra un aviso claro con «Reintentar» y «Volver al inicio» si falla el análisis o la construcción del mapa (antes quedaba un «generando…» eterno), y las cinco pantallas del proceso abren en «Mesa de trabajo» y reparten el encabezado en filas por debajo de 900 px.
- La nota de duración del formulario («alrededor de una hora y media», cifra «1–2 horas») sale de **una** ejecución completa medida en producción el 1-oct-2026, en automático, con 47 personas y 40 rondas: **83,5 min** (investigación 1 · ontología 3 · grafo 18 · preparación 10 · simulación 31 · informe 20). Antes decía «20–30 min», que salía de ejecuciones de 10 rondas sin investigación y dejó de ser cierto con el modo automático. Las rondas pesan un tercio: bajar de 40 a 12 ahorra ~20 min, así que no se ofrece «Rápida». Con más personas tarda más: si cambia el motor o el tamaño típico, volver a medir y repetir al menos una vez más. Las cifras «20–120 personas» salen de ejecuciones medidas (19, 23 y 113 personas).
- «Brief inicial» es el nombre del material que sube la persona (antes «semilla de la realidad», jerga heredada del motor); en inglés «initial brief». El chino conserva «现实种子» a la espera de una revisión de un hablante nativo.

## 🔗 Useful Resources

- [Simuloo en GitHub](https://github.com/koolbrand/MiroFish)
- [Aliyun Qwen API](https://bailian.console.aliyun.com/)
- [Zep Memory](https://app.getzep.com/)
- [Coolify Documentation](https://coolify.io/)

## 📌 Current Status

✅ En producción: https://simuloo.koolgrowth.com (Coolify, app `cim0v35ajeisb61vhm4bnn4o`)
✅ Flujo completo validado de extremo a extremo (brief → grafo → simulación → informe → chat)
✅ Portada con identidad Koolbrand (muro de Biankas) y memoria del recomendador acotada
⚠️ **Rondas**: el servidor nunca arranca más de `Config.SIMULATION_MAX_ROUNDS` (100; `/api/simulation/start` rechaza más y, sin `max_rounds`, aplica ese tope). El deslizador del paso a paso llega a 72 (`frontend/src/lib/rounds.js`, una sola fuente para portada y paso 2). El tope recorta, no alarga: si la configuración automática planifica menos rondas que el tope, se corre lo que planificó (por eso la portada dice «hasta N rondas»). ~35 s por ronda con 47 personas, solo la simulación.
⏳ Pendiente de decisión (Adrián): una simulación larga (72 rondas) en producción y relanzar la de un cliente que murió por memoria

---

**Last Updated**: 2026-09-30
**Maintained by**: Adrian (adrian@koolbrand.com)

## 🌍 Público con datos reales POR PAÍS — `backend/app/services/poblacion/`

> **Uso interno de I+D** hasta tener la **autorización escrita** de cada titular de los datos. Estrategia, evidencia, licencias verificadas y plan por fases: [`docs/estrategia-poblacion-por-pais.md`](docs/estrategia-poblacion-por-pais.md). Cita obligada: «Fuente de datos: <fuente> (estudio NNNN)» (sale en perfiles, reparto, informe en pantalla y PDF).

**Por qué:** un modelo, por defecto, se parece al público de EE. UU. y de los países occidentales, y acertar el **país** es lo que más rinde (un ama de casa de EE. UU. no es una de España). Las personas del **público** (entidades marcadas por `entity_role_filter` con `__simuloo_individual`) dejan de ser inventadas y se anclan a un **encuestado real y anónimo de la encuesta oficial de SU país**. Empresas, medios y competidores siguen como siempre.

**Cómo reparte (la idea central):** el grafo da GRUPOS (la entidad base + sus variantes, `__simuloo_group`); la encuesta pone las PERSONAS. Cada grupo pide a su segmento tantos encuestados como personas tenga, **los segmentos más estrechos eligen primero y nadie se repite**. La variedad dentro de un grupo la pone la encuesta, no la temperatura del modelo.

**Antiestereotipo (reglas duras):** (1) un filtro demográfico solo se pone si el texto lo **dice** («jubilados», «madres»); nunca se deduce de una afición o un producto. (2) El prompt de persona prohíbe inferir rasgos, aficiones, ingresos o política del sexo, edad, región o trabajo, y manda quedarse neutral donde la ficha calla. (3) Con encuestado real no se le pide al modelo que invente edad, familia ni que sea «distinta de las demás». (4) Edad, género y país son del dato real; no se inventa MBTI.

**Qué país:** lo elige la persona en la interfaz o, en «Automático», lo decide el modelo leyendo el brief **solo entre países que tienen banco**; si duda, no ancla. Sin país claro o sin banco de ese país, las personas se generan como siempre y la interfaz lo dice (`poblacion.json` → `sin_datos` + `motivo`).

| Pieza | Dónde |
|---|---|
| Registro de fuentes: una encuesta oficial por país (`Fuente`: país, nombre, regiones, licencia) | `services/poblacion/fuentes.py` |
| Banco SQLite genérico (segmento con relajación, muestreo ponderado sin repetir, `region`/`subregion`) | `services/poblacion/banco.py` |
| Vocabulario cerrado COMÚN (sexo, tramo, tamaño de municipio, estudios, situación laboral, estado civil) | `services/poblacion/vocabulario.py` |
| Detección del país | `services/poblacion/pais.py` |
| Descripción del grupo → filtros (el LLM propone, se valida contra la fuente; si falla, «sin filtros») | `services/poblacion/filtros.py` |
| «Ficha de datos reales» y hechos de memoria | `services/poblacion/ficha.py` |
| Calidad de la muestra (Jensen–Shannon, ruido esperable, dispersión de edad, línea base sin modelo) | `services/poblacion/metricas.py` |
| Fachada: `modo_activo()`, `asignar_por_grupos()`, `cita_de_simulacion()` | `services/poblacion/__init__.py` |
| Integración (agrupa por `__simuloo_group`, detecta país, prompt `_build_encuesta_persona_prompt`) | `services/oasis_profile_generator.py` |
| Constructores OFFLINE del banco (uno por fuente) | `backend/scripts/poblacion/build_banco_*.py` |
| Medición de fidelidad (a solo demografía · b con respuestas · moda del grupo · azar) | `backend/scripts/poblacion/fidelidad.py` |
| API | `GET /api/simulation/poblacion/estado` (una fuente por país) · `GET /api/simulation/<id>/poblacion` · `poblacion_datos` y `poblacion_pais` en `POST /prepare` |
| UI | interruptor + selector de país + reparto + «uso interno» en `Step2EnvSetup.vue`, cita en `Step4Report.vue`; textos `step2.datos*` en es/en/zh |

**Variables:** `POBLACION_DATOS_REALES` (`true/false`, por defecto `false`; el antiguo `POBLACION_CIS` sigue valiendo) · `POBLACION_BANCOS_DIR` (por defecto `backend/data/poblacion/`) · `POBLACION_BANCO_PATH` (solo el CIS; por defecto `<bancos>/banco_cis.sqlite`). **Sin banco o con el modo apagado el comportamiento es idéntico al de siempre** (el interruptor ni aparece sin banco).

**Añadir un país:** (1) registrar su `Fuente` en `fuentes.py` (nace `solo_investigacion`); (2) escribir su `scripts/poblacion/build_banco_<fuente>.py` que normalice a los vocabularios comunes y guarde `meta(fuente, pais)`; (3) tests con banco sintético (`tests/poblacion_fixture.py::registrar_pais_sintetico`); (4) medir fidelidad antes de fiarse; (5) pedir la autorización escrita antes de llevarlo a un entregable de cliente.

**Reglas de datos:** los microdatos **nunca** van al repo (es público) ni a la imagen Docker (`.gitignore`/`.dockerignore` cubren `backend/data/`, `*.sqlite`, `MD35*.zip`). Los tests usan bancos **sintéticos inventados**. No cruzar con datos personales ni reidentificar. No usar SDV (licencia BSL). Varias fuentes prohíben ceder los ficheros a terceros o investigar a individuos concretos: antes de enviar un registro individual a un modelo externo, la autorización escrita tiene que cubrir ese uso.

**Con datos reales (2-oct-2026):** banco de 20.128 encuestados y 156 preguntas de 5 estudios del CIS. Lo que hay que saber: (1) el modelo con las respuestas reales mejora al modelo con solo demografía (+6 puntos) pero **no supera a la respuesta más común del grupo sexo × edad** — por eso Simuloo es un ensayo, no una predicción; (2) la ficha pone primero lo que tiene que ver con el tema del brief y deja las políticas, los nombres propios y los elementos de batería sin enunciado al final (máx. 4); (3) los paradatos del trabajo de campo no entran en el banco. Detalle y cifras en `docs/estrategia-poblacion-por-pais.md` §7.

**Prueba completa en producción (2-oct-2026, Kool Café) — lo que hay que saber:** con datos reales las personas son menos tópicas y más variadas (jueces a ciegas, 6 de 6), pero informe y conjunto los prefirieron con personas inventadas (más color local); el color inventado no es realismo. Límite abierto: el banco es nacional y el brief puede ser local (salió una teletrabajadora de Extremadura para un café de Vigo): falta aplicar la región del brief a todos los grupos. La ficha lleva primero las 15 preguntas que un modelo elige como relevantes para el tema (una llamada por simulación, solo puede elegir de la lista); las instituciones no se anclan; `_llm_texto` repite con más espacio porque el modelo de razonamiento devuelve vacío. Cifras y límites en `docs/estrategia-poblacion-por-pais.md`.

**Alcance geográfico (3-oct-2026) — `services/poblacion/alcance.py`:** cada simulación decide **dónde vive el público** (`local · regional · nacional · multinacional · mundial`, o `desconocido`) y de eso cuelga todo: **local/regional** → a TODOS los grupos se les aplica la región (y la provincia en local) que el propio banco conoce, y solo se relaja el último (mínimo 10 casos); **nacional** → sin filtrar por lugar (que alguien de Extremadura opine de algo del País Vasco es válido si el problema es nacional); **multinacional/mundial** → NO se ancla a la encuesta de un país (sesgaría) y cada persona recibe una cultura distinta (`CULTURAS`, repartidas por orden entre las personas del público); el **informe** y el chat reciben cautelas según el nivel (`texto_para_informe`). Lo decide **Jev** (una petición, ~0,5 s: nivel + una pregunta de sí/no por región + provincia) y, si Jev duda (confianza < 0,6), cae o es multinacional, **el modelo grande** (que sí extrae el nombre del sitio y los países). Reglas que costaron un fallo: Jev **nunca** da el nombre del sitio (`lugar` queda vacío; la zona se dice con región/provincia); en nacional `lugar` NO sale del número de bancos (el país lo confirma la detección del país); una provincia clara manda sobre un «sí» suelto a otra región; las instituciones no se anclan; los visitantes o turistas de fuera se marcan `fuera_del_lugar` y no se fuerzan al lugar; un país elegido a mano gana a un alcance deducido como mundial. La persona lo fija en el selector del paso 2 (`alcance` en `POST /prepare`, `GET /api/simulation/<id>/alcance`; se guarda en `alcance.json`); mientras se prepara, los ajustes están bloqueados. Medido con 50 briefs etiquetados (`scripts/poblacion/evaluar_alcance.py`): modelo grande solo 48–49/50 exactos y 50/50 aceptables; con Jev primero, 37/50 los decide Jev con el 100 % bien y el resto pasa al modelo grande. Revisión adversarial con escépticos (38 hallazgos, 29 confirmados, corregidos). Límites: Jev no extrae países ni ciudades; el reparto de culturas es parejo (sin pesos por población); con pocas personas por cultura las diferencias son orientativas.

**Jev para decisiones cerradas (`services/poblacion/jev.py`):** `preguntar(state, {id: choice|noul})`, todas las preguntas en paralelo en una petición; devuelve `None` sin clave, con fallo del servicio (y no vuelve a llamar durante 90 s) o con un 4xx (no se reintenta) y quien llama sigue con el modelo grande. Se usa para el alcance, el país y las preguntas de la encuesta relevantes para el tema.

**Temas políticos (3-oct-2026) — `poblacion.tema_politico()`:** si el tema de la simulación es político (unas elecciones, partidos, gobierno; Jev decide en ~0,5 s y, si duda o no está, un respaldo por palabras que exige dos), la ficha deja de relegar la política: el catálogo de preguntas relevantes **incluye** las políticas (sin nombres de líderes ni elementos de batería sin enunciado), el voto y la ideología van **los primeros** de la ficha (intención de voto → voto+simpatía → recuerdo de voto → autoubicación → partido cercano → probabilidad → fidelidad → momento de decisión) y el prompt de persona añade «POLITICAL TOPIC» (el voto declarado, la indecisión o la abstención se reflejan tal cual; sin caricatura). Con cualquier otro tema todo sigue igual (la política al final, máx. 4, y «una persona no es su voto»). **Por qué:** sin el voto real de cada persona una simulación electoral no mide nada. **Ojo:** las respuestas políticas de un encuestado anónimo también van a un modelo externo; sigue siendo uso interno de I+D hasta tener la autorización escrita del CIS. `resumen["tema_politico"]` lo deja anotado en `poblacion.json`.

**Tamaño del público por simulación (4-oct-2026):** el paso 2 permite Automático o un tamaño explícito de 5–150 personas del público, aparte de actores e instituciones. `POST /prepare` recibe `audience_size`: entero JSON estricto en ese rango, `null` para automático; si se omite conserva la elección anterior. Un valor inválido da 400 antes del trabajo. Se guarda en `state.json` antes del worker y lo devuelve `GET /simulation/<id>`. El tamaño explícito solo expande colectivos confirmados: no convierte actores en encuestados para alcanzar la cifra. Si no se consigue el tamaño solicitado, o con datos reales solicitados falta banco o encuestados suficientes, falla de forma visible. Automático conserva los topes `JEV_MIN_AUDIENCE_RATIO` y `AUDIENCE_MAX_*`. La selección ponderada representa un muestreo del banco disponible: **no acredita representatividad nacional, intención de voto actual ni capacidad de predecir elecciones**. Los contadores `audience_count`/`audience_survey_count` distinguen público confirmado de público anclado a encuesta; el rol «audiencia» puede incluir actores y es otra métrica.

**Construir el banco del CIS** (ZIP en cis.es; el formulario solo exige el correo; en 2-oct-2026 están en `~/dev-worktrees/cis-zips/`, fuera del repo):

```bash
cd backend && uv run --with pyreadstat --with pandas python scripts/poblacion/build_banco_cis.py ~/Downloads/MD35*.zip --reemplazar
```

⚠️ Los nombres de variable cambian entre estudios: `build_banco_cis.py` prueba candidatos (`CANDIDATAS`) y se fijan a mano por estudio en `MAPEOS_ESTUDIO` tras mirar el codebook. Los normalizadores (CCAA, tamaño, estudios…) se probaron con etiquetas **supuestas** del CIS, no con los ficheros reales: revisar el primer volcado.

**Producción:** los microdatos **no van por GitHub ni por la imagen**. El volumen persistente `mirofish-uploads` (`/app/backend/uploads`) guarda el banco en `/app/backend/uploads/poblacion/` (variable `POBLACION_BANCOS_DIR`). Lo construye `backend/scripts/poblacion/instalar_banco_cis.sh`, que descarga del propio CIS los 5 estudios, **comprueba su huella** y lanza el constructor; es idempotente (si el banco existe, no hace nada) y tarda ~8 min. Se ejecuta como «comando posterior al despliegue» de la app en Coolify (en segundo plano):

```
setsid nohup sh /app/backend/scripts/poblacion/instalar_banco_cis.sh >/app/backend/logs/instalar_banco.log 2>&1 &
```

Si el CIS publica una versión nueva de un fichero, la huella no coincide y el script se para: hay que actualizar la URL y la huella en el script. El interruptor de la interfaz sigue apagado por defecto (`POBLACION_DATOS_REALES` sin definir).

## 🔒 Entradas de usuario: qué está acotado y dónde (3-oct-2026)

Todo texto libre que llega al modelo o al disco pasa por un tope y, si es un fichero, por una comprobación de contenido. Las utilidades están en `backend/app/utils/security.py` (`sanitize_user_text`, `validate_upload_content`, `clamp_limit`); los topes, en `Config`. Cualquier endpoint nuevo que acepte texto libre o ficheros **tiene que usarlas** (hay un test por endpoint en `tests/test_entradas_acotadas.py` y `tests/test_cost_limits.py`).

| Entrada | Dónde | Tope / comprobación |
|---|---|---|
| Brief inicial: `simulation_requirement`, `project_name`, `additional_context` | `graph.py` (subida de ontología) | `sanitize_user_text` (10.000, sin caracteres de control) |
| Ficheros subidos (PDF, Word, md/txt, imágenes) | `graph.py` y `brief.py` (`/api/brief/check`) | `validate_upload_content`: firma real (`%PDF-`, `PK\x03\x04`, PNG/JPG/GIF/WebP) y sin bytes nulos en texto, no solo la extensión |
| Nombre de proyecto / de grafo | `graph.py` | 120 / 200 caracteres y sin caracteres de control |
| Mensaje y historial del chat del informe | `report.py` | `MAX_CHAT_MESSAGE_CHARS` (4.000) y `sanitize_chat_history` |
| `prompt` de entrevista (individual, **a todos**, lote) | `simulation.py` | `MAX_INTERVIEW_PROMPT_CHARS` (2.000); el de «a todos» se repite por cada agente |
| Consulta de búsqueda del informe | `report.py` (`/tools/search`) | `MAX_SEARCH_QUERY_CHARS` (1.000) y `limit` ≤ 50 |
| `limit` de los listados | `graph.py`, `report.py` | `clamp_limit` (≤ 200) |
| Tamaño del público | `/prepare` | `audience_size` 5–150 |

La rama `security/hardening-batch` (mayo de 2026) ya no se puede fusionar: su contenido está en `main` por otra vía.
