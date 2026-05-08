// ── Azure Cosmos DB (SQL API) ─────────────────────────────────────────────────
// Serverless for dev/staging; autoscale (4000 RU/s) for prod.
// Four containers: test_artifacts, audit_log, ai_generation_log, crawler_results.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Use serverless capacity mode (dev/staging); false = autoscale (prod)')
param serverless bool = true

@description('Max autoscale throughput in RU/s when serverless=false')
param maxAutoscaleThroughput int = 4000

@description('Managed identity principal ID to grant Cosmos DB Built-in Data Contributor')
param identityPrincipalId string

@description('Private endpoints subnet resource ID')
param privateEndpointsSubnetId string

@description('Private DNS zone resource ID for Cosmos DB')
param dnsZoneId string

@description('Tags to apply to all resources')
param tags object = {}

// ── Account ───────────────────────────────────────────────────────────────────

resource account 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: '${namePrefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: serverless ? [{ name: 'EnableServerless' }] : []
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    publicNetworkAccess: 'Disabled'
    networkAclBypass: 'AzureServices'
    minimalTlsVersion: 'Tls12'
    disableLocalAuth: false  // Keep key auth for connection string
  }
}

// ── Database ──────────────────────────────────────────────────────────────────

resource db 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: account
  name: 'kaats'
  properties: {
    resource: { id: 'kaats' }
  }
}

// ── Containers ────────────────────────────────────────────────────────────────

var containers = [
  {
    name: 'test_artifacts'
    partitionKey: '/project_id'
    defaultTtl: -1  // no expiry
  }
  {
    name: 'audit_log'
    partitionKey: '/tenant_id'
    defaultTtl: 7776000  // 90 days
  }
  {
    name: 'ai_generation_log'
    partitionKey: '/project_id'
    defaultTtl: 2592000  // 30 days
  }
  {
    name: 'crawler_results'
    partitionKey: '/project_id'
    defaultTtl: 604800  // 7 days
  }
]

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = [for c in containers: {
  parent: db
  name: c.name
  properties: {
    resource: {
      id: c.name
      partitionKey: {
        paths: [c.partitionKey]
        kind: 'Hash'
        version: 2
      }
      defaultTtl: c.defaultTtl
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [{ path: '/*' }]
        excludedPaths: [{ path: '/"_etag"/?' }]
      }
    }
    options: serverless ? {} : {
      autoscaleSettings: { maxThroughput: maxAutoscaleThroughput }
    }
  }
}]

// ── RBAC: Managed Identity → Cosmos DB Built-in Data Contributor ─────────────
// Built-in Data Contributor role: 00000000-0000-0000-0000-000000000002

resource cosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: account
  name: guid(account.id, identityPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${account.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identityPrincipalId
    scope: account.id
  }
}

// ── Private Endpoint ──────────────────────────────────────────────────────────

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${namePrefix}-cosmos-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointsSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-cosmos-plsc'
        properties: {
          privateLinkServiceId: account.id
          groupIds: ['Sql']
        }
      }
    ]
  }

  resource dnsGroup 'privateDnsZoneGroups' = {
    name: 'default'
    properties: {
      privateDnsZoneConfigs: [
        {
          name: 'config'
          properties: { privateDnsZoneId: dnsZoneId }
        }
      ]
    }
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Cosmos DB account resource ID')
output id string = account.id

@description('Cosmos DB endpoint')
output endpoint string = account.properties.documentEndpoint

@description('Cosmos DB primary key')
@secure()
output primaryKey string = account.listKeys().primaryMasterKey
