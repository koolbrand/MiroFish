#!/bin/sh
# Construye el banco del CIS en el volumen persistente del servidor. Idempotente: si el banco ya existe, no hace nada.
#
# Los microdatos NUNCA van al repositorio ni a la imagen: se descargan aquí, del propio CIS (cis.es, enlaces públicos de
# los ficheros de datos), se comprueba su huella y se construye el SQLite en `POBLACION_BANCOS_DIR`. Uso interno de I+D.
# Fuente de datos: CIS. Pensado para el «comando posterior al despliegue» de Coolify (ver AGENTS.md); tarda unos 10 min
# y se lanza en segundo plano para no retrasar el despliegue.
#
#   setsid nohup sh /app/backend/scripts/poblacion/instalar_banco_cis.sh >/app/backend/logs/instalar_banco.log 2>&1 &
set -eu

DIR="${POBLACION_BANCOS_DIR:-/app/backend/uploads/poblacion}"
DEST="$DIR/banco_cis.sqlite"
LOCK="$DIR/.construyendo"
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"          # .../backend

mkdir -p "$DIR"
if [ -s "$DEST" ]; then echo "[banco] ya existe ($DEST): nada que hacer"; exit 0; fi
# Otro proceso lo está construyendo (un bloqueo de menos de 90 min cuenta como vivo)
if [ -e "$LOCK" ] && [ -n "$(find "$LOCK" -mmin -90 2>/dev/null)" ]; then echo "[banco] ya se está construyendo"; exit 0; fi

touch "$LOCK"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; rm -f "$LOCK"' EXIT

huella() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

bajar() {   # bajar <fichero> <sha256> <url>
  curl -fsSL --retry 3 --max-time 300 -o "$TMP/$1" "$3"
  esperado="$2"; real="$(huella "$TMP/$1")"
  [ "$real" = "$esperado" ] || { echo "[banco] huella distinta en $1 (el CIS lo habrá actualizado): $real"; exit 1; }
  echo "[banco] $1 ok"
}

bajar MD3505.zip df1f28248e622ac23fde454c3c4f2e4c8ff293bdbb2705be26ec64fc5e255392 "https://www.cis.es/documents/20117/13445319/MD3505.zip/e207cbfa-1d03-b893-8d59-3b6f34cf689e?version=1.1&t=1759848544086"
bajar MD3530.zip 758ff3f1f1bf8cd99c447a0838774da756c229080c36c71e8ae1bfce5f646de7 "https://www.cis.es/documents/20117/13661534/MD3530.zip/4dbf36a7-f66f-4b68-3290-7e9ab5de99fc?version=1.0&t=1764843560323"
bajar MD3535.zip b99df0c28663621e5cc9be72f6a216c90195adf37958812156b2e997ceb524f0 "https://www.cis.es/documents/20117/13708575/MD3535.zip/a97e2745-1f30-1973-b837-d763f262a38f?version=1.0&t=1768547465757"
bajar MD3571.zip b471e1c42f34f5642ed6ece014f09162803d8c3e145551f8a5cd365045939fca "https://www.cis.es/documents/20117/14189298/MD3571.zip/b1a9a24f-691c-a1c1-31b9-54085ac661b9?version=1.0&t=1788778183030"
bajar MD3577.zip 8669fc19f6bc038e823119aacee7a79bc438a7eb95cd6f7206acdce0021f1230 "https://www.cis.es/documents/20117/14250083/MD3577.zip/71da2723-5a10-0e95-7127-8531f06a816d?version=1.0&t=1790163543856"

# pandas y pyreadstat solo hacen falta para construir: van a una carpeta temporal, no al entorno de la aplicación
# (el entorno de la aplicación no trae pip: se usa el Python del sistema, que es de la misma versión)
PIP_PY="${PIP_PY:-/usr/local/bin/python}"; [ -x "$PIP_PY" ] || PIP_PY="$(command -v python3)"
"$PIP_PY" -m pip install --quiet --no-cache-dir --target "$TMP/deps" pyreadstat pandas
cd "$RAIZ"
PYTHONPATH="$TMP/deps:$RAIZ" python scripts/poblacion/build_banco_cis.py "$TMP"/MD35*.zip --reemplazar --salida "$DEST.tmp"
mv "$DEST.tmp" "$DEST"
echo "[banco] listo: $DEST ($(du -h "$DEST" | cut -f1))"
