# ===== Stage 1: Build Frontend =====
FROM node:22-alpine as frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ .

RUN npm run build

# ===== Stage 2: Build Backend Dependencies =====
FROM python:3.11-slim as backend-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

# 从 uv 官方镜像复制 uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./

RUN uv sync --frozen --no-editable

# ===== Stage 3: Production Runtime =====
FROM python:3.11-slim

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 从 builder 复制 Python 虚拟环境
COPY --from=backend-builder /app/backend/.venv /app/backend/.venv

# 从 frontend builder 复制编译后的前端
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 复制项目源码
COPY backend/ ./backend/
COPY frontend/package.json ./frontend/

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Ejecutar el servidor de producción
CMD ["python", "backend/run.py"]