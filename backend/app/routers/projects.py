"""Project and Environment endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CurrentUserDep, RequirePermission, TenantDB
from app.schemas.project import (
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from app.services.project_service import ProjectDashboard, ProjectService

router = APIRouter(prefix="/projects")


@router.get(
    "",
    response_model=list[ProjectRead],
    dependencies=[Depends(RequirePermission(Permission.PROJECT_READ))],
)
async def list_projects(db: TenantDB, current_user: CurrentUserDep) -> list[ProjectRead]:
    service = ProjectService(db)
    return await service.list_projects(current_user.tenant_id)


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.PROJECT_CREATE))],
)
async def create_project(
    body: ProjectCreate, db: TenantDB, current_user: CurrentUserDep
) -> ProjectRead:
    service = ProjectService(db)
    return await service.create_project(current_user.tenant_id, current_user.id, body)


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    dependencies=[Depends(RequirePermission(Permission.PROJECT_READ))],
)
async def get_project(project_id: uuid.UUID, db: TenantDB) -> ProjectRead:
    service = ProjectService(db)
    return await service.get_project(project_id)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    dependencies=[Depends(RequirePermission(Permission.PROJECT_UPDATE))],
)
async def update_project(
    project_id: uuid.UUID, body: ProjectUpdate, db: TenantDB
) -> ProjectRead:
    service = ProjectService(db)
    return await service.update_project(project_id, body)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.PROJECT_DELETE))],
)
async def delete_project(project_id: uuid.UUID, db: TenantDB) -> None:
    service = ProjectService(db)
    await service.archive_project(project_id)


@router.get(
    "/{project_id}/dashboard",
    response_model=ProjectDashboard,
    dependencies=[Depends(RequirePermission(Permission.PROJECT_READ))],
    summary="Live dashboard with requirement, script, cycle and execution counts",
)
async def get_project_dashboard(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUserDep
) -> ProjectDashboard:
    service = ProjectService(db)
    return await service.get_dashboard(project_id, current_user.tenant_id)


# ── Environments ──────────────────────────────────────────────────────────────

@router.get(
    "/{project_id}/environments",
    response_model=list[EnvironmentRead],
    dependencies=[Depends(RequirePermission(Permission.ENVIRONMENT_READ))],
)
async def list_environments(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUserDep
) -> list[EnvironmentRead]:
    service = ProjectService(db)
    return await service.list_environments(project_id, current_user.tenant_id)


@router.post(
    "/{project_id}/environments",
    response_model=EnvironmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.ENVIRONMENT_MANAGE))],
)
async def create_environment(
    project_id: uuid.UUID, body: EnvironmentCreate, db: TenantDB, current_user: CurrentUserDep
) -> EnvironmentRead:
    service = ProjectService(db)
    return await service.create_environment(project_id, current_user.tenant_id, body)


@router.patch(
    "/{project_id}/environments/{env_id}",
    response_model=EnvironmentRead,
    dependencies=[Depends(RequirePermission(Permission.ENVIRONMENT_MANAGE))],
)
async def update_environment(
    project_id: uuid.UUID, env_id: uuid.UUID, body: EnvironmentUpdate, db: TenantDB
) -> EnvironmentRead:
    service = ProjectService(db)
    return await service.update_environment(env_id, body)


@router.delete(
    "/{project_id}/environments/{env_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.ENVIRONMENT_MANAGE))],
)
async def delete_environment(
    project_id: uuid.UUID, env_id: uuid.UUID, db: TenantDB
) -> None:
    service = ProjectService(db)
    await service.delete_environment(env_id)
