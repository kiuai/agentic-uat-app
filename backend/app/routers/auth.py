"""Auth router — token introspection and user profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUser
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth")


@router.get("/me", response_model=UserRead, summary="Get current authenticated user")
async def get_me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's profile derived from their JWT claims."""
    return UserRead(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        domains=current_user.get_domains(),
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )
