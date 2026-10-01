#!/usr/bin/env bash
#
# Copia de seguridad de Simuloo. Hasta ahora no existía ninguna: un volumen borrado (o un `docker volume prune`, o
# el disco del servidor) se llevaba todos los proyectos, simulaciones e informes sin vuelta atrás.
#
# Qué copia:
#   ficheros  El volumen `mirofish_uploads`: proyectos, simulaciones e informes (JSON y texto). Es lo valioso y
#             se copia EN CALIENTE: cada archivo se escribe de forma atómica, así que la copia es coherente
#             archivo a archivo.
#   grafo     El volumen de Neo4j. Neo4j Community no hace copia en caliente: con --grafo se PARA el contenedor
#             unos segundos, se vuelca la base y se vuelve a arrancar. El grafo se puede reconstruir desde el
#             material (≈ 18 min de modelo), por eso no es obligatorio.
#
# Uso (en el servidor donde corre Docker):
#   ops/backup.sh                          copia los ficheros
#   ops/backup.sh --grafo                  ficheros + grafo (para Neo4j un momento)
#   ops/backup.sh --prefix <uuid>_         en Coolify los volúmenes se llaman «<uuid-de-la-app>_mirofish_uploads»
#   ops/backup.sh --dest /srv/copias --keep 14
#
# Restaurar: ver «Copias de seguridad» en COOLIFY_DEPLOYMENT.md.

set -euo pipefail

DEST="${BACKUP_DIR:-./backups}"
KEEP="${BACKUP_KEEP:-14}"
PREFIX="${VOLUME_PREFIX:-}"
WITH_GRAPH=0
NEO4J_CONTAINER="${NEO4J_CONTAINER:-}"
HELPER_IMAGE="${HELPER_IMAGE:-alpine:3.20}"

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dest)       DEST="$2"; shift 2 ;;
    --keep)       KEEP="$2"; shift 2 ;;
    --prefix)     PREFIX="$2"; shift 2 ;;
    --grafo)      WITH_GRAPH=1; shift ;;
    --neo4j)      NEO4J_CONTAINER="$2"; shift 2 ;;
    -h|--help)    usage 0 ;;
    *)            echo "Opción desconocida: $1" >&2; usage 1 ;;
  esac
done

case "$KEEP" in ''|*[!0-9]*) echo "--keep debe ser un número" >&2; exit 1 ;; esac
[ "$KEEP" -ge 1 ] || { echo "--keep debe ser al menos 1" >&2; exit 1; }

command -v docker >/dev/null || { echo "Docker no está disponible" >&2; exit 1; }
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

UPLOADS_VOL="${PREFIX}mirofish_uploads"
GRAPH_VOL="${PREFIX}neo4j_data_v2"

need_volume() {
  docker volume inspect "$1" >/dev/null 2>&1 || {
    echo "No existe el volumen «$1». Volúmenes que hay:" >&2
    docker volume ls --format '  {{.Name}}' | grep -E 'uploads|neo4j' >&2 || true
    echo "Si lleva un prefijo (Coolify usa el uuid de la app), pásalo con --prefix <uuid>_" >&2
    exit 1
  }
}

# Deja solo las KEEP copias más recientes de cada tipo (los nombres llevan la fecha, ordenan solos)
prune() {
  # El comodín de $pattern es a propósito (los nombres los generamos nosotros: sin espacios ni caracteres raros)
  # shellcheck disable=SC2012,SC2086
  local pattern="$1" count
  count=$(ls -1 "$DEST"/$pattern 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -gt "$KEEP" ]; then
    ls -1 "$DEST"/$pattern | head -n "$((count - KEEP))" | while read -r old; do
      rm -f -- "$old" && echo "  borrada la copia antigua: $(basename "$old")"
    done
  fi
}

backup_uploads() {
  need_volume "$UPLOADS_VOL"
  local out="simuloo-ficheros-$STAMP.tar.gz"
  echo "→ Ficheros: $UPLOADS_VOL"
  # Se escribe con nombre temporal y se renombra al final: una copia a medias nunca parece completa
  docker run --rm -v "$UPLOADS_VOL":/data:ro -v "$DEST":/backup "$HELPER_IMAGE" \
    sh -c "tar czf /backup/.$out.part -C /data . && mv /backup/.$out.part /backup/$out"
  tar tzf "$DEST/$out" >/dev/null || { echo "La copia $out no se puede leer" >&2; exit 1; }
  echo "  $out ($(du -h "$DEST/$out" | cut -f1), $(tar tzf "$DEST/$out" | grep -c '/$' || true) carpetas)"
  prune 'simuloo-ficheros-*.tar.gz'
}

find_neo4j_container() {
  [ -n "$NEO4J_CONTAINER" ] && { echo "$NEO4J_CONTAINER"; return; }
  # El contenedor que monta el volumen del grafo
  docker ps -a --filter "volume=$GRAPH_VOL" --format '{{.Names}}' | head -n 1
}

backup_graph() {
  need_volume "$GRAPH_VOL"
  local container image out="simuloo-grafo-$STAMP.dump"
  container="$(find_neo4j_container)"
  [ -n "$container" ] || { echo "No encuentro el contenedor de Neo4j (usa --neo4j <nombre>)" >&2; exit 1; }
  image="$(docker inspect --format '{{.Config.Image}}' "$container")"
  echo "→ Grafo: $GRAPH_VOL (contenedor $container, imagen $image) — Neo4j parado unos segundos"

  local was_running=0
  [ "$(docker inspect --format '{{.State.Running}}' "$container")" = "true" ] && was_running=1
  # Pase lo que pase, Neo4j vuelve a arrancar
  restart() { [ "$was_running" = 1 ] && docker start "$container" >/dev/null && echo "  Neo4j arrancado de nuevo"; was_running=0; }
  trap restart EXIT
  [ "$was_running" = 1 ] && docker stop --time 60 "$container" >/dev/null

  docker run --rm --entrypoint neo4j-admin -v "$GRAPH_VOL":/data -v "$DEST":/backups "$image" \
    database dump neo4j --to-path=/backups --overwrite-destination=true >/dev/null
  mv "$DEST/neo4j.dump" "$DEST/$out"
  [ -s "$DEST/$out" ] || { echo "El volcado $out salió vacío" >&2; exit 1; }
  restart
  trap - EXIT
  echo "  $out ($(du -h "$DEST/$out" | cut -f1))"
  prune 'simuloo-grafo-*.dump'
}

backup_uploads
[ "$WITH_GRAPH" = 1 ] && backup_graph
echo "Listo. Copias en $DEST"
