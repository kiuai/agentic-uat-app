// ── Azure Key Vault ───────────────────────────────────────────────────────────
// Standard SKU for dev/staging; Premium (HSM) + purge protection for prod.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('SKU: standard or premium')
@allowed(['standard', 'premium'])
param sku string = 'standard'

@description('Enable purge protection (required for prod)')
param enablePurgeProtection bool = false

@description('Soft-delete retention in days (7–90)')
param softDeleteRetentionDays int = 7

@description('Managed identity principal ID to grant secrets officer role')
param identityPrincipalId string

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

@description('Private endpoints subnet resource ID')
param privateEndpointsSubnetId string

@description('Private DNS zone resource ID for Key Vault')
param dnsZoneId string

@description('Tags to apply to all resources')
param tags object = {}

// ── Key Vault ─────────────────────────────────────────────────────────────────

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${namePrefix}-kv'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: sku
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: softDeleteRetentionDays
    enablePurgeProtection: enablePurgeProtection ? true : null
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Disabled'
  }
}

// ── RBAC: Managed Identity → Key Vault Secrets Officer ───────────────────────

var secretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

resource kvSecretsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, identityPrincipalId, secretsOfficerRoleId)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsOfficerRoleId)
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Private Endpoint ──────────────────────────────────────────────────────────

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${namePrefix}-kv-pe'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointsSubnetId }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-kv-plsc'
        properties: {
          privateLinkServiceId: kv.id
          groupIds: ['vault']
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

@description('Key Vault resource ID')
output id string = kv.id

@description('Key Vault name')
output name string = kv.name

@description('Key Vault URI')
output uri string = kv.properties.vaultUri
