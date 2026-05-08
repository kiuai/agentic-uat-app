variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "name_prefix" { type = string }

variable "api_image" { type = string }
variable "worker_image" { type = string }

variable "pg_admin" { type = string }
variable "pg_password" { type = string }
variable "pg_database" { type = string }

variable "redis_capacity" { type = number }

variable "vnet_cidr" { type = string }
variable "aca_subnet_cidr" { type = string }
variable "pe_subnet_cidr" { type = string }

variable "evidence_share_name" { type = string }

# Secrets (Terraform variant uses direct values; prefer Key Vault + external secrets manager in production)
variable "database_url" { type = string }
variable "redis_url" { type = string }
variable "celery_broker_url" { type = string }
variable "celery_result_backend" { type = string }
variable "app_secret_key" { type = string }
variable "azure_openai_endpoint" { type = string }
variable "azure_openai_api_key" { type = string }
variable "azure_openai_api_version" { type = string }
variable "azure_openai_deployment" { type = string }
