#!/usr/bin/env bash
#
# init.sh — health-check pre-sesión de mirofish (frontend + backend Python).

set -u
cd "$(dirname "$0")"

OK="\033[0;32m✓\033[0m"
FAIL="\033[0;31m✗\033[0m"
WARN="\033[0;33m!\033[0m"
errors=0
warnings=0

check() { local label="$1"; shift; if "$@" >/dev/null 2>&1; then echo -e "  $OK $label"; else echo -e "  $FAIL $label"; errors=$((errors+1)); fi }
warn_check() { local label="$1"; shift; if "$@" >/dev/null 2>&1; then echo -e "  $OK $label"; else echo -e "  $WARN $label  (warning)"; warnings=$((warnings+1)); fi }

echo "== mirofish pre-flight =="

echo ""
echo "Toolchain:"
check "node instalado"       command -v node
check "node >= 18"           bash -c '[ "$(node -p "parseInt(process.versions.node)")" -ge 18 ]'
check "python3 instalado"    command -v python3
check "python3 >= 3.9"       bash -c '[ "$(python3 -c "import sys; print(1 if sys.version_info >= (3,9) else 0)")" = "1" ]'
warn_check "docker instalado" command -v docker

echo ""
echo "Configuración (.env — opcional en local, vive en Coolify para prod):"
warn_check ".env local"                       test -f .env
warn_check "  → LLM_API_KEY no vacío"         bash -c 'test -f .env && grep -q "^LLM_API_KEY=." .env'
warn_check "  → LLM_BASE_URL set"             bash -c 'test -f .env && grep -q "^LLM_BASE_URL=" .env'
warn_check "  → LLM_MODEL_NAME set"           bash -c 'test -f .env && grep -q "^LLM_MODEL_NAME=" .env'
warn_check "  → ZEP_API_KEY no vacío"         bash -c 'test -f .env && grep -q "^ZEP_API_KEY=." .env'
check ".env.example existe (contrato)"        test -f .env.example

echo ""
echo "Frontend (frontend/):"
check "frontend/ existe"                  test -d frontend
check "frontend/package.json existe"      test -f frontend/package.json
warn_check "frontend/node_modules"        test -d frontend/node_modules

echo ""
echo "Backend (backend/):"
check "backend/ existe"                   test -d backend
check "backend/pyproject.toml existe"     test -f backend/pyproject.toml
check "backend/run.py existe"             test -f backend/run.py
warn_check "backend/uploads/ existe"      test -d backend/uploads
warn_check "backend/logs/ existe"         test -d backend/logs

echo ""
echo "Harness:"
check "AGENTS.md existe"                  test -f AGENTS.md
check "AGENTS.md bajo 250 líneas"         bash -c '[ "$(wc -l < AGENTS.md)" -lt 250 ]'
check ".claude/agents/ existe"            test -d .claude/agents
warn_check "subagente planner"            test -f .claude/agents/planner.md
warn_check "subagente quality-gate"       test -f .claude/agents/quality-gate.md

echo ""
echo "== Resumen =="
if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
  echo -e "$OK Todo OK. Listo para operar."
  exit 0
elif [ $errors -eq 0 ]; then
  echo -e "$OK Sin errores ($warnings warning(s))."
  exit 0
else
  echo -e "$FAIL $errors error(es) + $warnings warning(s). Arreglar antes de operar."
  exit 1
fi
