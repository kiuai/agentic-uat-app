// ── Azure SQL Database ────────────────────────────────────────────────────────
// General Purpose serverless (dev: auto-pause after 60 min; prod: always-on).
// Authentication: AAD-only, managed identity is AAD admin.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('SQL admin AAD object ID (managed identity principal ID)')
param adminObjectId string

@description('SQL admin AAD login name (managed identity name)')
param adminLoginName string

@description('vCores for serverless (min/max)')
param minVCores int = 1
param maxVCores int = 4

@description('Auto-pause delay in minutes (-1 = disabled, 60 = 1 hour)')
param autoPauseDelay int = 60

@description('Private endpoints subnet resource ID')
param privateEndpointsSubnetId string

@description('Private DNS zone resource ID for SQL')
param dnsZoneId string

@description('Tags to apply to all resources')
param tags object = {}

// ── Server ────────────────────────────────────────────────────────────────────

resource server 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: '${namePrefix}-sql'
  location: location
  tags: tags
  properties: {
    // AAD-only auth — no SQL logins
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: adminLoginName
      sid: adminObjectId
      tenantId: subscription().tenantId
      principalType: 'Application'
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
  }
}

// ── Database ──────────────────────────────────────────────────────────────────

resource database 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: server
  name: 'kaats'
  location: location
  tags: tags
  sku: {
    name: 'GP_S_Gen5'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: maxVCores
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 34359738368  // 32 GB
    autoPauseDelay: autoPauseDelay
    minCapacity: json(string(minVCores))
    zoneRedundant: false
    licenseType: 'LicenseIncluded'
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: 'Local'
  }
}

// ── Private Endpoint ──────────────────────────────────────────────────────────

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${namePrefix}-sql-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointsSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-sql-plsc'
        properties: {
          privateLinkServiceId: server.id
          groupIds: ['sqlServer']
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

@description('SQL server resource ID')
output serverId string = server.id

@description('SQL server FQDN')
output serverFqdn string = server.properties.fullyQualifiedDomainName

@description('Database resource ID')
output databaseId string = database.id

@description('Database name')
output databaseName string = database.name

@description('asyncpg connection string (uses AAD token, no password)')
output connectionString string = 'mssql+pyodbc://${server.properties.fullyQualifiedDomainName}/kaats?driver=ODBC+Driver+18+for+SQL+Server&authentication=ActiveDirectoryMsi'
