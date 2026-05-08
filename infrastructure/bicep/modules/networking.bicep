// ── Virtual Network + Private Endpoints ──────────────────────────────────────
// VNet (10.0.0.0/16) with subnets for Container Apps, private endpoints,
// and a delegated subnet for the Container Apps environment.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Tags to apply to all resources')
param tags object = {}

// ── VNet & Subnets ────────────────────────────────────────────────────────────

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: '${namePrefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        // Container Apps environment — needs /23 minimum
        name: 'container-apps'
        properties: {
          addressPrefix: '10.0.0.0/23'
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        // Private endpoints for PaaS services
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.0.4.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// ── Private DNS Zones ─────────────────────────────────────────────────────────

var privateDnsZones = [
  'privatelink${environment().suffixes.sqlServerHostname}'          // SQL
  'privatelink.documents.azure.com'                                  // Cosmos
  'privatelink.blob.${environment().suffixes.storage}'               // Storage
  'privatelink.vaultcore.azure.net'                                  // Key Vault
  'privatelink.servicebus.windows.net'                               // Service Bus
]

resource dnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = [for zone in privateDnsZones: {
  name: zone
  location: 'global'
  tags: tags
}]

resource dnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (zone, i) in privateDnsZones: {
  parent: dnsZone[i]
  name: '${namePrefix}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}]

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('VNet resource ID')
output vnetId string = vnet.id

@description('Container Apps subnet resource ID')
output containerAppsSubnetId string = vnet.properties.subnets[0].id

@description('Private endpoints subnet resource ID')
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id

@description('Private DNS zone resource IDs indexed by service')
output dnsZoneIds object = {
  sql: dnsZone[0].id
  cosmos: dnsZone[1].id
  storage: dnsZone[2].id
  keyVault: dnsZone[3].id
  serviceBus: dnsZone[4].id
}
