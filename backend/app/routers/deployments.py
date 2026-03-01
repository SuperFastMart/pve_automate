import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import AuthenticatedUser, get_current_user, require_admin
from app.config import load_tshirt_sizes
from app.database import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.vm_request import RequestStatus, VMRequest
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentList,
    DeploymentListItem,
    DeploymentResponse,
)
from app.services.jira import get_jira_service, get_jira_settings
from app.services.phpipam import get_phpipam_service
from app.services.email import send_request_received
from app.services.provisioning import provision_deployment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/deployments", tags=["deployments"])


@router.post("", response_model=DeploymentResponse, status_code=201)
async def create_deployment(
    payload: DeploymentCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a multi-VM deployment."""
    sizes = load_tshirt_sizes()

    # Resolve environment
    environment_name = None
    if payload.environment_id:
        from app.models.environment import Environment as PVEEnvironment
        env_result = await db.execute(
            select(PVEEnvironment).where(PVEEnvironment.id == payload.environment_id)
        )
        env = env_result.scalar_one_or_none()
        if not env:
            raise HTTPException(status_code=400, detail="Selected environment not found")
        if not env.enabled:
            raise HTTPException(status_code=400, detail="Selected environment is disabled")
        environment_name = env.display_name

    # Create deployment
    deployment = Deployment(
        name=payload.name,
        description=payload.description,
        requestor_name=user.name,
        requestor_email=user.email,
        workload_type=payload.workload_type,
        environment_id=payload.environment_id,
        environment_name=environment_name,
        status=DeploymentStatus.PENDING_APPROVAL,
    )
    db.add(deployment)
    await db.flush()  # Get deployment.id

    # Create VM requests
    vm_requests = []
    for vm in payload.vms:
        if vm.tshirt_size == "Custom":
            if not all([vm.cpu_cores, vm.ram_mb, vm.disk_gb]):
                raise HTTPException(
                    status_code=400,
                    detail=f"VM '{vm.vm_name}': Custom size requires cpu_cores, ram_mb, and disk_gb",
                )
            cpu_cores = vm.cpu_cores
            ram_mb = vm.ram_mb
            disk_gb = vm.disk_gb
        else:
            size_config = sizes.get(vm.tshirt_size)
            if not size_config:
                raise HTTPException(
                    status_code=400,
                    detail=f"VM '{vm.vm_name}': Invalid t-shirt size: {vm.tshirt_size}",
                )
            cpu_cores = size_config["cpu_cores"]
            ram_mb = size_config["ram_mb"]
            disk_gb = size_config["disk_gb"]

        vm_request = VMRequest(
            vm_name=vm.vm_name,
            description=vm.description,
            requestor_name=user.name,
            requestor_email=user.email,
            workload_type=payload.workload_type,
            os_template=vm.os_template,
            tshirt_size=vm.tshirt_size,
            cpu_cores=cpu_cores,
            ram_mb=ram_mb,
            disk_gb=disk_gb,
            subnet_id=vm.subnet_id,
            environment_id=payload.environment_id,
            environment_name=environment_name,
            deployment_id=deployment.id,
            status=RequestStatus.PENDING_APPROVAL,
        )
        db.add(vm_request)
        vm_requests.append(vm_request)

    await db.commit()
    await db.refresh(deployment)

    # Allocate IPs from phpIPAM for each VM with a subnet_id
    for i, vm_def in enumerate(payload.vms):
        vm_req = vm_requests[i]
        if vm_def.subnet_id:
            try:
                ipam = await get_phpipam_service(db)
                if ipam:
                    allocation = await ipam.allocate_ip(
                        subnet_id=vm_def.subnet_id,
                        hostname=vm_req.vm_name,
                        description=f"{vm_req.vm_name} — {payload.workload_type} (deployment: {deployment.name})",
                        owner=user.name,
                    )
                    vm_req.ip_address = allocation["ip"]
                    vm_req.phpipam_address_id = allocation["id"]
                    await ipam.close()
                    logger.info(
                        f"Allocated IP {allocation['ip']} for VM {vm_req.vm_name} "
                        f"in deployment {deployment.id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to allocate IP for VM {vm_req.vm_name}: {e}")

    await db.commit()
    # Refresh all VM requests to get updated IPs
    for vm_req in vm_requests:
        await db.refresh(vm_req)

    # Create single Jira ticket for the whole deployment
    try:
        jira = await get_jira_service(db)
        if jira:
            jira_settings = await get_jira_settings(db)
            project_key = jira_settings.get("JIRA_PROJECT_KEY", "INFRA")
            issue_type = jira_settings.get("JIRA_ISSUE_TYPE", "Service Request")

            summary = f"Deployment: {deployment.name}"
            desc_lines = [
                f"Requestor: {deployment.requestor_name} ({deployment.requestor_email})",
                f"Deployment: {deployment.name}",
                f"Workload Type: {deployment.workload_type}",
            ]
            if environment_name:
                desc_lines.append(f"Environment: {environment_name}")
            if deployment.description:
                desc_lines.append(f"Description: {deployment.description}")
            desc_lines.append("")
            desc_lines.append(f"VMs ({len(vm_requests)}):")
            for vm_req in vm_requests:
                line = (
                    f"  - {vm_req.vm_name}: {vm_req.os_template}, "
                    f"{vm_req.tshirt_size} ({vm_req.cpu_cores}C / {vm_req.ram_mb}MB / {vm_req.disk_gb}GB)"
                )
                if vm_req.ip_address:
                    line += f", IP: {vm_req.ip_address}"
                desc_lines.append(line)

            description = "\n".join(desc_lines)
            result = await jira.create_issue(project_key, summary, description, issue_type)
            deployment.jira_issue_key = result["key"]
            deployment.jira_issue_url = result["url"]
            await db.commit()
            await db.refresh(deployment)
            await jira.close()

            # Update phpIPAM records with Jira ticket link
            for vm_req in vm_requests:
                if vm_req.phpipam_address_id and result.get("url"):
                    try:
                        ipam = await get_phpipam_service(db)
                        if ipam:
                            await ipam.update_ip(
                                vm_req.phpipam_address_id,
                                note=f"Jira: {result['url']}",
                            )
                            await ipam.close()
                    except Exception as e:
                        logger.warning(f"Failed to update phpIPAM with Jira link: {e}")
    except Exception as e:
        logger.warning(f"Failed to create Jira issue for deployment {deployment.id}: {e}")

    # Send email notification (fire-and-forget — uses first VM's ID)
    if vm_requests:
        asyncio.create_task(send_request_received(vm_requests[0].id))

    return deployment


@router.get("", response_model=DeploymentList)
async def list_deployments(
    status: Optional[DeploymentStatus] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List deployments with pagination."""
    query = select(Deployment)

    # Non-admin users can only see their own deployments
    if not user.is_admin:
        query = query.where(Deployment.requestor_email == user.email)

    if status:
        query = query.where(Deployment.status == status)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.options(selectinload(Deployment.vm_requests))
    query = query.order_by(Deployment.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    deployments = result.scalars().unique().all()

    items = [
        DeploymentListItem(
            id=d.id,
            name=d.name,
            requestor_name=d.requestor_name,
            requestor_email=d.requestor_email,
            workload_type=d.workload_type,
            environment_name=d.environment_name,
            status=d.status,
            jira_issue_key=d.jira_issue_key,
            vm_count=len(d.vm_requests),
            created_at=d.created_at,
        )
        for d in deployments
    ]

    return DeploymentList(items=items, total=total)


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get deployment details including all VMs."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vm_requests))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


@router.post("/{deployment_id}/approve", response_model=DeploymentResponse)
async def approve_deployment(
    deployment_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a deployment. Sets all VMs to approved and starts provisioning."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vm_requests))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status != DeploymentStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve deployment in '{deployment.status.value}' state",
        )

    now = datetime.now(timezone.utc)
    deployment.status = DeploymentStatus.APPROVED
    deployment.approved_at = now

    for vm_req in deployment.vm_requests:
        vm_req.status = RequestStatus.APPROVED
        vm_req.approved_at = now

    await db.commit()
    await db.refresh(deployment)

    # Fire-and-forget provisioning
    asyncio.create_task(provision_deployment(deployment_id))

    # Sync to Jira (fire-and-forget)
    if deployment.jira_issue_key:
        asyncio.create_task(
            _sync_deployment_jira(deployment.jira_issue_key, "approve", "Deployment approved via admin UI")
        )

    return deployment


@router.post("/{deployment_id}/reject", response_model=DeploymentResponse)
async def reject_deployment(
    deployment_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a deployment. Sets all VMs to rejected."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vm_requests))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status != DeploymentStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject deployment in '{deployment.status.value}' state",
        )

    deployment.status = DeploymentStatus.REJECTED

    for vm_req in deployment.vm_requests:
        vm_req.status = RequestStatus.REJECTED
        # Release phpIPAM IPs
        if vm_req.phpipam_address_id:
            asyncio.create_task(_release_phpipam_ip(vm_req.phpipam_address_id))

    await db.commit()
    await db.refresh(deployment)

    # Sync to Jira (fire-and-forget)
    if deployment.jira_issue_key:
        asyncio.create_task(
            _sync_deployment_jira(deployment.jira_issue_key, "reject", "Deployment rejected via admin UI")
        )

    # Send rejection email (fire-and-forget)
    from app.services.email import send_request_rejected
    if deployment.vm_requests:
        asyncio.create_task(send_request_rejected(deployment.vm_requests[0].id))

    return deployment


@router.post("/{deployment_id}/retry", response_model=DeploymentResponse)
async def retry_deployment(
    deployment_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retry provisioning for a failed or partially completed deployment.

    Only re-provisions VMs that failed — completed VMs are left untouched.
    """
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vm_requests))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status not in (DeploymentStatus.FAILED, DeploymentStatus.PARTIALLY_COMPLETED):
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed deployments (current: '{deployment.status.value}')",
        )

    # Reset only the failed VMs
    failed_count = 0
    for vm_req in deployment.vm_requests:
        if vm_req.status == RequestStatus.PROVISIONING_FAILED:
            vm_req.status = RequestStatus.APPROVED
            vm_req.error_message = None
            failed_count += 1

    deployment.status = DeploymentStatus.APPROVED
    deployment.error_message = None
    await db.commit()
    await db.refresh(deployment)

    # Fire-and-forget provisioning
    asyncio.create_task(provision_deployment(deployment_id))

    # Post Jira comment (fire-and-forget)
    if deployment.jira_issue_key:
        asyncio.create_task(
            _jira_deployment_comment(
                deployment.jira_issue_key,
                f"Retrying provisioning for {failed_count} failed VM(s) via admin UI",
            )
        )

    return deployment


async def _jira_deployment_comment(issue_key: str, comment: str) -> None:
    """Background task: add a comment to a deployment Jira issue."""
    from app.database import async_session

    try:
        async with async_session() as db:
            jira = await get_jira_service(db)
            if not jira:
                return
            await jira.add_comment(issue_key, comment)
            await jira.close()
    except Exception as e:
        logger.warning(f"Failed to add Jira comment to {issue_key}: {e}")


async def _sync_deployment_jira(issue_key: str, action: str, comment: str) -> None:
    """Background task: transition deployment Jira issue and add a comment."""
    from app.database import async_session

    try:
        async with async_session() as db:
            jira = await get_jira_service(db)
            if not jira:
                return
            jira_settings = await get_jira_settings(db)

            if action == "approve":
                status_name = jira_settings.get("JIRA_APPROVE_STATUS", "Approved")
            else:
                status_name = jira_settings.get("JIRA_REJECT_STATUS", "Declined")

            await jira.transition_issue(issue_key, status_name)
            await jira.add_comment(issue_key, comment)
            await jira.close()
    except Exception as e:
        logger.warning(f"Failed to sync {action} to Jira issue {issue_key}: {e}")


async def _release_phpipam_ip(address_id: int) -> None:
    """Background task: release an IP address in phpIPAM."""
    from app.database import async_session

    try:
        async with async_session() as db:
            ipam = await get_phpipam_service(db)
            if not ipam:
                return
            await ipam.release_ip(address_id)
            await ipam.close()
            logger.info(f"Released phpIPAM address ID {address_id}")
    except Exception as e:
        logger.warning(f"Failed to release phpIPAM address {address_id}: {e}")
