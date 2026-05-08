#!/usr/bin/env bash
# deploy-images.sh — Build and push Docker images to ACR, then update Container Apps
#
# Usage:
#   ./infrastructure/bicep/scripts/deploy-images.sh dev    <git-sha>
#   ./infrastructure/bicep/scripts/deploy-images.sh staging abc1234
#   ./infrastructure/bicep/scripts/deploy-images.sh prod    v1.2.3
#
# Prerequisites:
#   - Docker available
#   - az CLI logged in, target subscription set
#   - Run deploy.sh first to create the ACR

set -euo pipefail

ENVIRONMENT="${1:-}"
IMAGE_TAG="${2:-}"

if [[ -z "${ENVIRONMENT}" ]] || [[ -z "${IMAGE_TAG}" ]]; then
  echo "Usage: $0 <dev|staging|prod> <image-tag>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
APP_NAME="kaats"
NAME_PREFIX="${APP_NAME}-${ENVIRONMENT}"
RG_NAME="rg-${NAME_PREFIX}"

# ── Resolve ACR login server ──────────────────────────────────────────────────

ACR_NAME=$(az acr list \
  --resource-group "${RG_NAME}" \
  --query "[0].name" \
  --output tsv)

if [[ -z "${ACR_NAME}" ]]; then
  echo "ERROR: No ACR found in resource group ${RG_NAME}"
  echo "Run deploy.sh first."
  exit 1
fi

ACR_SERVER=$(az acr show \
  --name "${ACR_NAME}" \
  --resource-group "${RG_NAME}" \
  --query "loginServer" \
  --output tsv)

echo "ACR: ${ACR_SERVER}"

# ── Login to ACR ──────────────────────────────────────────────────────────────

az acr login --name "${ACR_NAME}"

# ── Build and push images ─────────────────────────────────────────────────────

IMAGES=(
  "kaats-api:${REPO_ROOT}/backend:Dockerfile"
  "kaats-worker:${REPO_ROOT}/backend:Dockerfile.worker"
  "kaats-frontend:${REPO_ROOT}/frontend:Dockerfile"
)

for entry in "${IMAGES[@]}"; do
  IFS=':' read -r IMAGE_NAME CONTEXT DOCKERFILE <<< "${entry}"
  FULL_IMAGE="${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
  LATEST_IMAGE="${ACR_SERVER}/${IMAGE_NAME}:latest"

  echo ""
  echo "Building ${IMAGE_NAME}..."

  if [[ -f "${CONTEXT}/${DOCKERFILE}" ]]; then
    docker build \
      -t "${FULL_IMAGE}" \
      -t "${LATEST_IMAGE}" \
      -f "${CONTEXT}/${DOCKERFILE}" \
      "${CONTEXT}"
  else
    # Fallback: use default Dockerfile in context directory
    docker build \
      -t "${FULL_IMAGE}" \
      -t "${LATEST_IMAGE}" \
      "${CONTEXT}"
  fi

  echo "Pushing ${FULL_IMAGE}..."
  docker push "${FULL_IMAGE}"
  docker push "${LATEST_IMAGE}"
  echo "✓ ${IMAGE_NAME}:${IMAGE_TAG}"
done

# ── Update Container Apps with new image tag ──────────────────────────────────

echo ""
echo "Updating Container Apps to image tag: ${IMAGE_TAG}"

APPS=(
  "${NAME_PREFIX}-api:kaats-api"
  "${NAME_PREFIX}-worker:kaats-worker"
  "${NAME_PREFIX}-frontend:kaats-frontend"
)

for entry in "${APPS[@]}"; do
  IFS=':' read -r APP_NAME_FULL IMAGE_NAME <<< "${entry}"
  echo "  Updating ${APP_NAME_FULL}..."
  az containerapp update \
    --name "${APP_NAME_FULL}" \
    --resource-group "${RG_NAME}" \
    --image "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --output none
  echo "  ✓ ${APP_NAME_FULL}"
done

echo ""
echo "========================================"
echo " Image deployment complete"
echo " Tag: ${IMAGE_TAG}"
echo " Environment: ${ENVIRONMENT}"
echo "========================================"

# ── Print app URLs ────────────────────────────────────────────────────────────

echo ""
echo "Application URLs:"
az containerapp show \
  --name "${NAME_PREFIX}-api" \
  --resource-group "${RG_NAME}" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv | xargs -I{} echo "  API:      https://{}"

az containerapp show \
  --name "${NAME_PREFIX}-frontend" \
  --resource-group "${RG_NAME}" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv | xargs -I{} echo "  Frontend: https://{}"
