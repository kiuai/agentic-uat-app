// ── Azure Service Bus ─────────────────────────────────────────────────────────
// Standard tier namespace with two queues:
//   - ai-generation  : triggers AI test script generation jobs
//   - crawler        : triggers web crawler jobs
//
// Note: Standard tier does not support private endpoints (Premium only).
// Public network access is enabled; traffic is secured via SAS/RBAC auth.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Managed identity principal ID to grant Azure Service Bus Data Owner')
param identityPrincipalId string

@description('Tags to apply to all resources')
param tags object = {}

// ── Namespace ─────────────────────────────────────────────────────────────────

resource ns 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${namePrefix}-bus'
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  tags: tags
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'  // Standard tier does not support private endpoints
    disableLocalAuth: false  // Keep SAS for connection-string auth pattern
  }
}

// ── Queues ────────────────────────────────────────────────────────────────────

resource aiQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: ns
  name: 'ai-generation'
  properties: {
    maxDeliveryCount: 5
    lockDuration: 'PT5M'  // Standard tier max = 5 min
    defaultMessageTimeToLive: 'P1D'
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
  }
}

resource crawlerQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: ns
  name: 'crawler'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'  // Standard tier max = 5 min
    defaultMessageTimeToLive: 'P1D'
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
  }
}

// ── RBAC: Managed Identity → Azure Service Bus Data Owner ────────────────────

var sbDataOwnerRoleId = '090c5cfd-751d-490a-894a-3ce6f1109419'

resource sbRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ns.id, identityPrincipalId, sbDataOwnerRoleId)
  scope: ns
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', sbDataOwnerRoleId)
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Shared Access Policy (for connection string) ──────────────────────────────

resource rootRule 'Microsoft.ServiceBus/namespaces/AuthorizationRules@2022-10-01-preview' existing = {
  parent: ns
  name: 'RootManageSharedAccessKey'
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Service Bus namespace resource ID')
output id string = ns.id

@description('Service Bus namespace name')
output name string = ns.name

@description('Service Bus connection string (primary)')
@secure()
output connectionString string = rootRule.listKeys().primaryConnectionString
