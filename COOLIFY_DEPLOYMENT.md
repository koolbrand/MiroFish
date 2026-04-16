# 🚀 Deployment Guide: MiroFish en Coolify

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
| **Name** | `MiroFish` |
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

## 🔐 Seguridad

- **NO commits .env** a Git (ya está en .gitignore)
- Usa variables de entorno en Coolify para secretos
- Activa HTTPS en tu dominio
- Limita acceso a IPs conocidas si es posible

## 📝 Notas Adicionales

- El Dockerfile está optimizado para producción (multi-stage build)
- Health checks automáticos cada 30s
- Logs persistentes en `/app/backend/logs`
- Uploads guardados en `/app/backend/uploads`

---

**¿Preguntas o problemas?** Revisa los logs en el Dashboard de Coolify.
