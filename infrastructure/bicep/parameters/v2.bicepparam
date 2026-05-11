using '../main.bicep'

// ── KAATS v2 environment parameters ──────────────────────────────────────────
// Fresh environment: rg-kaatsv2-dev, all resources prefixed kaatsv2-dev.
// Container Apps Environment is external (public FQDNs).

param environment = 'dev'
param location = 'eastus'
param appName = 'kaatsv2'
param imageTag = 'latest'

// Azure AD app registration client ID
param azureAdClientId = '3b6d0f72-476a-4735-a592-afa40ce77aca'

// SQL: serverless, auto-pause after 60 min, 1–2 vCores
param sqlMinVCores = 1
param sqlMaxVCores = 2
param sqlAutoPauseDelay = 60

// Cosmos: serverless (cheapest dev option)
param cosmosServerless = true
param cosmosMaxThroughput = 4000

// Key Vault: standard, no purge protection, 7-day soft delete
param keyVaultSku = 'standard'
param keyVaultPurgeProtection = false
param keyVaultSoftDeleteDays = 7

// OpenAI: minimal capacity
param openAiGpt4oCapacity = 10
param openAiEmbeddingCapacity = 30

// Bootstrap: true on first deploy — no images in kaatsv2 ACR yet
param bootstrapMode = true

// Container scaling: always-on 1 replica
param apiMinReplicas = 1
param apiMaxReplicas = 3
param workerMinReplicas = 1
param workerMaxReplicas = 2

// Monitoring: 30-day retention
param logRetentionDays = 30
