import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthenticatedUser, get_current_user, require_admin
from app.database import get_db
from app.models.environment import Environment
from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentListItem,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from app.schemas.setting import ConnectionTestResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


@router.get("", response_model=list[EnvironmentListItem])
async def list_environments(
    location_id: Optional[int] = Query(None, description="Filter by phpIPAM location ID"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List enabled environments for the request form dropdown."""
    query = (
        select(Environment)
        .where(Environment.enabled == True)
        .order_by(Environment.display_name)
    )
    if location_id is not None:
        query = query.where(Environment.location_id == location_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/all", response_model=list[EnvironmentResponse])
async def list_all_environments(
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all environments including disabled (admin management)."""
    result = await db.execute(
        select(Environment).order_by(Environment.display_name)
    )
    return result.scalars().all()


@router.post("", response_model=EnvironmentResponse, status_code=201)
async def create_environment(
    payload: EnvironmentCreate,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new environment."""
    existing = await db.execute(
        select(Environment).where(Environment.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Environment '{payload.name}' already exists")

    # If this is marked as default, unset any existing default
    if payload.is_default:
        await _clear_default(db)

    env = Environment(**payload.model_dump())
    db.add(env)
    await db.commit()
    await db.refresh(env)
    return env


@router.put("/{env_id}", response_model=EnvironmentResponse)
async def update_environment(
    env_id: int,
    payload: EnvironmentUpdate,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing environment."""
    result = await db.execute(
        select(Environment).where(Environment.id == env_id)
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
    """Delete an environment."""
    result = await db.execute(
        select(Environment).where(Environment.id == env_id)
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
    """Test connectivity for a specific environment."""
    result = await db.execute(
        select(Environment).where(Environment.id == env_id)
    )
    env = result.scalar_one_or_none()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    try:
        if env.environment_type == "proxmox":
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
        elif env.environment_type in ("esxi", "vcenter"):
            from app.services.vsphere import VSphereService

            vs = VSphereService(
                host=env.vsphere_host,
                user=env.vsphere_user,
                password=env.vsphere_password,
                port=env.vsphere_port,
                verify_ssl=env.vsphere_verify_ssl,
                datacenter=env.vsphere_datacenter,
                cluster=env.vsphere_cluster,
            )
            version = await asyncio.to_thread(vs.get_version)
            await asyncio.to_thread(vs.disconnect)
            label = "vCenter" if env.environment_type == "vcenter" else "ESXi"
            return ConnectionTestResult(
                success=True,
                message=f"Connected to {label} {version.get('version', 'unknown')} "
                        f"(build {version.get('build', 'unknown')})",
            )
        else:
            return ConnectionTestResult(success=False, message=f"Unknown environment type: {env.environment_type}")
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))


async def _clear_default(db: AsyncSession) -> None:
    """Unset is_default on all environments."""
    result = await db.execute(
        select(Environment).where(Environment.is_default == True)
    )
    for env in result.scalars().all():
        env.is_default = False
