#!/usr/bin/env bash
# deploy.sh — Deploy KAATS infrastructure via Azure Bicep
#
# Usage:
#   ./infrastructure/bicep/scripts/deploy.sh dev    [--what-if]
#   ./infrastructure/bicep/scripts/deploy.sh staging
#   ./infrastructure/bicep/scripts/deploy.sh prod
#
# Prerequisites:
#   - az CLI >= 2.50 logged in (az login)
#   - Target subscription set: az account set --subscription <id>
#   - Bicep CLI installed (az bicep install)

set -euo pipefail

ENVIRONMENT="${1:-}"
WHAT_IF="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Validate args ─────────────────────────────────────────────────────────────

if [[ -z "${ENVIRONMENT}" ]] || [[ ! "${ENVIRONMENT}" =~ ^(dev|staging|prod)$ ]]; then
  echo "Usage: $0 <dev|staging|prod> [--what-if]"
  exit 1
fi

PARAMS_FILE="${BICEP_DIR}/parameters/${ENVIRONMENT}.bicepparam"
if [[ ! -f "${PARAMS_FILE}" ]]; then
  echo "ERROR: Parameter file not found: ${PARAMS_FILE}"
  exit 1
fi

# ── Derive deployment metadata ────────────────────────────────────────────────

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
DEPLOYMENT_NAME="kaats-${ENVIRONMENT}-${TIMESTAMP}"
LOCATION="eastus"

echo "========================================"
echo " KAATS Infrastructure Deployment"
echo " Environment : ${ENVIRONMENT}"
echo " Parameters  : ${PARAMS_FILE}"
echo " Deployment  : ${DEPLOYMENT_NAME}"
echo "========================================"

# ── Confirm prod deployments ──────────────────────────────────────────────────

if [[ "${ENVIRONMENT}" == "prod" && "${WHAT_IF}" != "--what-if" ]]; then
  read -rp "WARNING: You are about to deploy to PRODUCTION. Type 'yes' to continue: " CONFIRM
  if [[ "${CONFIRM}" != "yes" ]]; then
    echo "Deployment cancelled."
    exit 0
  fi
fi

# ── Run deployment ────────────────────────────────────────────────────────────

CMD=(
  az deployment sub create
  --name "${DEPLOYMENT_NAME}"
  --location "${LOCATION}"
  --template-file "${BICEP_DIR}/main.bicep"
  --parameters "${PARAMS_FILE}"
)

if [[ "${WHAT_IF}" == "--what-if" ]]; then
  echo "Running what-if analysis..."
  az deployment sub what-if \
    --location "${LOCATION}" \
    --template-file "${BICEP_DIR}/main.bicep" \
    --parameters "${PARAMS_FILE}"
  exit 0
fi

echo ""
echo "Starting deployment..."
"${CMD[@]}"

# ── Print outputs ─────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo " Deployment complete. Outputs:"
echo "========================================"
az deployment sub show \
  --name "${DEPLOYMENT_NAME}" \
  --query "properties.outputs" \
  --output table

echo ""
echo "Done. To deploy container images, run:"
echo "  ./infrastructure/bicep/scripts/deploy-images.sh ${ENVIRONMENT} <image-tag>"
