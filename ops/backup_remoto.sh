#!/usr/bin/env bash
#
# Recoge la copia de seguridad de Simuloo (GET /api/backup/export), la VERIFICA y la deja en el NAS con rotación.
# Pensado para correr cada noche en una máquina siempre encendida con acceso al NAS (el Mac mini, con launchd:
# ops/com.koolbrand.simuloo-backup.plist). El servidor de producción no se alcanza por SSH, así que la copia no se
# «empuja» desde allí: se «tira» de ella por HTTPS con una credencial propia de solo lectura (BACKUP_TOKEN).
#
# Qué comprueba antes de aceptar la copia:
#   1. HTTP 200 y que la cabecera X-Backup-Sha256 coincide con lo descargado
#   2. que el .tar.gz se lee entero (gzip -t) y trae un MANIFIESTO.json válido
#   3. tras subirla al NAS, que el tamaño allí es el mismo
# Y avisa (sin descartar la copia) si el nº de proyectos baja respecto a la anterior.
#
# Uso:
#   ops/backup_remoto.sh                    hace la copia
#   ops/backup_remoto.sh --comprobar [H]    sale con error si la última copia tiene más de H horas (36 por defecto)
#
# Configuración (variables de entorno, todas opcionales):
#   SIMULOO_URL           https://simuloo.koolgrowth.com
#   SIMULOO_TOKEN_FILE    ~/.simuloo/backup-token   (UNA línea: «X-Backup-Token: <token>», chmod 600)
#   NAS_HOST              nas        (vacío = guardar en una carpeta local; sirve para probar)
#   NAS_DIR               /share/Koolbrand/Bianka/entregables/003 - Simuloo/_copias-automaticas
#   KEEP                  21         copias que se conservan
#   LOG                   ~/Library/Logs/simuloo-backup.log

set -euo pipefail

URL="${SIMULOO_URL:-https://simuloo.koolgrowth.com}"
TOKEN_FILE="${SIMULOO_TOKEN_FILE:-$HOME/.simuloo/backup-token}"
NAS_HOST="${NAS_HOST-nas}"
NAS_DIR="${NAS_DIR:-/share/Koolbrand/Bianka/entregables/003 - Simuloo/_copias-automaticas}"
KEEP="${KEEP:-21}"
LOG="${LOG:-$HOME/Library/Logs/simuloo-backup.log}"
MARKER="ULTIMA_COPIA.json"

mkdir -p "$(dirname "$LOG")"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG" >&2; }
fail() { log "ERROR: $*"; exit 1; }

sha256_of() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

# Ejecuta un comando de shell en el destino (el NAS por ssh, o aquí mismo). La entrada estándar pasa tal cual.
dest_run() {
  if [ -n "$NAS_HOST" ]; then ssh -o BatchMode=yes -o ConnectTimeout=20 "$NAS_HOST" "$1"
  else sh -c "$1"; fi
}
q() { printf '%q' "$1"; }                                # entrecomillado seguro para el shell remoto (rutas con espacios)
DIR_Q="$(q "$NAS_DIR")"

# ---------- --comprobar ----------
if [ "${1:-}" = "--comprobar" ]; then
  HOURS="${2:-36}"
  json="$(dest_run "cat $DIR_Q/$MARKER 2>/dev/null" </dev/null || true)"
  [ -n "$json" ] || fail "no hay ninguna copia registrada en $NAS_DIR"
  age_h="$(printf '%s' "$json" | python3 -c 'import json,sys,datetime as d; m=json.load(sys.stdin); t=d.datetime.fromisoformat(m["fecha"]); print(int((d.datetime.now(d.timezone.utc)-t).total_seconds()//3600))')"
  [ "$age_h" -le "$HOURS" ] || fail "la última copia tiene $age_h h (máximo $HOURS h)"
  log "OK: la última copia tiene $age_h h"; exit 0
fi

# ---------- copia ----------
[ -f "$TOKEN_FILE" ] || fail "no existe el fichero del token ($TOKEN_FILE)"
perms="$(stat -f '%Lp' "$TOKEN_FILE" 2>/dev/null || stat -c '%a' "$TOKEN_FILE")"
case "$perms" in 600|400) ;; *) fail "el fichero del token debe ser chmod 600 (es $perms)";; esac
case "$KEEP" in ''|*[!0-9]*|0) fail "KEEP debe ser un número mayor que 0";; esac

