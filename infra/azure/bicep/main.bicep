@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Prefix used for resource names')
param namePrefix string

@description('Key Vault name (must be globally unique, 3-24 chars, alphanumeric and hyphens)')
param keyVaultName string = '${namePrefix}-kv'

@description('Container image for API')
param apiImage string

@description('Container image for worker')
param workerImage string

@description('Postgres admin username')
param pgAdmin string

@secure()
@description('Postgres admin password')
param pgPassword string

@description('Postgres database name')
param pgDatabase string = 'uat'

@description('Postgres SKU name (e.g., Standard_D2s_v3)')
param pgSkuName string = 'Standard_D2s_v3'

@description('Postgres location (use a supported region for your subscription)')
param pgLocation string = location

@description('Redis SKU capacity (C0=0, C1=1, C2=2, C3=3, C4=4, C5=5)')
param redisCapacity int = 1

@description('VNet address space')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Subnet for Container Apps environment (min /27)')
param acaSubnetPrefix string = '10.0.1.0/24'

@description('Subnet for private endpoints')
param peSubnetPrefix string = '10.0.2.0/24'

@description('Azure Files share name for evidence')
param evidenceShareName string = 'evidence'

@secure()
@description('DATABASE_URL value')
param databaseUrl string

@secure()
@description('REDIS_URL value')
param redisUrl string

@secure()
@description('CELERY_BROKER_URL value')
param celeryBrokerUrl string

@secure()
@description('CELERY_RESULT_BACKEND value')
param celeryResultBackend string

@secure()
@description('APP_SECRET_KEY value')
param appSecretKey string

@secure()
@description('AZURE_OPENAI_ENDPOINT value')
param azureOpenaiEndpoint string

@secure()
@description('AZURE_OPENAI_API_KEY value')
param azureOpenaiApiKey string

@secure()
@description('AZURE_OPENAI_API_VERSION value')
param azureOpenaiApiVersion string

@secure()
@description('AZURE_OPENAI_DEPLOYMENT value')
param azureOpenaiDeployment string

var acrName = '${namePrefix}acr'
var pgServerName = '${namePrefix}-pg'
var redisName = '${namePrefix}-redis'
var storageName = toLower(replace('${namePrefix}storage', '-', ''))
var logAnalyticsName = '${namePrefix}-logs'
var envName = '${namePrefix}-aca'
var apiAppName = '${namePrefix}-api'
var workerAppName = '${namePrefix}-worker'
var vnetName = '${namePrefix}-vnet'
var acaSubnetName = '${namePrefix}-aca-subnet'
var peSubnetName = '${namePrefix}-pe-subnet'

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
  }
}

resource acaSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  name: '${vnet.name}/${acaSubnetName}'
  properties: {
    addressPrefix: acaSubnetPrefix
    delegations: [
      {
        name: 'aca-delegation'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  name: '${vnet.name}/${peSubnetName}'
  properties: {
    addressPrefix: peSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Standard' }
  properties: {
    adminUserEnabled: false
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: listKeys(logAnalytics.id, logAnalytics.apiVersion).primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: acaSubnet.id
      internal: false
    }
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: pgServerName
  location: pgLocation
  sku: {
    name: pgSkuName
    tier: 'GeneralPurpose'
  }
  properties: {
    administratorLogin: pgAdmin
    administratorLoginPassword: pgPassword
    version: '16'
    storage: { storageSizeGB: 128 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: {
      publicNetworkAccess: 'Disabled'
    }
  }
}

resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  name: '${postgres.name}/${pgDatabase}'
  properties: {}
}

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  sku: {
    name: 'Standard'
    family: 'C'
    capacity: redisCapacity
  }
  properties: {
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisVersion: '6'
    publicNetworkAccess: 'Disabled'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2025-06-01' = {
  parent: storage
  name: 'default'
}

resource evidenceShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2025-06-01' = {
  parent: fileService
  name: evidenceShareName
  properties: {
    shareQuota: 1024
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
  }
}

resource kvDatabaseUrl 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/DATABASE-URL'
  properties: {
    value: databaseUrl
  }
}

resource kvRedisUrl 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/REDIS-URL'
  properties: {
    value: redisUrl
  }
}

