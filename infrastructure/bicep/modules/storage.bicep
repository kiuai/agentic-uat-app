// ── Azure Storage Account ─────────────────────────────────────────────────────
// Stores test evidence files (screenshots, PDFs). LRS for all environments.

@description('Azure region')
param location string

@description('Resource name prefix (storage name must be 3–24 chars, lowercase alphanumeric)')
param namePrefix string

@description('Managed identity principal ID to grant Storage Blob Data Contributor')
param identityPrincipalId string

@description('Private endpoints subnet resource ID')
param privateEndpointsSubnetId string

@description('Private DNS zone resource ID for Blob storage')
param dnsZoneId string

@description('Tags to apply to all resources')
param tags object = {}

// Storage name: strip hyphens, truncate to 24 chars
var storageName = take(replace(namePrefix, '-', ''), 20)

// ── Storage Account ───────────────────────────────────────────────────────────

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${storageName}sa'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  tags: tags
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Disabled'
  }
}

// ── Blob Service & Evidence Container ────────────────────────────────────────

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: sa
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 30 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource evidenceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'evidence'
  properties: {
    publicAccess: 'None'
  }
}

// ── RBAC: Managed Identity → Storage Blob Data Contributor ───────────────────

var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, identityPrincipalId, blobContributorRoleId)
  scope: sa
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Private Endpoint ──────────────────────────────────────────────────────────

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${namePrefix}-sa-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointsSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-sa-plsc'
        properties: {
          privateLinkServiceId: sa.id
          groupIds: ['blob']
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

@description('Storage account resource ID')
output id string = sa.id

@description('Storage account name')
output name string = sa.name

@description('Blob service primary endpoint')
output blobEndpoint string = sa.properties.primaryEndpoints.blob

@description('Storage connection string (for app config / Key Vault secret)')
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${sa.name};AccountKey=${sa.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
