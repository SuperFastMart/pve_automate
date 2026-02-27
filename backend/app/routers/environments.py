import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthenticatedUser, get_current_user, require_admin
from app.database import get_db
from app.models.pve_environment import PVEEnvironment
from app.schemas.pve_environment import (
    PVEEnvironmentCreate,
    PVEEnvironmentListItem,
    PVEEnvironmentResponse,
    PVEEnvironmentUpdate,
)
from app.schemas.setting import ConnectionTestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


@router.get("", response_model=list[PVEEnvironmentListItem])
async def list_environments(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List enabled environments for the request form dropdown."""
    result = await db.execute(
        select(PVEEnvironment)
        .where(PVEEnvironment.enabled == True)
        .order_by(PVEEnvironment.display_name)
    )
    return result.scalars().all()


@router.get("/all", response_model=list[PVEEnvironmentResponse])
async def list_all_environments(
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all environments including disabled (admin management)."""
    result = await db.execute(
        select(PVEEnvironment).order_by(PVEEnvironment.display_name)
    )
    return result.scalars().all()


@router.post("", response_model=PVEEnvironmentResponse, status_code=201)
async def create_environment(
    payload: PVEEnvironmentCreate,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new PVE environment."""
    existing = await db.execute(
        select(PVEEnvironment).where(PVEEnvironment.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Environment '{payload.name}' already exists")

    # If this is marked as default, unset any existing default
    if payload.is_default:
        await _clear_default(db)

    env = PVEEnvironment(**payload.model_dump())
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


@router.put("/{env_id}", response_model=PVEEnvironmentResponse)
async def update_environment(
    env_id: int,
    payload: PVEEnvironmentUpdate,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing PVE environment."""
    result = await db.execute(
        select(PVEEnvironment).where(PVEEnvironment.id == env_id)
    )
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If setting as default, clear existing default first
    if update_data.get("is_default"):
        await _clear_default(db)

    for field, value in update_data.items():
        setattr(env, field, value)

    await db.commit()
    await db.refresh(env)
    return env


@router.delete("/{env_id}", status_code=204)
async def delete_environment(
    env_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a PVE environment."""
    result = await db.execute(
        select(PVEEnvironment).where(PVEEnvironment.id == env_id)
    )
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    # Check if any VM requests reference this environment
    from app.models.vm_request import VMRequest
    ref_result = await db.execute(
        select(VMRequest.id).where(VMRequest.environment_id == env_id).limit(1)
    )
    if ref_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete environment that is referenced by existing requests. Disable it instead.",
        )

    await db.delete(env)
    await db.commit()


@router.post("/{env_id}/test", response_model=ConnectionTestResult)
async def test_environment_connection(
    env_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Test Proxmox connectivity for a specific environment."""
    result = await db.execute(
        select(PVEEnvironment).where(PVEEnvironment.id == env_id)
    )
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    try:
        from app.services.proxmox import ProxmoxService

        pve = ProxmoxService(
            host=env.pve_host,
            user=env.pve_user,
            token_name=env.pve_token_name,
            token_value=env.pve_token_value,
            verify_ssl=env.pve_verify_ssl,
        )
        version = await asyncio.to_thread(pve.get_version)
        return ConnectionTestResult(
            success=True,
            message=f"Connected to Proxmox VE {version.get('version', 'unknown')} "
                    f"(release {version.get('release', 'unknown')})",
        )
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))


async def _clear_default(db: AsyncSession) -> None:
    """Unset is_default on all environments."""
    result = await db.execute(
        select(PVEEnvironment).where(PVEEnvironment.is_default == True)
    )
    for env in result.scalars().all():
        env.is_default = False
