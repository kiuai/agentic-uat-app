# Terraform Deployment (Container Apps + Private Endpoints)

This Terraform stack provisions:
- VNet + subnets (ACA + private endpoints)
- ACR
- Container Apps Environment
- API + Worker apps
- PostgreSQL Flexible Server
- Redis Cache
- Storage account + Azure Files share
- Private DNS zones + private endpoints

## 1) Init
```bash
terraform init
```

## 2) Set variables
Create `terraform.tfvars`:
```hcl
resource_group_name = "uat-prod-rg"
location            = "eastus"
name_prefix         = "uatprod"

api_image    = "<ACR_LOGIN_SERVER>/uat-app:latest"
worker_image = "<ACR_LOGIN_SERVER>/uat-app:latest"

pg_admin    = "pgadmin"
pg_password = "Fu!!3r3n3C60C6H5CH3"
pg_database = "uat"

redis_capacity   = 1
vnet_cidr        = "10.0.0.0/16"
aca_subnet_cidr  = "10.0.1.0/24"
pe_subnet_cidr   = "10.0.2.0/24"

evidence_share_name = "evidence"

database_url        = "postgresql+psycopg://pgadmin:<Fu!!3r3n3C60C6H5CH3>@uatprod-pg.postgres.database.azure.com:5432/uat"
redis_url           = "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
celery_broker_url   = "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
celery_result_backend = "rediss://uatprod-redis.redis.cache.windows.net:6380/0"
app_secret_key      = "Fu!!3r3n3C60C6H5CH3"

azure_openai_endpoint   = "https://kiu-auto-tester2.openai.azure.com"
azure_openai_api_key    = "DFlcMZpn9gEGxAqbFtc3O5I9l93mnvdTIqo6zIPN221vvBxzwSwcJQQJ99CAACHYHv6XJ3w3AAABACOGw2Ti"
azure_openai_api_version = "2025-04-01-preview"
azure_openai_deployment  = "gpt-5.2-chat"
```

## 3) Apply
```bash
terraform apply
```

## Notes
- This Terraform version stores secrets in state. For production, use Key Vault + external secret injection.
