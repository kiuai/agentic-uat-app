// ── Log Analytics + Application Insights ─────────────────────────────────────

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Log Analytics retention in days (30–730)')
param retentionDays int = 30

@description('Tags to apply to all resources')
param tags object = {}

// ── Log Analytics Workspace ───────────────────────────────────────────────────

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-law'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ── Application Insights ──────────────────────────────────────────────────────

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Log Analytics workspace resource ID')
output workspaceId string = law.id

@description('Log Analytics workspace customer ID (used for Container Apps environment)')
output workspaceCustomerId string = law.properties.customerId

@description('Log Analytics shared key')
@secure()
output workspaceKey string = law.listKeys().primarySharedKey

@description('Application Insights connection string')
@secure()
output connectionString string = appInsights.properties.ConnectionString

@description('Application Insights instrumentation key (legacy)')
output instrumentationKey string = appInsights.properties.InstrumentationKey
