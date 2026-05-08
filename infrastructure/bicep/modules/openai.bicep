// ── Azure OpenAI ──────────────────────────────────────────────────────────────
// Used for AI test script generation. Deploys gpt-4o (latest) for generation
// and text-embedding-3-small for semantic search.

@description('Azure region (must support Azure OpenAI)')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Managed identity principal ID to grant Cognitive Services OpenAI User')
param identityPrincipalId string

@description('TPM capacity for gpt-4o deployment (thousands of tokens per minute)')
param gpt4oCapacity int = 30

@description('TPM capacity for embedding model')
param embeddingCapacity int = 120

@description('Tags to apply to all resources')
param tags object = {}

// ── OpenAI Account ────────────────────────────────────────────────────────────

resource openai 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: '${namePrefix}-oai'
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  tags: tags
  properties: {
    customSubDomainName: '${namePrefix}-oai'
    publicNetworkAccess: 'Enabled'  // Private endpoint for OpenAI only in select regions
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false
  }
}

// ── Model Deployments ─────────────────────────────────────────────────────────

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openai
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: gpt4oCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openai
  name: 'text-embedding-3-small'
  dependsOn: [gpt4oDeployment]  // deployments must be sequential
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// ── RBAC: Managed Identity → Cognitive Services OpenAI User ──────────────────

var openaiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openaiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openai.id, identityPrincipalId, openaiUserRoleId)
  scope: openai
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openaiUserRoleId)
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('OpenAI account resource ID')
output id string = openai.id

@description('OpenAI endpoint')
output endpoint string = openai.properties.endpoint

@description('OpenAI API key')
@secure()
output apiKey string = openai.listKeys().key1

@description('GPT-4o deployment name')
output gpt4oDeploymentName string = gpt4oDeployment.name

@description('Embedding deployment name')
output embeddingDeploymentName string = embeddingDeployment.name
