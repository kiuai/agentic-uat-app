// ── Container Apps Environment ────────────────────────────────────────────────
// VNet-integrated environment shared by all three apps (api, worker, frontend).

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Container Apps subnet resource ID (requires /23 minimum, delegated to Microsoft.App/environments)')
param subnetId string

@description('Log Analytics workspace customer ID')
param logAnalyticsWorkspaceCustomerId string

@description('Log Analytics workspace shared key')
@secure()
param logAnalyticsWorkspaceKey string

@description('Tags to apply to all resources')
param tags object = {}

// ── Environment ───────────────────────────────────────────────────────────────

resource env 'Microsoft.App/managedEnvironments@2023-11-02-preview' = {
  name: '${namePrefix}-cae'
  location: location
  tags: tags
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: subnetId
      internal: false  // External load balancer — apps with external ingress get public FQDNs
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceCustomerId
        sharedKey: logAnalyticsWorkspaceKey
      }
    }
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Container Apps Environment resource ID')
output id string = env.id

@description('Container Apps Environment name')
output name string = env.name

@description('Default domain for the environment')
output defaultDomain string = env.properties.defaultDomain

@description('Static IP of the environment (for DNS/firewall rules)')
output staticIp string = env.properties.staticIp
