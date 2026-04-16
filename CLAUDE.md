# 📋 MiroFish Project Documentation

## 🎯 Project Overview

**MiroFish** es un motor de predicción de IA de siguiente generación impulsado por tecnología multi-agente. Extrae información semilla del mundo real y construye un mundo digital paralelo donde miles de agentes inteligentes interactúan.

- **GitHub**: https://github.com/koolbrand/MiroFish
- **Status**: En desarrollo
- **Node Version**: ≥18.0.0
- **Python Version**: ≥3.9

## 📁 Project Structure

```
mirofish/
├── frontend/              # React/Node.js frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── backend/               # Python backend
│   ├── run.py
│   ├── pyproject.toml
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

### Environment Variables

Required for development/production:

```
LLM_API_KEY=<your_llm_api_key>
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=<your_zep_memory_key>
```

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

## 🔗 Useful Resources

- [MiroFish GitHub](https://github.com/koolbrand/MiroFish)
- [Aliyun Qwen API](https://bailian.console.aliyun.com/)
- [Zep Memory](https://app.getzep.com/)
- [Coolify Documentation](https://coolify.io/)

## 📌 Current Status

✅ Project cloned locally
✅ .env configured
✅ Docker optimized for production
✅ Coolify deployment guide created
⏳ Ready for deployment

---

**Last Updated**: 2026-04-16
**Maintained by**: Adrian (adrian@koolbrand.com)