resource kvCeleryBrokerUrl 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/CELERY-BROKER-URL'
  properties: {
    value: celeryBrokerUrl
  }
}

resource kvCeleryResultBackend 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/CELERY-RESULT-BACKEND'
  properties: {
    value: celeryResultBackend
  }
}

resource kvAppSecretKey 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/APP-SECRET-KEY'
  properties: {
    value: appSecretKey
  }
}

resource kvAzureEndpoint 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/AZURE-OPENAI-ENDPOINT'
  properties: {
    value: azureOpenaiEndpoint
  }
}

resource kvAzureApiKey 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/AZURE-OPENAI-API-KEY'
  properties: {
    value: azureOpenaiApiKey
  }
}

resource kvAzureApiVersion 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/AZURE-OPENAI-API-VERSION'
  properties: {
    value: azureOpenaiApiVersion
  }
}

resource kvAzureDeployment 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  name: '${keyVault.name}/AZURE-OPENAI-DEPLOYMENT'
  properties: {
    value: azureOpenaiDeployment
  }
}

// Private DNS zones
resource dnsPostgres 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

resource dnsRedis 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.redis.cache.windows.net'
  location: 'global'
}

resource dnsKeyVault 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource dnsFile 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.file.core.windows.net'
  location: 'global'
}

resource dnsPostgresLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${dnsPostgres.name}/${namePrefix}-vnet'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsRedisLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${dnsRedis.name}/${namePrefix}-vnet'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsKeyVaultLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${dnsKeyVault.name}/${namePrefix}-vnet'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsFileLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  name: '${dnsFile.name}/${namePrefix}-vnet'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// Private endpoints
resource pePostgres 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${namePrefix}-pe-postgres'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'postgres-connection'
        properties: {
          privateLinkServiceId: postgres.id
          groupIds: [ 'postgresqlServer' ]
        }
      }
    ]
  }
}

resource pePostgresDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: '${pePostgres.name}/postgres-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'postgres'
        properties: { privateDnsZoneId: dnsPostgres.id }
      }
    ]
  }
}

resource peRedis 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${namePrefix}-pe-redis'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'redis-connection'
        properties: {
          privateLinkServiceId: redis.id
          groupIds: [ 'redisCache' ]
        }
      }
    ]
  }
}

resource peRedisDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: '${peRedis.name}/redis-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'redis'
        properties: { privateDnsZoneId: dnsRedis.id }
      }
    ]
  }
}

resource peKeyVault 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${namePrefix}-pe-kv'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'kv-connection'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [ 'vault' ]
        }
      }
    ]
  }
}

resource peKeyVaultDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: '${peKeyVault.name}/kv-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'kv'
        properties: { privateDnsZoneId: dnsKeyVault.id }
      }
    ]
  }
}

resource peFile 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: '${namePrefix}-pe-file'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'file-connection'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [ 'file' ]
        }
      }
    ]
  }
}

resource peFileDns 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  name: '${peFile.name}/file-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'file'
        properties: { privateDnsZoneId: dnsFile.id }
      }
    ]
  }
}

