// ── Azure Container Registry ──────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Tags to apply to all resources')
param tags object = {}

var acrName = take(replace(namePrefix, '-', ''), 50)

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: '${acrName}acr'
  location: location
  sku: { name: 'Standard' }
  tags: tags
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'  // Required for Container Apps to pull images
    zoneRedundancy: 'Disabled'
  }
}

output id string = acr.id
output name string = acr.name
output loginServer string = acr.properties.loginServer
