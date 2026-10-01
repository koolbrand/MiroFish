# 🚀 Deployment Guide: Simuloo en Coolify

## Requisitos Previos

- Acceso a Coolify: `coolify.koolgrowth.com`
- Usuario: `adrian@koolbrand.com`
- LLM API Keys configuradas
- Zep Memory API Key

## 1️⃣ Preparar Variables de Entorno

Asegúrate de tener un archivo `.env` en la raíz del proyecto:

```bash
# .env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key_here
DEBUG=false
```

## 2️⃣ Pasos para Desplegar en Coolify

### A. Crear Aplicación en Coolify

1. Accede a `coolify.koolgrowth.com`
2. Inicia sesión con: `adrian@koolbrand.com`
3. En Dashboard, clickea **"New Project"** o **"New Application"**
4. Selecciona **"Docker Compose"** como tipo de deployment

### B. Configurar la Aplicación

| Campo | Valor |
|-------|-------|
| **Name** | `Simuloo` |
| **Repository** | `https://github.com/koolbrand/MiroFish` |
| **Branch** | `main` |
| **Docker Compose File** | `docker-compose.yml` |

### C. Configurar Variables de Entorno

En Coolify, agrega estas variables:

```
LLM_API_KEY=<tu_api_key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=<tu_zep_key>
DEBUG=false
```

### D. Configurar Puertos

- **Internal Port**: `8000`
- **External Port**: `80` o `443` (según tu setup)
- **Protocol**: `HTTP`

### E. Volumes (Almacenamiento)

Configura estos volúmenes persistentes:

- `/app/backend/uploads` → `/data/mirofish/uploads`
- `/app/backend/logs` → `/data/mirofish/logs`

### F. Health Check

Coolify debería detectar automáticamente:
- **Endpoint**: `/health`
- **Interval**: `30s`
- **Timeout**: `10s`
- **Retries**: `3`

## 3️⃣ Desplegar

1. Clickea **"Deploy"**
2. Espera a que se complete la construcción de la imagen Docker
3. Verifica en **"Logs"** que la aplicación inició correctamente

## 4️⃣ Verificar Deployment

Una vez desplegado:

```bash
# Verificar salud de la aplicación
curl https://tu-dominio.com/health

# Ver logs en tiempo real
# Accede a Coolify Dashboard → Logs
```

## 🔧 Troubleshooting

### Problema: Build falla
- Verifica que todas las variables de entorno están configuradas
- Revisa los logs en Coolify Dashboard
- Asegúrate de que `.env` NO está en el repositorio

### Problema: Aplicación no responde
- Verifica los health checks en Coolify
- Comprueba los logs de la aplicación
- Asegúrate de que los puertos están correctamente mapeados

### Problema: APIs no funcionan
- Verifica que `LLM_API_KEY` y `ZEP_API_KEY` son válidas
- Comprueba conectividad a APIs externas

## 📊 Monitoreo

En Coolify Dashboard puedes:
- Ver logs en tiempo real
- Monitorear uso de recursos (CPU, RAM)
- Ver historial de deployments
- Configurar alertas

### Dos endpoints de salud, con papeles distintos

| Endpoint | Qué dice | Para qué |
|---|---|---|
| `/health` | Flask responde | La sonda del **contenedor** (Docker/Coolify). Si falla, se reinicia. |
| `/health/ready` | Flask responde **y** Neo4j contesta **y** el disco de datos se puede escribir y tiene sitio (`MIN_FREE_DISK_MB`, 200 por defecto) | Un **monitor externo** (UptimeRobot, Better Stack...). Devuelve `503` con `{"checks": {"neo4j": false, ...}}` sin direcciones ni errores. Se guarda 10 s. |

No se han unido a propósito: si Coolify reiniciara el contenedor cada vez que Neo4j tarda en arrancar, el remedio
sería peor que el fallo. Y el servicio de la app tampoco espera a que Neo4j esté «healthy» para arrancar
(`depends_on` simple): con Neo4j caído, un redespliegue dejaría sin servicio también el inicio de sesión y los
informes ya hechos, que no lo necesitan.

## 💾 Copias de seguridad

Antes no había ninguna: un volumen borrado se llevaba todos los proyectos, simulaciones e informes. Qué hay que
guardar, de más a menos valioso:

