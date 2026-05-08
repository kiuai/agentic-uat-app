// ── Container Apps: api, worker, frontend ────────────────────────────────────
// All three apps share the same environment and managed identity.
// Secrets are pulled from Key Vault via managed identity references.

@description('Azure region')
param location string

@description('Resource name prefix')
param namePrefix string

@description('Container Apps Environment resource ID')
param environmentId string

@description('User-assigned managed identity resource ID')
param identityId string

@description('User-assigned managed identity client ID')
param identityClientId string

@description('Azure Container Registry login server (e.g. myacr.azurecr.io)')
param acrLoginServer string

@description('Image tag to deploy')
param imageTag string = 'latest'

@description('Key Vault URI (e.g. https://myapp-kv.vault.azure.net/)')
param keyVaultUri string

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

@description('Azure AD client ID (app registration) for MSAL')
param azureClientId string

@description('Minimum replicas for API container app')
param apiMinReplicas int = 1

@description('Maximum replicas for API container app')
param apiMaxReplicas int = 10

@description('Minimum replicas for worker container app')
param workerMinReplicas int = 1

@description('Maximum replicas for worker container app')
param workerMaxReplicas int = 5

@description('Tags to apply to all resources')
param tags object = {}

// ── Shared environment variables (non-secret) ─────────────────────────────────

var sharedEnv = [
  { name: 'AZURE_CLIENT_ID', value: identityClientId }
  { name: 'AZURE_TENANT_ID', value: tenantId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
]

// ── API Container App ─────────────────────────────────────────────────────────

resource api 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: '${namePrefix}-api'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}secrets/database-url'
          identity: identityId
        }
        {
          name: 'cosmos-endpoint'
          keyVaultUrl: '${keyVaultUri}secrets/cosmos-endpoint'
          identity: identityId
        }
        {
          name: 'cosmos-key'
          keyVaultUrl: '${keyVaultUri}secrets/cosmos-key'
          identity: identityId
        }
        {
          name: 'service-bus-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/service-bus-connection-string'
          identity: identityId
        }
        {
          name: 'storage-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/storage-connection-string'
          identity: identityId
        }
        {
          name: 'openai-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/openai-api-key'
          identity: identityId
        }
        {
          name: 'appinsights-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/appinsights-connection-string'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/kaats-api:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: union(sharedEnv, [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'COSMOS_ENDPOINT', secretRef: 'cosmos-endpoint' }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'SERVICE_BUS_CONNECTION_STRING', secretRef: 'service-bus-connection-string' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-connection-string' }
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'AZURE_AD_TENANT_ID', value: tenantId }
            { name: 'AZURE_AD_CLIENT_ID', value: azureClientId }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: apiMaxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ── Worker Container App ──────────────────────────────────────────────────────

resource worker 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: '${namePrefix}-worker'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      // No ingress — worker only consumes Service Bus
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: '${keyVaultUri}secrets/database-url'
          identity: identityId
        }
        {
          name: 'cosmos-endpoint'
          keyVaultUrl: '${keyVaultUri}secrets/cosmos-endpoint'
          identity: identityId
        }
        {
          name: 'cosmos-key'
          keyVaultUrl: '${keyVaultUri}secrets/cosmos-key'
          identity: identityId
        }
        {
          name: 'service-bus-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/service-bus-connection-string'
          identity: identityId
        }
        {
          name: 'storage-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/storage-connection-string'
          identity: identityId
        }
        {
          name: 'openai-api-key'
          keyVaultUrl: '${keyVaultUri}secrets/openai-api-key'
          identity: identityId
        }
        {
          name: 'appinsights-connection-string'
          keyVaultUrl: '${keyVaultUri}secrets/appinsights-connection-string'
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/kaats-worker:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: union(sharedEnv, [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'COSMOS_ENDPOINT', secretRef: 'cosmos-endpoint' }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'SERVICE_BUS_CONNECTION_STRING', secretRef: 'service-bus-connection-string' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-connection-string' }
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
          ])
        }
      ]
      scale: {
        minReplicas: workerMinReplicas
        maxReplicas: workerMaxReplicas
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              metadata: {
                queueName: 'ai-generation'
                messageCount: '5'
              }
              auth: [
                {
                  secretRef: 'service-bus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
            }
          }
        ]
      }
    }
  }
}

// ── Frontend Container App ────────────────────────────────────────────────────

resource frontend 'Microsoft.App/containerApps@2023-11-02-preview' = {
  name: '${namePrefix}-frontend'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acrLoginServer}/kaats-frontend:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'VITE_AZURE_CLIENT_ID', value: azureClientId }
            { name: 'VITE_AZURE_TENANT_ID', value: tenantId }
            { name: 'VITE_API_BASE_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: { concurrentRequests: '100' }
            }
          }
        ]
      }
    }
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('API app FQDN')
output apiFqdn string = api.properties.configuration.ingress.fqdn

@description('Frontend app FQDN')
output frontendFqdn string = frontend.properties.configuration.ingress.fqdn

@description('API container app resource ID')
output apiId string = api.id

@description('Worker container app resource ID')
output workerId string = worker.id

@description('Frontend container app resource ID')
output frontendId string = frontend.id
