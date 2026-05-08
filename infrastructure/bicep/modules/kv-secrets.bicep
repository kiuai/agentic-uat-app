// ── Key Vault Secrets ─────────────────────────────────────────────────────────
// Writes all application secrets into Key Vault.
// Deployed after Key Vault is created and RBAC is in place.

@description('Key Vault name')
param keyVaultName string

@description('Map of secret name → value')
@secure()
param secrets object

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Bicep doesn't support dynamic keys in a loop from an object, so we enumerate
// each secret individually. This ensures idempotent updates.

resource dbUrlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'database-url'
  properties: { value: secrets['database-url'] }
}

resource cosmosEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'cosmos-endpoint'
  properties: { value: secrets['cosmos-endpoint'] }
}

resource cosmosKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'cosmos-key'
  properties: { value: secrets['cosmos-key'] }
}

resource sbConnStrSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'service-bus-connection-string'
  properties: { value: secrets['service-bus-connection-string'] }
}

resource storageConnStrSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'storage-connection-string'
  properties: { value: secrets['storage-connection-string'] }
}

resource openaiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'openai-api-key'
  properties: { value: secrets['openai-api-key'] }
}

resource appInsightsSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'appinsights-connection-string'
  properties: { value: secrets['appinsights-connection-string'] }
}