| Dato | Volumen | Cómo se copia | Si se pierde |
|---|---|---|---|
| Proyectos, simulaciones, informes | `mirofish_uploads` | En caliente (los archivos se escriben de forma atómica) | **Irrecuperable** |
| Grafo de conocimiento | `neo4j_data_v2` | Parando Neo4j unos segundos (Community no tiene copia en caliente) | Se reconstruye desde el material (≈ 18 min de modelo y su coste) |
| Registros | `mirofish_logs` | No hace falta | Solo diagnóstico |
| Modelo del recomendador | `mirofish_hf_cache` | No hace falta | Se vuelve a descargar (1,1 GB) |

### Hacer la copia (en el servidor donde corre Docker)

```bash
# En Coolify los volúmenes llevan de prefijo el uuid de la app: «<uuid>_mirofish_uploads»
docker volume ls | grep -E 'uploads|neo4j'

ops/backup.sh --prefix <uuid>_ --dest /srv/copias-simuloo --keep 14            # solo los ficheros
ops/backup.sh --prefix <uuid>_ --dest /srv/copias-simuloo --keep 14 --grafo    # y el grafo (Neo4j para unos segundos)
```

El script comprueba que cada copia se puede leer, la escribe con nombre temporal (una copia a medias nunca parece
completa), conserva las `--keep` más recientes y arranca Neo4j de nuevo pase lo que pase. **Programarlo es cosa
del servidor** (cron: `0 4 * * * /ruta/ops/backup.sh ...`): una copia que nadie ejecuta no existe. Y una copia que
vive en el mismo disco que los datos no protege del disco: súbela también a otro sitio (`rclone`, `rsync`, S3...).

### Restaurar

```bash
# Ficheros: en un volumen vacío (o con la app parada, encima del existente)
docker run --rm -v <uuid>_mirofish_uploads:/data -v /srv/copias-simuloo:/backup:ro alpine:3.20 \
  sh -c 'tar xzf /backup/simuloo-ficheros-AAAAMMDD-HHMMSS.tar.gz -C /data'

# Grafo: con Neo4j PARADO. El volcado tiene que llamarse neo4j.dump y estar solo en su carpeta
docker stop <contenedor-neo4j>
mkdir -p /tmp/restaurar && cp /srv/copias-simuloo/simuloo-grafo-AAAAMMDD-HHMMSS.dump /tmp/restaurar/neo4j.dump
docker run --rm --entrypoint neo4j-admin -v <uuid>_neo4j_data_v2:/data -v /tmp/restaurar:/backups neo4j:5.26.2 \
  database load neo4j --from-path=/backups --overwrite-destination=true
docker start <contenedor-neo4j>
```

Las dos formas (copia y restauración, sobre volúmenes nuevos, con un nodo centinela en el grafo) se probaron de punta
a punta el 1-oct-2026. **Lo que no se ha probado** es el nombre exacto de los volúmenes en el servidor de Coolify
(el script falla con un mensaje claro y lista los que hay si no lo encuentra).

## 🔐 Seguridad

- **NO commits .env** a Git (ya está en .gitignore)
- Usa variables de entorno en Coolify para secretos
- Activa HTTPS en tu dominio
- Limita acceso a IPs conocidas si es posible

## 📝 Notas Adicionales

- El Dockerfile está optimizado para producción (multi-stage build, sin dependencias de desarrollo)
- Health checks automáticos cada 30s
- **Variables en Coolify:** Coolify reescribe el compose y añade `env_file: .env` a los dos servicios, así que
  cualquier variable que definas en su panel (`LEGACY_OWNER_ID`, `MAX_CONCURRENT_SIMULATIONS`,
  `WEB_RESEARCH_*`, `LLM_TIMEOUT_SECONDS`...) llega a la app aunque no esté listada en `docker-compose.yml`
  (comprobado con la API de Coolify el 1-oct-2026). Si ejecutas el compose **sin** Coolify (`docker compose up`),
  esas no llegan: añádelas en `environment:`. Una variable numérica **vacía** o con un typo (`30s`) ya no tumba el
  arranque: se avisa por stderr y se usa el valor por defecto.
- **Apagado:** `init: true` y `stop_grace_period: 60s` en la app. Al apagar, termina las simulaciones vivas y vuelca
  la memoria del grafo; con los 10 s por defecto Docker la mataba a medias. Lo que quede en «running» lo marca como
  fallido el arranque siguiente.
- Logs persistentes en `/app/backend/logs`
- Uploads guardados en `/app/backend/uploads`

---

**¿Preguntas o problemas?** Revisa los logs en el Dashboard de Coolify.
