"""Azure Blob Storage service for tenant-scoped file operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

from app.config import get_settings

logger = structlog.get_logger(__name__)


class BlobService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = BlobServiceClient.from_connection_string(
            self._settings.azure_storage_connection_string
        )

    def _container_name(self, tenant_id: uuid.UUID) -> str:
        return f"tenant-{tenant_id}"

    async def upload(
        self,
        tenant_id: uuid.UUID,
        blob_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        container = self._container_name(tenant_id)
        container_client = self._client.get_container_client(container)

        try:
            await container_client.create_container()
        except Exception:
            pass  # Container already exists

        blob_client = container_client.get_blob_client(blob_path)
        await blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings={"content_type": content_type},
        )
        logger.info("blob_uploaded", container=container, path=blob_path, size=len(data))
        return blob_client.url

    async def download(self, tenant_id: uuid.UUID, blob_path: str) -> bytes:
        container = self._container_name(tenant_id)
        blob_client = self._client.get_container_client(container).get_blob_client(blob_path)
        stream = await blob_client.download_blob()
        return await stream.readall()

    def get_sas_url(
        self, tenant_id: uuid.UUID, blob_path: str, expiry_hours: int = 24
    ) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        sas_token = generate_blob_sas(
            account_name=self._settings.azure_storage_account_name,
            container_name=self._container_name(tenant_id),
            blob_name=blob_path,
            account_key=self._settings.azure_storage_account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )
        return (
            f"https://{self._settings.azure_storage_account_name}.blob.core.windows.net"
            f"/{self._container_name(tenant_id)}/{blob_path}?{sas_token}"
        )

    async def close(self) -> None:
        await self._client.close()
