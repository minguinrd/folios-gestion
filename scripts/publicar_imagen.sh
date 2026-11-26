#!/usr/bin/env bash
# Publica la imagen de la versión actual en Docker Hub y actualiza la
# descripción del repositorio, en un solo paso.
#
#   DOCKERHUB_USERNAME=... DOCKERHUB_TOKEN=... scripts/publicar_imagen.sh
#
# Antes de construir comprueba:
#   - árbol de trabajo limpio y HEAD ya subido a origin (la imagen sale del
#     mismo código que está en GitHub);
#   - VERSION citado en README, docker-compose.deploy.yml y
#     docker-hub-description.md (la doc no queda en la versión anterior).
# Luego construye <repo>:<VERSION> y :latest, los sube, verifica que ambos
# tags apunten al mismo digest y sube la descripción (scripts/dockerhub_descripcion.py).
# Sin token, publica la imagen y avisa que la descripción quedó pendiente.
set -euo pipefail

cd "$(dirname "$0")/.."

REPO="${DOCKERHUB_REPO:-m809/folios-gestion}"
VERSION="$(tr -d '[:space:]' < VERSION)"

fallar() { echo "[publicar] ERROR: $*" >&2; exit 1; }

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fallar "VERSION inválido: '$VERSION'"

[ -z "$(git status --porcelain)" ] || fallar "hay cambios sin commit"
git fetch -q origin
rama="$(git rev-parse --abbrev-ref HEAD)"
[ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$rama" 2>/dev/null)" ] \
    || fallar "HEAD no coincide con origin/$rama: haga push antes de publicar"

for archivo in README.md docker-compose.deploy.yml docker-hub-description.md; do
    grep -q "$VERSION" "$archivo" || fallar "$archivo no menciona la versión $VERSION"
done

if docker buildx imagetools inspect "$REPO:$VERSION" >/dev/null 2>&1; then
    fallar "$REPO:$VERSION ya existe en Docker Hub: suba VERSION antes de publicar"
fi

echo "[publicar] Construyendo $REPO:$VERSION y :latest…"
docker build -t "$REPO:$VERSION" -t "$REPO:latest" .

[ "$(docker run --rm --entrypoint cat "$REPO:$VERSION" VERSION | tr -d '[:space:]')" = "$VERSION" ] \
    || fallar "la imagen no trae VERSION=$VERSION"

docker push "$REPO:$VERSION"
docker push "$REPO:latest"

d1="$(docker buildx imagetools inspect "$REPO:$VERSION" --format '{{json .Manifest.Digest}}')"
d2="$(docker buildx imagetools inspect "$REPO:latest" --format '{{json .Manifest.Digest}}')"
[ "$d1" = "$d2" ] || fallar "los tags $VERSION y latest apuntan a digests distintos"
echo "[publicar] $REPO:$VERSION = :latest ($d1)"

if [ -n "${DOCKERHUB_USERNAME:-}" ] && [ -n "${DOCKERHUB_TOKEN:-}" ]; then
    python3 scripts/dockerhub_descripcion.py
else
    echo "[publicar] AVISO: sin DOCKERHUB_USERNAME/DOCKERHUB_TOKEN; la descripción de" \
         "Docker Hub NO se actualizó. Ejecute luego: scripts/dockerhub_descripcion.py" >&2
fi
