#!/usr/bin/env bash
# rotate-secrets.sh — Rotate secrets in Key Vault and restart Container Apps
#
# Rotates service credentials and re-deploys container apps to pick up new values.
# Currently supports: storage-key, servicebus-key, cosmos-key
#
# Usage:
#   ./infrastructure/bicep/scripts/rotate-secrets.sh dev    storage
#   ./infrastructure/bicep/scripts/rotate-secrets.sh prod   cosmos
#   ./infrastructure/bicep/scripts/rotate-secrets.sh prod   all
#
# Prerequisites:
#   - az CLI logged in, target subscription set
#   - Managed identity with Key Vault Secrets Officer role (already granted by Bicep)

set -euo pipefail

ENVIRONMENT="${1:-}"
SECRET_TARGET="${2:-all}"

if [[ -z "${ENVIRONMENT}" ]] || [[ ! "${ENVIRONMENT}" =~ ^(dev|staging|prod)$ ]]; then
  echo "Usage: $0 <dev|staging|prod> <storage|servicebus|cosmos|all>"
  exit 1
fi

APP_NAME="kaats"
NAME_PREFIX="${APP_NAME}-${ENVIRONMENT}"
RG_NAME="rg-${NAME_PREFIX}"

# ── Resolve resource names from the resource group ───────────────────────────

KV_NAME=$(az keyvault list \
  --resource-group "${RG_NAME}" \
  --query "[0].name" \
  --output tsv)

if [[ -z "${KV_NAME}" ]]; then
  echo "ERROR: No Key Vault found in ${RG_NAME}"
  exit 1
fi

echo "Key Vault: ${KV_NAME}"

# ── Rotate storage key ────────────────────────────────────────────────────────

rotate_storage() {
  echo "Rotating Storage Account key..."

  SA_NAME=$(az storage account list \
    --resource-group "${RG_NAME}" \
    --query "[0].name" \
    --output tsv)

  if [[ -z "${SA_NAME}" ]]; then
    echo "ERROR: No Storage Account found in ${RG_NAME}"
    return 1
  fi

  # Rotate key2 (keep key1 valid during rotation)
  az storage account keys renew \
    --account-name "${SA_NAME}" \
    --resource-group "${RG_NAME}" \
    --key key2 \
    --output none

  NEW_CONN_STR=$(az storage account show-connection-string \
    --account-name "${SA_NAME}" \
    --resource-group "${RG_NAME}" \
    --key key2 \
    --query "connectionString" \
    --output tsv)

  az keyvault secret set \
    --vault-name "${KV_NAME}" \
    --name "storage-connection-string" \
    --value "${NEW_CONN_STR}" \
    --output none

  echo "✓ Storage key rotated"
}

# ── Rotate Service Bus SAS key ────────────────────────────────────────────────

rotate_servicebus() {
  echo "Rotating Service Bus SAS key..."

  SB_NAME=$(az servicebus namespace list \
    --resource-group "${RG_NAME}" \
    --query "[0].name" \
    --output tsv)

  if [[ -z "${SB_NAME}" ]]; then
    echo "ERROR: No Service Bus namespace found in ${RG_NAME}"
    return 1
  fi

  # Regenerate secondary key, then update secret
  az servicebus namespace authorization-rule keys renew \
    --resource-group "${RG_NAME}" \
    --namespace-name "${SB_NAME}" \
    --name "RootManageSharedAccessKey" \
    --key SecondaryKey \
    --output none

  NEW_CONN_STR=$(az servicebus namespace authorization-rule keys list \
    --resource-group "${RG_NAME}" \
    --namespace-name "${SB_NAME}" \
    --name "RootManageSharedAccessKey" \
    --query "secondaryConnectionString" \
    --output tsv)

  az keyvault secret set \
    --vault-name "${KV_NAME}" \
    --name "service-bus-connection-string" \
    --value "${NEW_CONN_STR}" \
    --output none

  echo "✓ Service Bus key rotated"
}

# ── Rotate Cosmos DB key ──────────────────────────────────────────────────────

rotate_cosmos() {
  echo "Rotating Cosmos DB key..."

  COSMOS_NAME=$(az cosmosdb list \
    --resource-group "${RG_NAME}" \
    --query "[0].name" \
    --output tsv)

  if [[ -z "${COSMOS_NAME}" ]]; then
    echo "ERROR: No Cosmos DB account found in ${RG_NAME}"
    return 1
  fi

  # Regenerate secondary key (primary stays valid during rotation window)
  az cosmosdb keys regenerate \
    --resource-group "${RG_NAME}" \
    --name "${COSMOS_NAME}" \
    --key-kind secondary \
    --output none

  NEW_KEY=$(az cosmosdb keys list \
    --resource-group "${RG_NAME}" \
    --name "${COSMOS_NAME}" \
    --query "secondaryMasterKey" \
    --output tsv)

  az keyvault secret set \
    --vault-name "${KV_NAME}" \
    --name "cosmos-key" \
    --value "${NEW_KEY}" \
    --output none

  echo "✓ Cosmos DB key rotated"
}

# ── Execute selected rotation(s) ─────────────────────────────────────────────

case "${SECRET_TARGET}" in
  storage)    rotate_storage ;;
  servicebus) rotate_servicebus ;;
  cosmos)     rotate_cosmos ;;
  all)
    rotate_storage
    rotate_servicebus
    rotate_cosmos
    ;;
  *)
    echo "ERROR: Unknown target '${SECRET_TARGET}'. Use: storage, servicebus, cosmos, all"
    exit 1
    ;;
esac

# ── Restart Container Apps to pick up new secrets ────────────────────────────

echo ""
echo "Restarting Container Apps to reload secrets..."

for APP in "${NAME_PREFIX}-api" "${NAME_PREFIX}-worker"; do
  echo "  Restarting ${APP}..."
  az containerapp revision list \
    --name "${APP}" \
    --resource-group "${RG_NAME}" \
    --query "[0].name" \
    --output tsv | xargs -I{} az containerapp revision restart \
      --revision {} \
      --name "${APP}" \
      --resource-group "${RG_NAME}" \
      --output none
  echo "  ✓ ${APP} restarted"
done

echo ""
echo "Secret rotation complete for environment: ${ENVIRONMENT}"
echo "Target: ${SECRET_TARGET}"
