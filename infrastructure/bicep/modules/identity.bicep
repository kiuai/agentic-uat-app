// ── User-Assigned Managed Identity ───────────────────────────────────────────
// Single identity used by all Container Apps to access Azure services via RBAC.

@description('Azure region for all resources')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Tags to apply to all resources')
param tags object = {}

// ── Identity ─────────────────────────────────────────────────────────────────

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-id'
  location: location
  tags: tags
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Resource ID of the managed identity')
output identityId string = identity.id

@description('Client ID of the managed identity (used in app config)')
output clientId string = identity.properties.clientId

@description('Principal ID of the managed identity (used for RBAC assignments)')
output principalId string = identity.properties.principalId

@description('Resource name of the managed identity')
output name string = identity.name
