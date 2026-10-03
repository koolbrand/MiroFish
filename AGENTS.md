# Simuloo — instrucciones de trabajo

**Lectura obligatoria antes de trabajar:** [guía operativa completa](docs/guia-operativa.md).
Todas las instrucciones de esa guía siguen vigentes. Se han trasladado sin recortar
para mantener este punto de entrada por debajo del límite de 250 líneas del pre-flight.

## Pre-flight

Ejecutar `bash init.sh` antes de cualquier sesión. Si falla, corregir el problema
antes de arrancar servicios. El `.env` local es opcional; las claves de producción
viven en Coolify. No imprimir, commitear ni modificar secretos al hacer reparaciones.

## Flujo obligatorio

`planner` → `backend-implementer` / `frontend-implementer` → `quality-gate` → commit.
El planner orquesta; los implementadores no commitean. Dejar plan y resultados en
`tmp/plan-*.md` y `tmp/result-*-implementer-*.md`. La revisión final debe aprobar.
Las instrucciones de cada rol están en `.claude/agents/`.

## Proyecto

Simuloo (fork de MiroFish), Vue 3 + Vite y Python/Flask. Memoria Graphiti + Neo4j;
OASIS para simulación social. Los nombres `mirofish`, volúmenes, ids y loggers
históricos no se renombran. Runtime en Coolify, aplicación `cim0v35ajeisb61vhm4bnn4o`:
https://simuloo.koolgrowth.com — repositorio https://github.com/koolbrand/MiroFish.

## Invariantes

- Aislamiento por usuario central en `utils/access.py`; filtrar listados antes del límite.
- Estado JSON con escritura atómica y lectura tolerante; no resucitar elementos borrados.
- Servidor de un solo proceso; respetar recuperación y límites de procesos OASIS vivos.
- Autenticar antes de leer cuerpos, validar entradas y mantener topes de coste por petición.
- No HTML de la API en `v-html`; storage del navegador dentro de `try/catch`.
- Pantallas ya ejecutadas de solo lectura; el automático lo dirige el servidor.
- Datos poblacionales: instituciones no se anclan; microdatos fuera de Git/Docker;
  tests con datos sintéticos y cautelas/citas de las fuentes visibles.
- Respetar identidad, accesibilidad e idiomas es/en/zh de la guía completa.

## Comprobaciones

`cd backend && uv run pytest -q`; `npm run build`; `uv lock --check` en backend;
`docker compose config --quiet`. Añadir pruebas de regresión significativas según
el cambio. Para PDF en macOS consultar las instrucciones de Pango en la guía.
Despliegue y copias: [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md).
