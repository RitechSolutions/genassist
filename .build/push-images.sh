#!/usr/bin/env bash
set -euo pipefail

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ Missing dependency: $1"; exit 1; }; }

need docker

OWNER="${OWNER:?Set OWNER (GitHub org/user)}"
REPO="${REPO:?Set REPO}"
VERSION="${VERSION:?Set VERSION (e.g. 1.2.3)}"

REGISTRY="${REGISTRY:-ghcr.io}"
NAMESPACE="${REGISTRY}/${OWNER}/${REPO}"

# Compose files:
# - docker-compose.yml                (runtime compose: images/env/depends_on/etc.)
# - .build/docker-compose.build.yml   (build overrides: build contexts, additional_contexts)
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
BUILD_COMPOSE_FILE="${BUILD_COMPOSE_FILE:-.build/docker-compose.build.yml}"

PUSH_UITESTS="${PUSH_UITESTS:-false}"

# Immutable release tag (defaults to VERSION)
IMAGE_TAG="${IMAGE_TAG:-$VERSION}"

# Moving tags
PROD_TAG="${PROD_TAG:-prod}"
LATEST_TAG="${LATEST_TAG:-latest}"

# Image repositories (no tag)
APP_IMAGE="${APP_IMAGE:-${NAMESPACE}/app}"
UI_IMAGE="${UI_IMAGE:-${NAMESPACE}/ui}"
WHISPER_IMAGE="${WHISPER_IMAGE:-${NAMESPACE}/whisper}"
UITESTS_IMAGE="${UITESTS_IMAGE:-${NAMESPACE}/uitests}"

export IMAGE_TAG APP_IMAGE UI_IMAGE WHISPER_IMAGE UITESTS_IMAGE
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"
export COMPOSE_DOCKER_CLI_BUILD="${COMPOSE_DOCKER_CLI_BUILD:-1}"

echo "============================================================"
echo "🚀 Releasing images to GHCR"
echo "  Registry    : ${REGISTRY}"
echo "  Namespace   : ${NAMESPACE}"
echo "  Version tag : ${IMAGE_TAG}"
echo "  Prod tag    : ${PROD_TAG}"
echo "  Latest tag  : ${LATEST_TAG}"
echo "  Compose     : ${COMPOSE_FILE}"
echo "  Build file  : ${BUILD_COMPOSE_FILE}"
echo "============================================================"

# ---- GHCR login (non-interactive friendly)
if [ -z "${GHCR_TOKEN:-}" ]; then
  echo "❌ GHCR_TOKEN is not set."
  echo "   Export it and rerun, e.g.:"
  echo "   export GHCR_TOKEN='...'"
  exit 1
fi

echo "${GHCR_TOKEN}" | docker login "${REGISTRY}" -u "${OWNER}" --password-stdin >/dev/null
echo "✅ Logged into ${REGISTRY}"

SERVICES=(app ui whisper)
if [ "${PUSH_UITESTS}" = "true" ]; then
  SERVICES+=(uitests)
fi

# Use both compose files so build contexts exist
COMPOSE_ARGS=(-f "${COMPOSE_FILE}" -f "${BUILD_COMPOSE_FILE}")

echo "==> Services to build/push: ${SERVICES[*]}"

echo "==> Building (compose)..."
docker compose "${COMPOSE_ARGS[@]}" build "${SERVICES[@]}"

echo "==> Verifying local images exist..."
CHECK_IMAGES=("${APP_IMAGE}:${IMAGE_TAG}" "${UI_IMAGE}:${IMAGE_TAG}" "${WHISPER_IMAGE}:${IMAGE_TAG}")
if [ "${PUSH_UITESTS}" = "true" ]; then
  CHECK_IMAGES+=("${UITESTS_IMAGE}:${IMAGE_TAG}")
fi

for img in "${CHECK_IMAGES[@]}"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "❌ Expected local image not found: $img"
    echo "   This usually means compose didn't tag the image correctly."
    exit 1
  fi
done

echo "==> Pushing versioned tags..."
docker compose "${COMPOSE_ARGS[@]}" push "${SERVICES[@]}"

echo "==> Creating and pushing '${PROD_TAG}' and '${LATEST_TAG}' tags..."
IMAGES=("${APP_IMAGE}" "${UI_IMAGE}" "${WHISPER_IMAGE}")
if [ "${PUSH_UITESTS}" = "true" ]; then
  IMAGES+=("${UITESTS_IMAGE}")
fi

for IMG in "${IMAGES[@]}"; do
  echo "  - Tagging ${IMG}:${IMAGE_TAG} -> ${IMG}:${PROD_TAG}"
  docker tag "${IMG}:${IMAGE_TAG}" "${IMG}:${PROD_TAG}"
  echo "  - Pushing ${IMG}:${PROD_TAG}"
  docker push "${IMG}:${PROD_TAG}"

  echo "  - Tagging ${IMG}:${IMAGE_TAG} -> ${IMG}:${LATEST_TAG}"
  docker tag "${IMG}:${IMAGE_TAG}" "${IMG}:${LATEST_TAG}"
  echo "  - Pushing ${IMG}:${LATEST_TAG}"
  docker push "${IMG}:${LATEST_TAG}"
done

echo "============================================================"
echo "✅ Done."
echo "Pushed tags:"
echo "  - ${APP_IMAGE}:${IMAGE_TAG}, :${PROD_TAG}, :${LATEST_TAG}"
echo "  - ${UI_IMAGE}:${IMAGE_TAG}, :${PROD_TAG}, :${LATEST_TAG}"
echo "  - ${WHISPER_IMAGE}:${IMAGE_TAG}, :${PROD_TAG}, :${LATEST_TAG}"
if [ "${PUSH_UITESTS}" = "true" ]; then
  echo "  - ${UITESTS_IMAGE}:${IMAGE_TAG}, :${PROD_TAG}, :${LATEST_TAG}"
fi
echo "============================================================"
