import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_effective_settings, load_tshirt_sizes
from app.database import get_db
from app.models.vm_request import RequestStatus, VMRequest
from app.schemas.vm_request import VMRequestCreate, VMRequestList, VMRequestResponse
from app.services.jira import get_jira_service, get_jira_settings
from app.services.phpipam import get_phpipam_service
from app.services.provisioning import provision_vm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


@router.post("", response_model=VMRequestResponse, status_code=201)
async def create_vm_request(
    payload: VMRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    # Resolve t-shirt size to specs
    sizes = load_tshirt_sizes()
    size_config = sizes.get(payload.tshirt_size)
    if not size_config:
        raise HTTPException(status_code=400, detail=f"Invalid t-shirt size: {payload.tshirt_size}")

    vm_request = VMRequest(
        vm_name=payload.vm_name,
        description=payload.description,
        requestor_name=payload.requestor_name,
        requestor_email=payload.requestor_email,
        workload_type=payload.workload_type,
        os_template=payload.os_template,
        tshirt_size=payload.tshirt_size,
        cpu_cores=size_config["cpu_cores"],
        ram_mb=size_config["ram_mb"],
        disk_gb=size_config["disk_gb"],
        subnet_id=payload.subnet_id,
        status=RequestStatus.PENDING_APPROVAL,
    )

    db.add(vm_request)
    await db.commit()
    await db.refresh(vm_request)

    # Allocate IP from phpIPAM (non-blocking — don't fail the request if phpIPAM is down)
    if payload.subnet_id:
        try:
            ipam = await get_phpipam_service(db)
            if ipam:
                allocation = await ipam.allocate_ip(
                    subnet_id=payload.subnet_id,
                    hostname=payload.vm_name,
                    description=f"Peevinator request #{vm_request.id}",
                )
                vm_request.ip_address = allocation["ip"]
                vm_request.phpipam_address_id = allocation["id"]
                await db.commit()
                await db.refresh(vm_request)
                await ipam.close()
                logger.info(
                    f"Allocated IP {allocation['ip']} (phpIPAM ID {allocation['id']}) "
                    f"for request {vm_request.id}"
                )
        except Exception as e:
            logger.warning(f"Failed to allocate IP for request {vm_request.id}: {e}")

    # Create Jira issue (non-blocking — don't fail the request if Jira is down)
    try:
        jira = await get_jira_service(db)
        if jira:
            jira_settings = await get_jira_settings(db)
            project_key = jira_settings.get("JIRA_PROJECT_KEY", "INFRA")
            issue_type = jira_settings.get("JIRA_ISSUE_TYPE", "Service Request")

            summary = f"VM Request: {vm_request.vm_name}"
            desc_lines = [
                f"Requestor: {vm_request.requestor_name} ({vm_request.requestor_email})",
                f"VM Name: {vm_request.vm_name}",
                f"Workload Type: {vm_request.workload_type}",
                f"OS Template: {vm_request.os_template}",
                f"Size: {vm_request.tshirt_size} "
                f"({vm_request.cpu_cores} vCPU, {vm_request.ram_mb} MB RAM, {vm_request.disk_gb} GB disk)",
            ]
            if vm_request.ip_address:
                desc_lines.append(f"IP Address: {vm_request.ip_address}")
            if vm_request.subnet_id:
                # Try to fetch subnet details from phpIPAM for context
                try:
                    ipam = await get_phpipam_service(db)
                    if ipam:
                        all_subnets = await ipam.get_subnets()
                        await ipam.close()
                        subnet_info = next(
                            (s for s in all_subnets if s["id"] == vm_request.subnet_id), None
                        )
                        if subnet_info:
                            subnet_label = subnet_info.get("description", "")
                            subnet_cidr = f"{subnet_info['subnet']}/{subnet_info['mask']}"
                            if subnet_label:
                                desc_lines.append(f"Subnet: {subnet_label} ({subnet_cidr})")
                            else:
                                desc_lines.append(f"Subnet: {subnet_cidr}")
                        else:
                            desc_lines.append(f"Subnet ID: {vm_request.subnet_id}")
                except Exception:
                    desc_lines.append(f"Subnet ID: {vm_request.subnet_id}")
            desc_lines.append(f"Description: {vm_request.description or 'N/A'}")
            description = "\n".join(desc_lines)

            result = await jira.create_issue(project_key, summary, description, issue_type)
            vm_request.jira_issue_key = result["key"]
            vm_request.jira_issue_url = result["url"]
            await db.commit()
            await db.refresh(vm_request)
            await jira.close()
    except Exception as e:
        logger.warning(f"Failed to create Jira issue for request {vm_request.id}: {e}")

    # TODO: Phase 7 - Send "request received" email here

    return vm_request


@router.get("", response_model=VMRequestList)
async def list_vm_requests(
    status: Optional[RequestStatus] = None,
    requestor_email: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(VMRequest)

    if status:
        query = query.where(VMRequest.status == status)
    if requestor_email:
        query = query.where(VMRequest.requestor_email == requestor_email)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(VMRequest.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return VMRequestList(items=items, total=total)


@router.get("/{request_id}", response_model=VMRequestResponse)
async def get_vm_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VMRequest).where(VMRequest.id == request_id))
    vm_request = result.scalar_one_or_none()

    if not vm_request:
        raise HTTPException(status_code=404, detail="VM request not found")

    return vm_request


@router.post("/{request_id}/approve", response_model=VMRequestResponse)
async def approve_vm_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manual approval endpoint (admin use). Triggers provisioning and syncs to Jira."""
    result = await db.execute(select(VMRequest).where(VMRequest.id == request_id))
    vm_request = result.scalar_one_or_none()

    if not vm_request:
        raise HTTPException(status_code=404, detail="VM request not found")
    if vm_request.status != RequestStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Cannot approve request in '{vm_request.status.value}' state")

    vm_request.status = RequestStatus.APPROVED
    vm_request.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(vm_request)

    # Fire-and-forget background provisioning
    asyncio.create_task(provision_vm(request_id))

    # Sync approval to Jira (fire-and-forget)
    if vm_request.jira_issue_key:
        asyncio.create_task(
            _sync_jira_transition(vm_request.jira_issue_key, "approve", "Approved via admin UI")
        )

    return vm_request


@router.post("/{request_id}/reject", response_model=VMRequestResponse)
async def reject_vm_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manual rejection endpoint (admin use). Syncs to Jira."""
    result = await db.execute(select(VMRequest).where(VMRequest.id == request_id))
    vm_request = result.scalar_one_or_none()

    if not vm_request:
        raise HTTPException(status_code=404, detail="VM request not found")
    if vm_request.status != RequestStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Cannot reject request in '{vm_request.status.value}' state")

    vm_request.status = RequestStatus.REJECTED
    await db.commit()
    await db.refresh(vm_request)

    # Release phpIPAM IP allocation (fire-and-forget)
    if vm_request.phpipam_address_id:
        asyncio.create_task(_release_phpipam_ip(vm_request.phpipam_address_id))

    # Sync rejection to Jira (fire-and-forget)
    if vm_request.jira_issue_key:
        asyncio.create_task(
            _sync_jira_transition(vm_request.jira_issue_key, "reject", "Rejected via admin UI")
        )

    return vm_request


async def _sync_jira_transition(issue_key: str, action: str, comment: str) -> None:
    """Background task: transition Jira issue and add a comment."""
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
