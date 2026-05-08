"""
Azure Entra ID (formerly Azure AD) JWT validation.

Validates RS256 JWTs issued by Azure Entra ID for the KAATS application
registration. Public keys are fetched from the Entra ID JWKS endpoint and
cached with a 1-hour TTL.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

import httpx
import structlog
from jose import JWTError, jwt
from jose.backends.rsa_backend import RSAKey

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# JWKS cache: {kid: RSAKey}
_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


class TokenValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _get_signing_key(self, kid: str) -> Any:
        global _jwks_cache, _jwks_fetched_at

        now = time.monotonic()
        if now - _jwks_fetched_at > _JWKS_TTL_SECONDS or kid not in _jwks_cache:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self._settings.entra_jwks_uri, timeout=10)
                resp.raise_for_status()
                jwks = resp.json()

            _jwks_cache = {key["kid"]: key for key in jwks.get("keys", [])}
            _jwks_fetched_at = now
            logger.debug("jwks_refreshed", key_count=len(_jwks_cache))

        key = _jwks_cache.get(kid)
        if key is None:
            raise ValueError(f"No signing key found for kid={kid!r}")
        return key

    async def validate(self, token: str) -> dict[str, Any]:
        """
        Validate a JWT and return its decoded claims.
        Raises ValueError with a user-safe message on any validation failure.
        """
        try:
            # Peek at the header to find the key ID
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise ValueError("Malformed token header.") from exc

        kid = header.get("kid")
        if not kid:
            raise ValueError("Token header missing 'kid' claim.")

        signing_key = await self._get_signing_key(kid)

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._settings.azure_client_id,
                issuer=self._settings.entra_issuer,
                options={"verify_exp": True},
            )
        except JWTError as exc:
            logger.warning("token_validation_failed", error=str(exc))
            raise ValueError(f"Token validation failed: {exc}") from exc

        return claims


@lru_cache
def get_token_validator() -> TokenValidator:
    return TokenValidator(get_settings())
