terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.111"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_virtual_network" "vnet" {
  name                = "${var.name_prefix}-vnet"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = [var.vnet_cidr]
}

resource "azurerm_subnet" "aca" {
  name                 = "${var.name_prefix}-aca-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = [var.aca_subnet_cidr]
  delegation {
    name = "aca-delegation"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "${var.name_prefix}-pe-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = [var.pe_subnet_cidr]
  private_endpoint_network_policies_enabled = false
}

resource "azurerm_container_registry" "acr" {
  name                = "${var.name_prefix}acr"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Standard"
  admin_enabled       = false
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${var.name_prefix}-logs"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "aca" {
  name                       = "${var.name_prefix}-aca"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
  infrastructure_subnet_id   = azurerm_subnet.aca.id
}

resource "azurerm_postgresql_flexible_server" "pg" {
  name                   = "${var.name_prefix}-pg"
  resource_group_name    = azurerm_resource_group.rg.name
  location               = azurerm_resource_group.rg.location
  administrator_login    = var.pg_admin
  administrator_password = var.pg_password
  version                = "16"
  sku_name               = "Standard_D4ds_v5"
  storage_mb             = 131072
  public_network_access_enabled = false
}

resource "azurerm_postgresql_flexible_server_database" "pgdb" {
  name      = var.pg_database
  server_id = azurerm_postgresql_flexible_server.pg.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_redis_cache" "redis" {
  name                = "${var.name_prefix}-redis"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  capacity            = var.redis_capacity
  family              = "C"
  sku_name            = "Standard"
  minimum_tls_version = "1.2"
  public_network_access_enabled = false
}

resource "azurerm_storage_account" "storage" {
  name                     = replace(lower("${var.name_prefix}storage"), "-", "")
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_share" "evidence" {
  name                 = var.evidence_share_name
  storage_account_name = azurerm_storage_account.storage.name
  quota                = 1024
}

resource "azurerm_key_vault" "kv" {
  name                       = "${var.name_prefix}-kv"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  public_network_access_enabled = false
}

data "azurerm_client_config" "current" {}

resource "azurerm_private_dns_zone" "postgres" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.cache.windows.net"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone" "file" {
  name                = "privatelink.file.core.windows.net"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone" "kv" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "pg_link" {
  name                  = "${var.name_prefix}-pg-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_dns_zone_virtual_network_link" "redis_link" {
  name                  = "${var.name_prefix}-redis-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.redis.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_dns_zone_virtual_network_link" "file_link" {
  name                  = "${var.name_prefix}-file-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.file.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_dns_zone_virtual_network_link" "kv_link" {
  name                  = "${var.name_prefix}-kv-link"
  resource_group_name   = azurerm_resource_group.rg.name
  private_dns_zone_name = azurerm_private_dns_zone.kv.name
  virtual_network_id    = azurerm_virtual_network.vnet.id
}

resource "azurerm_private_endpoint" "pg" {
  name                = "${var.name_prefix}-pe-postgres"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  private_service_connection {
    name                           = "pg-connection"
    private_connection_resource_id = azurerm_postgresql_flexible_server.pg.id
    subresource_names              = ["postgresqlServer"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_dns_zone_group" "pg_dns" {
  name                 = "pg-dns"
  private_endpoint_id  = azurerm_private_endpoint.pg.id
  private_dns_zone_ids = [azurerm_private_dns_zone.postgres.id]
}

resource "azurerm_private_endpoint" "redis" {
  name                = "${var.name_prefix}-pe-redis"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  private_service_connection {
    name                           = "redis-connection"
    private_connection_resource_id = azurerm_redis_cache.redis.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_dns_zone_group" "redis_dns" {
  name                 = "redis-dns"
  private_endpoint_id  = azurerm_private_endpoint.redis.id
  private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
}

resource "azurerm_private_endpoint" "kv" {
  name                = "${var.name_prefix}-pe-kv"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  private_service_connection {
    name                           = "kv-connection"
    private_connection_resource_id = azurerm_key_vault.kv.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_dns_zone_group" "kv_dns" {
  name                 = "kv-dns"
  private_endpoint_id  = azurerm_private_endpoint.kv.id
  private_dns_zone_ids = [azurerm_private_dns_zone.kv.id]
}

resource "azurerm_private_endpoint" "file" {
  name                = "${var.name_prefix}-pe-file"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  private_service_connection {
    name                           = "file-connection"
    private_connection_resource_id = azurerm_storage_account.storage.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }
}

resource "azurerm_private_dns_zone_group" "file_dns" {
  name                 = "file-dns"
  private_endpoint_id  = azurerm_private_endpoint.file.id
  private_dns_zone_ids = [azurerm_private_dns_zone.file.id]
}

resource "azurerm_container_app_environment_storage" "evidence" {
  name                         = "${var.name_prefix}-evidence"
  container_app_environment_id = azurerm_container_app_environment.aca.id
  account_name                 = azurerm_storage_account.storage.name
  share_name                   = azurerm_storage_share.evidence.name
  access_key                   = azurerm_storage_account.storage.primary_access_key
}

resource "azurerm_container_app" "api" {
  name                         = "${var.name_prefix}-api"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca.id
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = "System"
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }
  secret {
    name  = "redis-url"
    value = var.redis_url
  }
  secret {
    name  = "celery-broker"
    value = var.celery_broker_url
  }
  secret {
    name  = "celery-backend"
    value = var.celery_result_backend
  }
  secret {
    name  = "app-secret"
    value = var.app_secret_key
  }
  secret {
    name  = "azure-endpoint"
    value = var.azure_openai_endpoint
  }
  secret {
    name  = "azure-api-key"
    value = var.azure_openai_api_key
  }
  secret {
    name  = "azure-api-version"
    value = var.azure_openai_api_version
  }
  secret {
    name  = "azure-deployment"
    value = var.azure_openai_deployment
  }

  ingress {
    external_enabled = true
    target_port      = 8000
  }

  template {
    volume {
      name         = "evidence"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.evidence.name
    }
    container {
      name   = "api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker"
      }
      env {
        name        = "CELERY_RESULT_BACKEND"
        secret_name = "celery-backend"
      }
      env {
        name        = "APP_SECRET_KEY"
        secret_name = "app-secret"
      }
      env {
        name  = "EVIDENCE_DIR"
        value = "/data/evidence"
      }
      env {
        name  = "LLM_PROVIDER"
        value = "azure"
      }
      env {
        name        = "AZURE_OPENAI_ENDPOINT"
        secret_name = "azure-endpoint"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-api-key"
      }
      env {
        name        = "AZURE_OPENAI_API_VERSION"
        secret_name = "azure-api-version"
      }
      env {
        name        = "AZURE_OPENAI_DEPLOYMENT"
        secret_name = "azure-deployment"
      }

      volume_mounts {
        name       = "evidence"
        mount_path = "/data/evidence"
      }
    }
  }
}

resource "azurerm_container_app" "worker" {
  name                         = "${var.name_prefix}-worker"
  resource_group_name          = azurerm_resource_group.rg.name
  container_app_environment_id = azurerm_container_app_environment.aca.id
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  registry {
    server   = azurerm_container_registry.acr.login_server
    identity = "System"
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }
  secret {
    name  = "redis-url"
    value = var.redis_url
  }
  secret {
    name  = "celery-broker"
    value = var.celery_broker_url
  }
  secret {
    name  = "celery-backend"
    value = var.celery_result_backend
  }
  secret {
    name  = "app-secret"
    value = var.app_secret_key
  }
  secret {
    name  = "azure-endpoint"
    value = var.azure_openai_endpoint
  }
  secret {
    name  = "azure-api-key"
    value = var.azure_openai_api_key
  }
  secret {
    name  = "azure-api-version"
    value = var.azure_openai_api_version
  }
  secret {
    name  = "azure-deployment"
    value = var.azure_openai_deployment
  }

  template {
    volume {
      name         = "evidence"
      storage_type = "AzureFile"
      storage_name = azurerm_container_app_environment_storage.evidence.name
    }
    container {
      name   = "worker"
      image  = var.worker_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name        = "CELERY_BROKER_URL"
        secret_name = "celery-broker"
      }
      env {
        name        = "CELERY_RESULT_BACKEND"
        secret_name = "celery-backend"
      }
      env {
        name        = "APP_SECRET_KEY"
        secret_name = "app-secret"
      }
      env {
        name  = "EVIDENCE_DIR"
        value = "/data/evidence"
      }
      env {
        name  = "LLM_PROVIDER"
        value = "azure"
      }
      env {
        name        = "AZURE_OPENAI_ENDPOINT"
        secret_name = "azure-endpoint"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-api-key"
      }
      env {
        name        = "AZURE_OPENAI_API_VERSION"
        secret_name = "azure-api-version"
      }
      env {
        name        = "AZURE_OPENAI_DEPLOYMENT"
        secret_name = "azure-deployment"
      }

      volume_mounts {
        name       = "evidence"
        mount_path = "/data/evidence"
      }
    }
  }
}
