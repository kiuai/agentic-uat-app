// ── KAATS — Main Bicep Deployment ─────────────────────────────────────────────
// Subscription-scoped. Creates resource group then deploys all modules.
// Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infrastructure/bicep/main.bicep \
//     --parameters infrastructure/bicep/parameters/dev.bicepparam

targetScope = 'subscription'

// ── Parameters ────────────────────────────────────────────────────────────────

@description('Environment name: dev, staging, or prod')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Azure region for all resources')
param location string = 'eastus'

@description('Short app name used in resource naming')
param appName string = 'kaats'

@description('Image tag to deploy across all container apps')
param imageTag string = 'latest'

@description('Bootstrap mode: use placeholder image on first deploy before ACR images exist')
param bootstrapMode bool = false

@description('Azure AD Application (client) ID for MSAL authentication')
param azureAdClientId string

// ── SQL parameters ────────────────────────────────────────────────────────────
@description('Min vCores for serverless SQL')
param sqlMinVCores int = 1

@description('Max vCores for serverless SQL')
param sqlMaxVCores int = 4

@description('Auto-pause delay in minutes (-1 = disabled)')
param sqlAutoPauseDelay int = 60

// ── Cosmos DB parameters ──────────────────────────────────────────────────────
@description('Use Cosmos DB serverless capacity (dev/staging=true, prod=false)')
param cosmosServerless bool = true

@description('Max autoscale RU/s when serverless=false')
param cosmosMaxThroughput int = 4000

// ── Key Vault parameters ──────────────────────────────────────────────────────
@description('Key Vault SKU: standard or premium')
@allowed(['standard', 'premium'])
param keyVaultSku string = 'standard'

@description('Enable Key Vault purge protection (prod only)')
param keyVaultPurgeProtection bool = false

@description('Soft delete retention in days')
param keyVaultSoftDeleteDays int = 7

// ── OpenAI parameters ─────────────────────────────────────────────────────────
@description('TPM capacity for GPT-4o deployment')
param openAiGpt4oCapacity int = 30

@description('TPM capacity for embedding model')
param openAiEmbeddingCapacity int = 120

// ── Scaling parameters ────────────────────────────────────────────────────────
@description('API container app min replicas')
param apiMinReplicas int = 1

@description('API container app max replicas')
param apiMaxReplicas int = 10

@description('Worker container app min replicas')
param workerMinReplicas int = 1

@description('Worker container app max replicas')
param workerMaxReplicas int = 5

// ── Monitoring parameters ─────────────────────────────────────────────────────
@description('Log Analytics retention in days')
param logRetentionDays int = 30

// ── Derived naming ────────────────────────────────────────────────────────────

var namePrefix = '${appName}-${environment}'
var rgName = 'rg-${namePrefix}'

var tags = {
  application: appName
  environment: environment
  managedBy: 'bicep'
}

// ── Resource Group ────────────────────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: rgName
  location: location
  tags: tags
}

// ── Azure Container Registry ──────────────────────────────────────────────────
// Deployed at RG scope inline (simple enough to not need its own module)

module acrDeploy 'modules/acr.bicep' = {
  name: 'acr'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

// ── Identity (foundation — everything else depends on principalId) ────────────

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

// ── Networking ────────────────────────────────────────────────────────────────

module networking 'modules/networking.bicep' = {
  name: 'networking'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

// ── Monitoring ────────────────────────────────────────────────────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    retentionDays: logRetentionDays
    tags: tags
  }
}

// ── Data layer ────────────────────────────────────────────────────────────────

module sql 'modules/sql-database.bicep' = {
  name: 'sql'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    adminObjectId: identity.outputs.principalId
    adminLoginName: identity.outputs.name
    minVCores: sqlMinVCores
    maxVCores: sqlMaxVCores
    autoPauseDelay: sqlAutoPauseDelay
    privateEndpointsSubnetId: networking.outputs.privateEndpointsSubnetId
    dnsZoneId: networking.outputs.dnsZoneIds.sql
    tags: tags
  }
}

