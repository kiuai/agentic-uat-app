# Azure Bicep Deployment (Managed Identity + Key Vault)

This deployment uses **managed identities** for ACR pulls and **Key Vault secret references** for Container Apps configuration.

## 1) Prereqs
- Azure CLI installed and logged in
- Contributor access to your subscription

## 2) Create a resource group

```bash
az group create --name uat-prod-rg --location eastus
```

## 3) Create ACR and push image

```bash
az acr create --resource-group uat-prod-rg --name uatprodacr12345 --sku Standard
az acr build --image uat-app:latest --registry uatprodacr12345 --file Dockerfile .
```

Get ACR login server:

```bash
az acr show --name uatprodacr12345 --query loginServer -o tsv
```

## 4) Create Key Vault and secrets

```bash
az keyvault create --name uatprod-kv --resource-group uat-prod-rg --enable-rbac-authorization true
```

Create secrets (example):

```bash
az keyvault secret set --vault-name uatprod-kv --name DATABASE-URL --value "postgresql+psycopg://pgadmin:<PASSWORD>@uatprod-pg.postgres.database.azure.com:5432/uat"
az keyvault secret set --vault-name uatprod-kv --name REDIS-URL --value "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
az keyvault secret set --vault-name uatprod-kv --name CELERY-BROKER-URL --value "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
az keyvault secret set --vault-name uatprod-kv --name CELERY-RESULT-BACKEND --value "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
az keyvault secret set --vault-name uatprod-kv --name APP-SECRET-KEY --value "<LONG_RANDOM_SECRET>"
az keyvault secret set --vault-name uatprod-kv --name AZURE-OPENAI-ENDPOINT --value "https://<resource>.openai.azure.com"
az keyvault secret set --vault-name uatprod-kv --name AZURE-OPENAI-API-KEY --value "<AZURE_KEY>"
az keyvault secret set --vault-name uatprod-kv --name AZURE-OPENAI-API-VERSION --value "2025-04-01-preview"
az keyvault secret set --vault-name uatprod-kv --name AZURE-OPENAI-DEPLOYMENT --value "gpt-5.2-chat"
```

Get secret URIs:

```bash
az keyvault secret show --vault-name uatprod-kv --name DATABASE-URL --query id -o tsv
```

## 5) Update parameters

Edit `infra/azure/bicep/params.prod.json`:
- Set `apiImage` and `workerImage` to `<ACR_LOGIN_SERVER>/uat-app:latest`
- Set `pgPassword`
- Set `kv*` parameters to Key Vault **secret URIs**

## 6) Deploy

```bash
az deployment group create \
  --resource-group uat-prod-rg \
  --template-file infra/azure/bicep/main.bicep \
  --parameters infra/azure/bicep/params.prod.json
```

## 7) Get API URL

```bash
az containerapp show --resource-group uat-prod-rg --name uatprod-api --query properties.configuration.ingress.fqdn -o tsv
```

## Notes
- Managed identities are assigned AcrPull and Key Vault Secrets User roles automatically by the template.
- Secrets are referenced directly from Key Vault; no secrets are stored in Container Apps configuration.