// ACA environment storage (Azure Files)
var storageKey = listKeys(storage.id, storage.apiVersion).keys[0].value
var envStorageName = '${namePrefix}-evidence'
resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: '${acaEnv.name}/${envStorageName}'
  properties: {
    azureFile: {
      accountName: storage.name
      shareName: evidenceShareName
      accountKey: storageKey
      accessMode: 'ReadWrite'
    }
  }
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'System'
        }
      ]
      secrets: [
        { name: 'database-url', keyVaultUrl: reference(kvDatabaseUrl.id, kvDatabaseUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'redis-url', keyVaultUrl: reference(kvRedisUrl.id, kvRedisUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'celery-broker', keyVaultUrl: reference(kvCeleryBrokerUrl.id, kvCeleryBrokerUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'celery-backend', keyVaultUrl: reference(kvCeleryResultBackend.id, kvCeleryResultBackend.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'app-secret', keyVaultUrl: reference(kvAppSecretKey.id, kvAppSecretKey.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-endpoint', keyVaultUrl: reference(kvAzureEndpoint.id, kvAzureEndpoint.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-api-key', keyVaultUrl: reference(kvAzureApiKey.id, kvAzureApiKey.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-api-version', keyVaultUrl: reference(kvAzureApiVersion.id, kvAzureApiVersion.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-deployment', keyVaultUrl: reference(kvAzureDeployment.id, kvAzureDeployment.apiVersion).properties.secretUriWithVersion, identity: 'System' }
      ]
    }
    template: {
      volumes: [
        {
          name: 'evidence'
          storageType: 'AzureFile'
          storageName: envStorageName
        }
      ]
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker' }
            { name: 'CELERY_RESULT_BACKEND', secretRef: 'celery-backend' }
            { name: 'APP_SECRET_KEY', secretRef: 'app-secret' }
            { name: 'EVIDENCE_DIR', value: '/data/evidence' }
            { name: 'LLM_PROVIDER', value: 'azure' }
            { name: 'AZURE_OPENAI_ENDPOINT', secretRef: 'azure-endpoint' }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-api-key' }
            { name: 'AZURE_OPENAI_API_VERSION', secretRef: 'azure-api-version' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', secretRef: 'azure-deployment' }
          ]
          volumeMounts: [
            { volumeName: 'evidence', mountPath: '/data/evidence' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: workerAppName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: acaEnv.id
    configuration: {
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'System'
        }
      ]
      secrets: [
        { name: 'database-url', keyVaultUrl: reference(kvDatabaseUrl.id, kvDatabaseUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'redis-url', keyVaultUrl: reference(kvRedisUrl.id, kvRedisUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'celery-broker', keyVaultUrl: reference(kvCeleryBrokerUrl.id, kvCeleryBrokerUrl.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'celery-backend', keyVaultUrl: reference(kvCeleryResultBackend.id, kvCeleryResultBackend.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'app-secret', keyVaultUrl: reference(kvAppSecretKey.id, kvAppSecretKey.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-endpoint', keyVaultUrl: reference(kvAzureEndpoint.id, kvAzureEndpoint.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-api-key', keyVaultUrl: reference(kvAzureApiKey.id, kvAzureApiKey.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-api-version', keyVaultUrl: reference(kvAzureApiVersion.id, kvAzureApiVersion.apiVersion).properties.secretUriWithVersion, identity: 'System' }
        { name: 'azure-deployment', keyVaultUrl: reference(kvAzureDeployment.id, kvAzureDeployment.apiVersion).properties.secretUriWithVersion, identity: 'System' }
      ]
    }
    template: {
      volumes: [
        {
          name: 'evidence'
          storageType: 'AzureFile'
          storageName: envStorageName
        }
      ]
      containers: [
        {
          name: 'worker'
          image: workerImage
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker' }
            { name: 'CELERY_RESULT_BACKEND', secretRef: 'celery-backend' }
            { name: 'APP_SECRET_KEY', secretRef: 'app-secret' }
            { name: 'EVIDENCE_DIR', value: '/data/evidence' }
            { name: 'LLM_PROVIDER', value: 'azure' }
            { name: 'AZURE_OPENAI_ENDPOINT', secretRef: 'azure-endpoint' }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-api-key' }
            { name: 'AZURE_OPENAI_API_VERSION', secretRef: 'azure-api-version' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', secretRef: 'azure-deployment' }
          ]
          volumeMounts: [
            { volumeName: 'evidence', mountPath: '/data/evidence' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, apiApp.name, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, workerApp.name, 'acrpull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: workerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource apiKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, apiApp.name, 'kv-secrets-user')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource workerKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workerApp.name, 'kv-secrets-user')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: workerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output apiUrl string = apiApp.properties.configuration.ingress.fqdn
output postgresHost string = '${postgres.name}.postgres.database.azure.com'
output redisHost string = '${redis.name}.redis.cache.windows.net'
output keyVaultName string = keyVault.name
output storageAccount string = storage.name
