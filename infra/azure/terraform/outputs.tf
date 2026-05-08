output "api_fqdn" {
  value = azurerm_container_app.api.latest_revision_fqdn
}

output "postgres_host" {
  value = azurerm_postgresql_flexible_server.pg.fqdn
}

output "redis_host" {
  value = azurerm_redis_cache.redis.hostname
}
