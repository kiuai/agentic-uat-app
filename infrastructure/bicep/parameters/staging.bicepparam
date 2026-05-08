using '../main.bicep'

// ── Staging environment parameters ───────────────────────────────────────────
// Production-like config but smaller scale. No auto-pause.

param environment = 'staging'
param location = 'eastus'
param appName = 'kaats'
param imageTag = 'latest'

param azureAdClientId = '00000000-0000-0000-0000-000000000000'

// SQL: no auto-pause (staging needs to be always available for QA)
param sqlMinVCores = 1
param sqlMaxVCores = 4
param sqlAutoPauseDelay = -1

// Cosmos: serverless (still cost-effective at staging load)
param cosmosServerless = true
param cosmosMaxThroughput = 4000

// Key Vault: standard, 14-day soft delete
param keyVaultSku = 'standard'
param keyVaultPurgeProtection = false
param keyVaultSoftDeleteDays = 14

// OpenAI: moderate capacity
param openAiGpt4oCapacity = 20
param openAiEmbeddingCapacity = 60

// Container scaling
param apiMinReplicas = 1
param apiMaxReplicas = 5
param workerMinReplicas = 1
param workerMaxReplicas = 3

// Monitoring: 60-day retention
param logRetentionDays = 60
