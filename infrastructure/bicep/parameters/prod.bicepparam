using '../main.bicep'

// ── Production environment parameters ────────────────────────────────────────
// HA config: autoscale Cosmos, premium KV with purge protection, max OpenAI TPM.

param environment = 'prod'
param location = 'eastus'
param appName = 'kaats'
param imageTag = 'stable'  // CI/CD pins this to a specific SHA tag

param azureAdClientId = '00000000-0000-0000-0000-000000000000'

// SQL: always-on, max 8 vCores for burst
param sqlMinVCores = 2
param sqlMaxVCores = 8
param sqlAutoPauseDelay = -1  // Never auto-pause in prod

// Cosmos: autoscale (provisioned) for predictable latency
param cosmosServerless = false
param cosmosMaxThroughput = 4000

// Key Vault: premium HSM, purge protection, 90-day soft delete
param keyVaultSku = 'premium'
param keyVaultPurgeProtection = true
param keyVaultSoftDeleteDays = 90

// OpenAI: full capacity
param openAiGpt4oCapacity = 30
param openAiEmbeddingCapacity = 120

// Container scaling: HA min replicas
param apiMinReplicas = 2
param apiMaxReplicas = 10
param workerMinReplicas = 2
param workerMaxReplicas = 5

// Monitoring: 90-day retention
param logRetentionDays = 90