module cosmos 'modules/cosmos-db.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    serverless: cosmosServerless
    maxAutoscaleThroughput: cosmosMaxThroughput
    identityPrincipalId: identity.outputs.principalId
    privateEndpointsSubnetId: networking.outputs.privateEndpointsSubnetId
    dnsZoneId: networking.outputs.dnsZoneIds.cosmos
    tags: tags
  }
}

module serviceBus 'modules/service-bus.bicep' = {
  name: 'serviceBus'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    identityPrincipalId: identity.outputs.principalId
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    identityPrincipalId: identity.outputs.principalId
    privateEndpointsSubnetId: networking.outputs.privateEndpointsSubnetId
    dnsZoneId: networking.outputs.dnsZoneIds.storage
    tags: tags
  }
}

module openai 'modules/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    identityPrincipalId: identity.outputs.principalId
    gpt4oCapacity: openAiGpt4oCapacity
    embeddingCapacity: openAiEmbeddingCapacity
    tags: tags
  }
}

// ── Key Vault (depends on all data layers — stores their secrets) ─────────────

module keyVault 'modules/key-vault.bicep' = {
  name: 'keyVault'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    sku: keyVaultSku
    enablePurgeProtection: keyVaultPurgeProtection
    softDeleteRetentionDays: keyVaultSoftDeleteDays
    identityPrincipalId: identity.outputs.principalId
    privateEndpointsSubnetId: networking.outputs.privateEndpointsSubnetId
    dnsZoneId: networking.outputs.dnsZoneIds.keyVault
    tags: tags
  }
}

// ── Store secrets in Key Vault ────────────────────────────────────────────────

module kvSecrets 'modules/kv-secrets.bicep' = {
  name: 'kvSecrets'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.name
    secrets: {
      'database-url': sql.outputs.connectionString
      'cosmos-endpoint': cosmos.outputs.endpoint
      'cosmos-key': cosmos.outputs.primaryKey
      'service-bus-connection-string': serviceBus.outputs.connectionString
      'storage-connection-string': storage.outputs.connectionString
      'openai-api-key': openai.outputs.apiKey
      'appinsights-connection-string': monitoring.outputs.connectionString
    }
  }
}

// ── ACR: grant pull to managed identity ──────────────────────────────────────

module acrPull 'modules/acr-rbac.bicep' = {
  name: 'acrPull'
  scope: rg
  params: {
    acrName: acrDeploy.outputs.name
    identityPrincipalId: identity.outputs.principalId
  }
}

// ── Container Apps Environment ────────────────────────────────────────────────

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'containerAppsEnv'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    subnetId: networking.outputs.containerAppsSubnetId
    logAnalyticsWorkspaceCustomerId: monitoring.outputs.workspaceCustomerId
    logAnalyticsWorkspaceKey: monitoring.outputs.workspaceKey
    tags: tags
  }
}

// ── Container Apps (api, worker, frontend) ────────────────────────────────────

module containerApps 'modules/container-apps.bicep' = {
  name: 'containerApps'
  scope: rg
  dependsOn: [kvSecrets]  // Ensure secrets exist before apps read them
  params: {
    location: location
    namePrefix: namePrefix
    environmentId: containerAppsEnv.outputs.id
    identityId: identity.outputs.identityId
    identityClientId: identity.outputs.clientId
    acrLoginServer: acrDeploy.outputs.loginServer
    imageTag: imageTag
    keyVaultUri: keyVault.outputs.uri
    tenantId: subscription().tenantId
    azureClientId: azureAdClientId
    apiMinReplicas: apiMinReplicas
    apiMaxReplicas: apiMaxReplicas
    workerMinReplicas: workerMinReplicas
    workerMaxReplicas: workerMaxReplicas
    bootstrapMode: bootstrapMode
    tags: tags
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Resource group name')
output resourceGroupName string = rg.name

@description('API FQDN')
output apiFqdn string = containerApps.outputs.apiFqdn

@description('Frontend FQDN')
output frontendFqdn string = containerApps.outputs.frontendFqdn

@description('Azure Container Registry login server')
output acrLoginServer string = acrDeploy.outputs.loginServer

@description('Managed identity client ID (set as AZURE_CLIENT_ID in app config)')
output managedIdentityClientId string = identity.outputs.clientId
