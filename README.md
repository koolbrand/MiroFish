<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="60%"/>

# MiroFish — Production Fork by KoolBrand

**Next-generation AI prediction engine powered by multi-agent swarm intelligence.**
*Predice opinión pública, reacciones de mercado y dinámicas sociales — antes de que ocurran.*

> 🇪🇸 **Interfaz en español** · **Dual-LLM** (reasoning for simulation, structured-output for graph) · Memoria de grafo **100 % autoalojada** (sin Zep Cloud)

[![GitHub Stars](https://img.shields.io/github/stars/koolbrand/MiroFish?style=flat-square&color=DAA520)](https://github.com/koolbrand/MiroFish/stargazers)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](LICENSE)
[![MiniMax](https://img.shields.io/badge/LLM-MiniMax%20M2.7-FF6B35?style=flat-square)](https://www.minimaxi.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![Coolify](https://img.shields.io/badge/Coolify-One--click-6B46C1?style=flat-square)](https://coolify.io/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Self--hosted-008CC1?style=flat-square&logo=neo4j&logoColor=white)](https://neo4j.com/)

[🇪🇸 Español](#quick-start) · [🇬🇧 English](#quick-start) · [Proyecto original ↗](https://github.com/666ghj/MiroFish)

</div>

---

## What is MiroFish?

MiroFish lets you upload real-world seed data — news articles, reports, documents — and simulate how thousands of AI agents with independent personalities, memories, and behaviors would react to it. The result: a detailed prediction report of social dynamics, public opinion, or market response **before events unfold**.

> Upload seed materials → describe your prediction in natural language → get a full simulation report with interactive agents

**Built for:** brand managers, researchers, policy analysts, journalists, and anyone who wants to stress-test decisions before making them.

---

## 🚀 What KoolBrand Added to this Fork

This fork takes the original MiroFish engine and makes it **production-ready**, **self-hosted**, and **enterprise-friendly**. Here's what changed:

### 🧬 Dual-LLM Architecture — reasoning for simulation, structured output for graph

The original project uses a single LLM for everything. In production this breaks: reasoning models like **MiniMax-M2.7** or **DeepSeek-R1** give great simulation reasoning but silently ignore `response_format: json_schema`, so ~50 % of graph extractions come back with invented field names and invalid JSON (we saw runs with 38 nodes / 2 edges that were effectively unusable).

This fork splits the LLM in two, each optimized for its job:

| Job | Why it needs what | Recommended model |
|---|---|---|
| **Simulation reasoning** (`LLM_*`) | Agents need chain-of-thought, nuance, persona fidelity | `MiniMax-M2.7`, `DeepSeek-R1`, `gpt-4o`, `qwen-plus` |
| **Graph extraction** (`GRAPHITI_LLM_*`) | Graphiti requires strict JSON schema compliance — one invalid field = lost entity | `seed-2-0-lite-260228` (BytePlus), `deepseek-chat` v3, `qwen-plus` |

Each `GRAPHITI_LLM_*` variable independently falls back to its `LLM_*` counterpart, so **single-provider setups still work out of the box** — you only need to override when you want the split. The adapter also auto-detects which `response_format` modes each model supports (`json_schema` → `json_object` → none) and retries gracefully.

**Real-world impact on our runs:** edge-to-node ratio jumped from **0.05 (broken) to ~1.2 (healthy)**, and the entity-type labels finally match the agent filter, so the simulation actually finds characters to instantiate.

### 🧠 Self-Hosted Graph Memory (Graphiti + Neo4j)

The original project requires **Zep Cloud** — an external paid service with strict free-tier limits (5 episodes/min, monthly caps). We replaced it entirely with **self-hosted [Graphiti](https://github.com/getzep/graphiti) + Neo4j**:

- ✅ No external API dependency for graph memory
- ✅ No usage limits — run as many simulations as you want
- ✅ Your data stays in your infrastructure
- ✅ Neo4j included as a Docker service — zero additional setup

This is the most impactful change for the community: **you can now run MiroFish fully self-hosted with no external services required** (beyond your LLM provider).

### 🔐 PocketBase Authentication

Added enterprise-ready authentication using [PocketBase](https://pocketbase.io/):
- Secure login before accessing the simulation engine
- Compatible with any PocketBase instance (self-hosted or cloud)
- Configurable via `VITE_POCKETBASE_URL` env variable

### 🌍 Spanish Language Support

Full Spanish translation (`es`) across all 17 UI sections. The app now supports **Spanish, English, and Chinese** — making it accessible to the entire Spanish-speaking market (500M+ speakers).

### 🐳 Docker Compose — Deploy in One Click

Complete multi-service `docker-compose.yml` with:
- MiroFish app container
- Neo4j graph database container with APOC plugin
- Health checks and automatic restart policies
- Compatible with [Coolify](https://coolify.io/) for zero-ops self-hosting

### ⏹ Stop Simulation

Added a **Stop** button to the simulation run view — you can now interrupt a simulation mid-run and still access the partial results and report.

### 🏷 Version Badge

Every page now shows the app version and build date — useful for tracking deployments in production.

### 🔧 Production API Fix

Fixed a critical bug where the frontend called `localhost:5001` in production (hardcoded URL), causing all API calls to fail when deployed. Now uses relative URLs that work on any host.

---

## 🏗 Architecture

```
Browser → Vue 3 + vue-i18n (es/en/zh)
         ↓ PocketBase auth guard
Flask API (Python 3.11)
         ↓
   ┌──────────────┐    ┌──────────────────┐
   │  LLM Client  │    │  Graphiti Core   │
   │  (any OpenAI │    │  (graph memory)  │
   │  compatible) │    │        ↕         │
   └──────────────┘    │     Neo4j        │
                        └──────────────────┘
         ↓
   OASIS Simulation Engine (CAMEL-AI)
         ↓
   Report Agent → Prediction Report
```

---

## ⚡ Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | Latest |
| LLM API key | Any OpenAI-compatible provider |

### 1. Clone & Configure

```bash
git clone https://github.com/koolbrand/MiroFish.git
cd MiroFish
cp .env.example .env
```

Edit `.env`:

```env
# ===== Simulation LLM — reasoning model for agents =====
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.minimaxi.chat/v1       # or OpenAI, Qwen, DeepSeek…
LLM_MODEL_NAME=MiniMax-M2.7

# ===== Graph-extraction LLM — needs json_schema support =====
# Optional: if unset, falls back to the LLM_* vars above.
# Recommended: BytePlus Seed-2-0-lite (cheap, reliable structured output) or DeepSeek-V3.
GRAPHITI_LLM_API_KEY=your_byteplus_key
GRAPHITI_LLM_BASE_URL=https://ap-southeast.bytepluses.com/api/v3
GRAPHITI_LLM_MODEL_NAME=seed-2-0-lite-260228

# ===== Embeddings (used by Graphiti for graph search) =====
# Falls back to LLM_* if unset.
EMBEDDING_MODEL=text-embedding-3-small
# EMBEDDING_API_KEY=...
# EMBEDDING_BASE_URL=...

# ===== Neo4j — auto-started by docker-compose =====
NEO4J_PASSWORD=change_me_please

# ===== PocketBase (optional — for authentication) =====
# VITE_POCKETBASE_URL=https://your-pocketbase.example.com
```

### 2. Start Everything

```bash
docker compose up -d
```

This starts **two containers**: MiroFish app (port 8000) and Neo4j. Wait ~40s for Neo4j to initialize, then open:

```
http://localhost:8000
```

### 3. Run a Simulation

1. **Upload** a document (PDF, MD, or TXT) — a news article, report, anything real
2. **Describe** what you want to predict in natural language
3. **Review** the auto-generated entity ontology
4. **Build** the knowledge graph (powered by Graphiti + Neo4j)
5. **Run** the multi-agent simulation
6. **Read** the prediction report — and interact with any agent

---

## 🛠 Development Setup

```bash
# Install all dependencies
npm run setup:all

# Start backend (port 8000) and frontend (port 3000) in dev mode
npm run dev
```

Backend requires Python 3.11 and [`uv`](https://docs.astral.sh/uv/) package manager.

---

## 🌐 Deploy to Coolify (Recommended)

[Coolify](https://coolify.io/) is an open-source self-hosted platform that makes deployment effortless. MiroFish + Neo4j deploy together in one step:

1. Add a new **Docker Compose** resource in Coolify
2. Point to `https://github.com/koolbrand/MiroFish`
3. Set the environment variables (see table below)
4. Deploy — Coolify handles everything

Full guide: [COOLIFY_DEPLOYMENT.md](./COOLIFY_DEPLOYMENT.md)

---

## 🔧 Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_API_KEY` | ✅ | — | API key — **simulation** LLM (reasoning model) |
| `LLM_BASE_URL` | ✅ | — | Base URL — simulation LLM (OpenAI-compatible) |
| `LLM_MODEL_NAME` | ✅ | — | Simulation model name (e.g. `MiniMax-M2.7`, `gpt-4o`) |
| `GRAPHITI_LLM_API_KEY` | ❌ | falls back to `LLM_API_KEY` | API key — **graph-extraction** LLM |
| `GRAPHITI_LLM_BASE_URL` | ❌ | falls back to `LLM_BASE_URL` | Base URL — graph-extraction LLM |
| `GRAPHITI_LLM_MODEL_NAME` | ❌ | falls back to `LLM_MODEL_NAME` | Graph-extraction model (must support `json_schema` — `seed-2-0-lite-260228`, `deepseek-chat`…) |
| `EMBEDDING_MODEL` | ❌ | `text-embedding-3-small` | Embedding model for Graphiti graph search |
| `EMBEDDING_API_KEY` | ❌ | falls back to `LLM_API_KEY` | API key for embeddings (if different provider) |
| `EMBEDDING_BASE_URL` | ❌ | falls back to `LLM_BASE_URL` | Base URL for embeddings |
| `NEO4J_PASSWORD` | ✅ | `mirofish2026` | Neo4j password — **change in production!** |
| `NEO4J_URI` | ❌ | `bolt://neo4j:7687` | Neo4j Bolt URI |
| `VITE_POCKETBASE_URL` | ❌ | — | PocketBase instance URL for authentication |
| `DEBUG` | ❌ | `false` | Enable Flask debug mode |

---

## 📋 What's New vs Original

| Feature | Original | This Fork |
|---|---|---|
| LLM architecture | Single LLM | Dual-LLM — reasoning + structured-output split ✅ |
| Graph extraction quality | ~50 % invalid JSON with reasoning models | Auto model-aware `response_format` chain ✅ |
| Graph memory | Zep Cloud (external, limited) | Self-hosted Graphiti + Neo4j ✅ |
| Authentication | None | PocketBase ✅ |
| Languages | Chinese + English | + Spanish (es, default) ✅ |
| Docker Compose | Single container | Multi-service (app + Neo4j) ✅ |
| Coolify deploy | Manual | One-click ✅ |
| Stop simulation | ❌ | ✅ |
| Production API URLs | Hardcoded localhost | Relative (works anywhere) ✅ |
| Version tracking | ❌ | Build date badge ✅ |

---

## 🤝 Community & Contributing

This fork is maintained by **[KoolBrand](https://koolbrand.com)** — a studio building AI-powered brand intelligence tools for the Spanish-speaking market and beyond.

We believe MiroFish is genuinely useful for:
- **Brands** stress-testing campaigns and messaging before launch
- **Researchers** studying how information spreads in social networks
- **Journalists & analysts** modeling public reaction to events
- **Writers & creators** exploring narrative possibilities

If you use this fork, we'd love to hear what you're building. Open an issue, start a discussion, or reach out at **hola@koolbrand.com**.

**PRs welcome.** If you add a feature, document it — that's the deal.

---

## 📄 Credits & Acknowledgments

- Original **MiroFish** engine by [666ghj](https://github.com/666ghj/MiroFish) — incubated by [Shanda Group](https://www.shanda.com/)
- Simulation core powered by **[OASIS](https://github.com/camel-ai/oasis)** by the CAMEL-AI team
- Graph memory powered by **[Graphiti](https://github.com/getzep/graphiti)** by the Zep team
- Self-hosting via **[Coolify](https://coolify.io/)**

---

<div align="center">

**Built with ❤️ by [KoolBrand](https://koolbrand.com)**

*Making AI prediction accessible to everyone*

</div>
