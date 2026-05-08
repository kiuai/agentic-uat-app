"""
Azure Cosmos DB client factory.

Each company tenant gets its own Cosmos container: `kaats-{tenant_id}`.
Partition key within each container: /project_id.
"""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

import structlog
from azure.cosmos.aio import CosmosClient, ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.config import get_settings

logger = structlog.get_logger(__name__)


@lru_cache
def get_cosmos_client() -> CosmosClient:
    settings = get_settings()
    return CosmosClient(
        url=settings.azure_cosmos_endpoint,
        credential=settings.azure_cosmos_key,
    )


def get_cosmos_database() -> DatabaseProxy:
    settings = get_settings()
    return get_cosmos_client().get_database_client(settings.azure_cosmos_database)


def get_tenant_container(tenant_id: UUID) -> ContainerProxy:
    """Return the Cosmos container for the given company tenant."""
    db = get_cosmos_database()
    container_name = f"kaats-{tenant_id}"
    return db.get_container_client(container_name)


async def ensure_tenant_container(tenant_id: UUID) -> ContainerProxy:
    """
    Create the Cosmos container for a new tenant if it does not exist.
    Called during company provisioning, not on every request.
    """
    settings = get_settings()
    db = get_cosmos_database()
    container_name = f"kaats-{tenant_id}"

    try:
        container = await db.create_container_if_not_exists(
            id=container_name,
            partition_key={"paths": ["/project_id"], "kind": "Hash"},
            offer_throughput=None,  # Use database-level shared throughput
            default_ttl=-1,  # No TTL by default; AI logs set their own TTL
            indexing_policy={
                "includedPaths": [
                    {"path": "/status/?"},
                    {"path": "/tags/*"},
                    {"path": "/domain_code/?"},
                    {"path": "/created_at/?"},
                    {"path": "/type/?"},
                ],
                "excludedPaths": [{"path": "/*"}],
            },
        )
        logger.info("cosmos_container_ensured", tenant_id=str(tenant_id), container=container_name)
        return container
    except Exception as exc:
        logger.error(
            "cosmos_container_creation_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        raise


async def check_cosmos_connection() -> bool:
    """Health check — returns True if Cosmos DB is reachable."""
    try:
        settings = get_settings()
        client = get_cosmos_client()
        await client.get_database_client(settings.azure_cosmos_database).read()
        return True
    except Exception as exc:
        logger.error("cosmos_health_check_failed", error=str(exc))
        return False


async def close_cosmos_client() -> None:
    """Close the Cosmos client HTTP session on application shutdown."""
    client = get_cosmos_client()
    await client.close()