work="$(mktemp -d "${TMPDIR:-/tmp}/simuloo-backup.XXXXXX")"
trap 'rm -rf "$work"' EXIT
name="simuloo-$(date -u '+%Y%m%d-%H%M%S').tar.gz"

log "Descargando de $URL …"
code="$(curl -sS --retry 3 --retry-delay 10 --retry-connrefused --max-time 1800 \
  -H "@$TOKEN_FILE" -D "$work/headers" -o "$work/$name" -w '%{http_code}' "$URL/api/backup/export" || true)"
[ "$code" = "200" ] || fail "el servidor respondió HTTP ${code:-sin respuesta} (¿BACKUP_TOKEN mal puesto o app caída?)"

expected="$(tr -d '\r' < "$work/headers" | awk -F': ' 'tolower($1)=="x-backup-sha256"{print $2}')"
actual="$(sha256_of "$work/$name")"
{ [ -n "$expected" ] && [ "$expected" = "$actual" ]; } || fail "el sha256 no coincide (esperado ${expected:-ninguno}, recibido $actual): descarga corrupta"
gzip -t "$work/$name" 2>/dev/null || fail "el .tar.gz no se lee entero"
manifest="$(tar -xzOf "$work/$name" MANIFIESTO.json 2>/dev/null)" || fail "la copia no trae MANIFIESTO.json"
summary="$(printf '%s' "$manifest" | python3 -c '
import json,sys
m=json.load(sys.stdin)
assert m["formato"]==1 and isinstance(m["archivos"],list)
print(m["proyectos"],m["ficheros"],m["bytes"],len(m["omitidos"]))')" || fail "el MANIFIESTO.json no es válido"
read -r projects files bytes skipped <<<"$summary"
size="$(wc -c < "$work/$name" | tr -d ' ')"
log "Descargada y verificada: $projects proyectos, $files ficheros, $bytes bytes ($size comprimidos), $skipped omitidos"

# ¿ha bajado el nº de proyectos? (puede ser legítimo: avisa, no descarta)
prev="$(dest_run "cat $DIR_Q/$MARKER 2>/dev/null" </dev/null 2>/dev/null || true)"
if [ -n "$prev" ]; then
  prev_projects="$(printf '%s' "$prev" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("proyectos",0))' 2>/dev/null || echo 0)"
  if [ "$projects" -lt "$prev_projects" ]; then log "AVISO: hay $projects proyectos y la copia anterior tenía $prev_projects"; fi
fi

# Subida con nombre provisional; se renombra al final, así una copia a medias nunca parece completa
log "Subiendo a ${NAS_HOST:-carpeta local}:$NAS_DIR …"
NAME_Q="$(q "$name")"
dest_run "mkdir -p $DIR_Q && cat > $DIR_Q/.$NAME_Q.part" < "$work/$name" || fail "no se pudo escribir en el destino"
remote_size="$(dest_run "wc -c < $DIR_Q/.$NAME_Q.part" </dev/null | tr -d ' ')"
if [ "$remote_size" != "$size" ]; then
  dest_run "rm -f $DIR_Q/.$NAME_Q.part" </dev/null || true
  fail "en el destino la copia pesa $remote_size bytes y debería pesar $size"
fi
dest_run "mv $DIR_Q/.$NAME_Q.part $DIR_Q/$NAME_Q" </dev/null || fail "no se pudo renombrar la copia en el destino"

# Marca de la última copia buena (la lee --comprobar)
printf '{"fecha": "%s", "archivo": "%s", "sha256": "%s", "proyectos": %s, "ficheros": %s, "bytes": %s, "comprimidos": %s}\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%S+00:00')" "$name" "$actual" "$projects" "$files" "$bytes" "$size" \
  | dest_run "cat > $DIR_Q/$MARKER"

# Rotación: se quedan las KEEP más recientes (los nombres llevan la fecha: ordenar es ordenar por tiempo)
old="$(dest_run "ls -1 $DIR_Q 2>/dev/null | grep -E '^simuloo-[0-9]{8}-[0-9]{6}[.]tar[.]gz\$' | sort" </dev/null || true)"
total="$(printf '%s\n' "$old" | grep -c . || true)"
if [ "$total" -gt "$KEEP" ]; then
  printf '%s\n' "$old" | head -n "$((total - KEEP))" | while read -r f; do
    dest_run "rm -f $DIR_Q/$(q "$f")" </dev/null && log "Borrada la copia antigua $f"
  done
fi
log "Hecho: $name ($size bytes) guardada; hay $(( total > KEEP ? KEEP : total )) copias"
