import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthenticatedUser, get_current_user, require_admin
from app.database import get_db
from app.models.decom_request import DecomRequest, DecomStatus
from app.models.deployment import Deployment
from app.models.vm_request import RequestStatus, VMRequest
from app.schemas.decom_request import DecomRequestCreate, DecomRequestList, DecomRequestResponse
from app.services.jira import get_jira_service, get_jira_settings
from app.services.phpipam import get_phpipam_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decom-requests", tags=["decom-requests"])


def _to_response(decom: DecomRequest) -> DecomRequestResponse:
    """Convert a DecomRequest ORM object to a response with denormalized resource info."""
    resource_name = None
    resource_type = None
    ip_address = None

    if decom.vm_request:
        resource_name = decom.vm_request.vm_name
        resource_type = decom.vm_request.resource_type
        ip_address = decom.vm_request.ip_address
    elif decom.deployment:
        resource_name = decom.deployment.name
        resource_type = decom.deployment.resource_type

    return DecomRequestResponse(
        id=decom.id,
        vm_request_id=decom.vm_request_id,
        deployment_id=decom.deployment_id,
        reason=decom.reason,
        requestor_name=decom.requestor_name,
        requestor_email=decom.requestor_email,
        review_date=decom.review_date,
        notes=decom.notes,
        status=decom.status,
        jira_issue_key=decom.jira_issue_key,
        jira_issue_url=decom.jira_issue_url,
        error_message=decom.error_message,
        created_at=decom.created_at,
        updated_at=decom.updated_at,
        approved_at=decom.approved_at,
        completed_at=decom.completed_at,
        resource_name=resource_name,
        resource_type=resource_type,
        ip_address=ip_address,
    )


@router.post("", response_model=DecomRequestResponse, status_code=201)
async def create_decom_request(
    payload: DecomRequestCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate target resource exists and is in a decomm-able state
    if payload.vm_request_id:
        result = await db.execute(
            select(VMRequest).where(VMRequest.id == payload.vm_request_id)
        )
        vm = result.scalar_one_or_none()
        if not vm:
            raise HTTPException(status_code=404, detail="VM request not found")
        if vm.status not in (RequestStatus.COMPLETED, RequestStatus.PROVISIONING_FAILED):
            raise HTTPException(
                status_code=400,
                detail=f"Can only decommission completed or failed resources (current: '{vm.status.value}')",
            )
        resource_label = f"{'CT' if vm.resource_type == 'lxc' else 'VM'}: {vm.vm_name}"

        # Check no active decom already exists
        existing = await db.execute(
            select(DecomRequest).where(
                DecomRequest.vm_request_id == payload.vm_request_id,
                DecomRequest.status.not_in([DecomStatus.COMPLETED, DecomStatus.CANCELLED, DecomStatus.REJECTED]),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="An active decom request already exists for this resource")

    elif payload.deployment_id:
        result = await db.execute(
            select(Deployment).where(Deployment.id == payload.deployment_id)
        )
        dep = result.scalar_one_or_none()
        if not dep:
            raise HTTPException(status_code=404, detail="Deployment not found")
        resource_label = f"Deployment: {dep.name}"

        # Check no active decom already exists
        existing = await db.execute(
            select(DecomRequest).where(
                DecomRequest.deployment_id == payload.deployment_id,
                DecomRequest.status.not_in([DecomStatus.COMPLETED, DecomStatus.CANCELLED, DecomStatus.REJECTED]),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="An active decom request already exists for this deployment")

    decom = DecomRequest(
        vm_request_id=payload.vm_request_id,
        deployment_id=payload.deployment_id,
        reason=payload.reason,
        requestor_name=user.name,
        requestor_email=user.email,
        review_date=payload.review_date,
        status=DecomStatus.PENDING_APPROVAL,
    )
    db.add(decom)
    await db.commit()
    await db.refresh(decom)

    # Create Jira issue (non-blocking)
    try:
        jira = await get_jira_service(db)
        if jira:
            jira_settings = await get_jira_settings(db)
            project_key = jira_settings.get("JIRA_PROJECT_KEY", "INFRA")
            issue_type = jira_settings.get("JIRA_ISSUE_TYPE", "Service Request")

            summary = f"Decom Request: {resource_label}"
            desc_lines = [
                f"Requestor: {decom.requestor_name} ({decom.requestor_email})",
                f"Resource: {resource_label}",
                f"Reason: {decom.reason}",
            ]
            if decom.review_date:
                desc_lines.append(f"Preferred Review Date: {decom.review_date.strftime('%Y-%m-%d')}")
            description = "\n".join(desc_lines)

            result = await jira.create_issue(project_key, summary, description, issue_type)
            decom.jira_issue_key = result["key"]
            decom.jira_issue_url = result["url"]
            await db.commit()
            await db.refresh(decom)
            await jira.close()
    except Exception as e:
        logger.warning(f"Failed to create Jira issue for decom request {decom.id}: {e}")

    # Send "decom request received" email (fire-and-forget)
    asyncio.create_task(_send_decom_email(decom.id, "received"))

    return _to_response(decom)


@router.get("", response_model=DecomRequestList)
async def list_decom_requests(
    status: Optional[DecomStatus] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(DecomRequest)

    # Non-admin users can only see their own
    if not user.is_admin:
        query = query.where(DecomRequest.requestor_email == user.email)

    if status:
        query = query.where(DecomRequest.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(DecomRequest.created_at.desc())
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    items = result.scalars().all()

    return DecomRequestList(
        items=[_to_response(d) for d in items],
        total=total,
    )


@router.get("/{decom_id}", response_model=DecomRequestResponse)
async def get_decom_request(
    decom_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DecomRequest).where(DecomRequest.id == decom_id))
    decom = result.scalar_one_or_none()
    if not decom:
        raise HTTPException(status_code=404, detail="Decom request not found")
    return _to_response(decom)


@router.post("/{decom_id}/approve", response_model=DecomRequestResponse)
async def approve_decom_request(
    decom_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin approves the decom request. Auto-triggers destroy pipeline."""
    decom = await _get_decom_or_404(decom_id, db)
    if decom.status != DecomStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Cannot approve in '{decom.status.value}' state")

    decom.status = DecomStatus.APPROVED
    decom.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(decom)

    # Sync to Jira
    if decom.jira_issue_key:
        asyncio.create_task(_sync_jira_transition(decom.jira_issue_key, "approve", "Decom approved via admin UI"))

    asyncio.create_task(_send_decom_email(decom.id, "approved"))
    # Auto-execute: destroy resources, release IPs, mark completed
    asyncio.create_task(execute_decom(decom.id))
    return _to_response(decom)


@router.post("/{decom_id}/reject", response_model=DecomRequestResponse)
async def reject_decom_request(
    decom_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin rejects the decom request. Resource stays."""
    decom = await _get_decom_or_404(decom_id, db)
    if decom.status != DecomStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Cannot reject in '{decom.status.value}' state")

    decom.status = DecomStatus.REJECTED
    await db.commit()
    await db.refresh(decom)

    if decom.jira_issue_key:
        asyncio.create_task(_sync_jira_transition(decom.jira_issue_key, "reject", "Decom rejected via admin UI"))

    asyncio.create_task(_send_decom_email(decom.id, "rejected"))
    return _to_response(decom)


@router.post("/{decom_id}/start", response_model=DecomRequestResponse)
async def start_decom(
    decom_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin marks decom as in-progress (actively tearing down)."""
    decom = await _get_decom_or_404(decom_id, db)
    if decom.status != DecomStatus.APPROVED:
        raise HTTPException(status_code=400, detail=f"Cannot start in '{decom.status.value}' state")

    decom.status = DecomStatus.IN_PROGRESS
    await db.commit()
    await db.refresh(decom)

    if decom.jira_issue_key:
        asyncio.create_task(_jira_comment(decom.jira_issue_key, "Decommissioning started"))

    return _to_response(decom)


@router.post("/{decom_id}/complete", response_model=DecomRequestResponse)
async def complete_decom(
    decom_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Auto-destroy resources on Proxmox, release phpIPAM IPs, mark as decommissioned."""
    decom = await _get_decom_or_404(decom_id, db)
    if decom.status not in (DecomStatus.APPROVED, DecomStatus.IN_PROGRESS):
        raise HTTPException(status_code=400, detail=f"Cannot complete in '{decom.status.value}' state")

    # Collect all VMs to destroy
    vms_to_destroy: list[VMRequest] = []
    if decom.vm_request_id:
        result = await db.execute(select(VMRequest).where(VMRequest.id == decom.vm_request_id))
        vm = result.scalar_one_or_none()
        if vm:
            vms_to_destroy.append(vm)
    elif decom.deployment_id:
        result = await db.execute(
            select(VMRequest).where(VMRequest.deployment_id == decom.deployment_id)
        )
        vms_to_destroy = list(result.scalars().all())

    # Destroy each resource on Proxmox, then release phpIPAM IP
    for vm in vms_to_destroy:
        # Step 1: Destroy on Proxmox (stop + delete)
        await _destroy_on_proxmox(db, vm, decom.id)

        # Step 2: Release phpIPAM IP
        if vm.phpipam_address_id:
            try:
                ipam = await get_phpipam_service(db)
                if ipam:
                    await ipam.release_ip(vm.phpipam_address_id)
                    await ipam.close()
                    logger.info(f"Released phpIPAM address ID {vm.phpipam_address_id} for decom {decom.id}")
            except Exception as e:
                logger.warning(f"Failed to release phpIPAM address {vm.phpipam_address_id}: {e}")

        vm.status = RequestStatus.DECOMMISSIONED

    decom.status = DecomStatus.COMPLETED
    decom.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(decom)

    if decom.jira_issue_key:
        asyncio.create_task(_jira_comment(decom.jira_issue_key, "Decommissioning complete. Resources destroyed, IPs released."))

    asyncio.create_task(_send_decom_email(decom.id, "completed"))
    return _to_response(decom)


@router.post("/{decom_id}/cancel", response_model=DecomRequestResponse)
async def cancel_decom(
    decom_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending decom request."""
    decom = await _get_decom_or_404(decom_id, db)
    if decom.status not in (DecomStatus.PENDING_APPROVAL, DecomStatus.APPROVED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel in '{decom.status.value}' state")

    # Non-admins can only cancel their own
    if not user.is_admin and decom.requestor_email != user.email:
        raise HTTPException(status_code=403, detail="You can only cancel your own decom requests")

    decom.status = DecomStatus.CANCELLED
    await db.commit()
    await db.refresh(decom)

    if decom.jira_issue_key:
        asyncio.create_task(_jira_comment(decom.jira_issue_key, "Decom request cancelled"))

    return _to_response(decom)


@router.delete("/{decom_id}", status_code=204)
async def delete_decom_request(
    decom_id: int,
    user: AuthenticatedUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a decom request record (admin only)."""
    decom = await _get_decom_or_404(decom_id, db)
    await db.delete(decom)
    await db.commit()
    logger.info(f"Admin {user.email} deleted decom request {decom_id}")


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_decom_or_404(decom_id: int, db: AsyncSession) -> DecomRequest:
    result = await db.execute(select(DecomRequest).where(DecomRequest.id == decom_id))
    decom = result.scalar_one_or_none()
    if not decom:
        raise HTTPException(status_code=404, detail="Decom request not found")
    return decom


async def _destroy_on_proxmox(db, vm: VMRequest, decom_id: int) -> None:
    """Stop and destroy a VM/CT on Proxmox. Non-fatal: logs warnings on failure."""
    import asyncio as _asyncio

    vmid_str = vm.hypervisor_vm_id or (str(vm.proxmox_vmid) if vm.proxmox_vmid else None)
    node = vm.hypervisor_host or vm.proxmox_node
    if not vmid_str or not node:
        logger.warning(f"Decom {decom_id}: VM {vm.vm_name} has no hypervisor ID/host — skipping destroy")
        return

    vmid = int(vmid_str)
    is_lxc = vm.resource_type == "lxc"

    try:
        from app.services.provisioning import _get_proxmox_service
        from app.models.environment import Environment

        env = None
        if vm.environment_id:
            result = await db.execute(
                select(Environment).where(Environment.id == vm.environment_id)
            )
            env = result.scalar_one_or_none()

        pve = await _get_proxmox_service(db, env)
        resource_label = f"{'CT' if is_lxc else 'VM'} {vmid} ({vm.vm_name}) on {node}"

        # Stop the resource first
        try:
            if is_lxc:
                upid = await _asyncio.to_thread(pve.stop_lxc, node, vmid)
            else:
                upid = await _asyncio.to_thread(pve.stop_vm, node, vmid)
            await _asyncio.to_thread(pve.wait_for_task, node, upid, timeout=120)
            logger.info(f"Decom {decom_id}: Stopped {resource_label}")
        except Exception as e:
            # May already be stopped — continue to destroy
            logger.info(f"Decom {decom_id}: Stop {resource_label} returned: {e} (may already be stopped)")

        # Destroy the resource
        if is_lxc:
            upid = await _asyncio.to_thread(pve.destroy_lxc, node, vmid)
        else:
            upid = await _asyncio.to_thread(pve.destroy_vm, node, vmid)
        await _asyncio.to_thread(pve.wait_for_task, node, upid, timeout=120)
        logger.info(f"Decom {decom_id}: Destroyed {resource_label}")

    except Exception as e:
        logger.warning(f"Decom {decom_id}: Failed to destroy {vm.vm_name} (VMID {vmid}): {e}")


async def _jira_comment(issue_key: str, comment: str) -> None:
    """Background task: add a comment to a Jira issue."""
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


async def execute_decom(decom_id: int) -> None:
    """Full auto-decom pipeline: in_progress → destroy resources → release IPs → completed.

    Called as a background task after Jira approval (webhook) or admin approval.
    Uses its own DB session so it can run independently.
    """
    from app.database import async_session

    try:
        async with async_session() as db:
            result = await db.execute(select(DecomRequest).where(DecomRequest.id == decom_id))
            decom = result.scalar_one_or_none()
            if not decom or decom.status != DecomStatus.APPROVED:
                logger.warning(f"execute_decom({decom_id}): not found or not in approved state")
                return

            # Move to in_progress
            decom.status = DecomStatus.IN_PROGRESS
            await db.commit()

            if decom.jira_issue_key:
                await _jira_comment(decom.jira_issue_key, "Decommissioning started (auto)")

            # Collect VMs to destroy
            vms_to_destroy: list[VMRequest] = []
            if decom.vm_request_id:
                result = await db.execute(select(VMRequest).where(VMRequest.id == decom.vm_request_id))
                vm = result.scalar_one_or_none()
                if vm:
                    vms_to_destroy.append(vm)
            elif decom.deployment_id:
                result = await db.execute(
                    select(VMRequest).where(VMRequest.deployment_id == decom.deployment_id)
                )
                vms_to_destroy = list(result.scalars().all())

            # Destroy each resource on Proxmox, then release phpIPAM IP
            for vm in vms_to_destroy:
                await _destroy_on_proxmox(db, vm, decom.id)

                if vm.phpipam_address_id:
                    try:
                        ipam = await get_phpipam_service(db)
                        if ipam:
                            await ipam.release_ip(vm.phpipam_address_id)
                            await ipam.close()
                            logger.info(f"Released phpIPAM address ID {vm.phpipam_address_id} for decom {decom.id}")
                    except Exception as e:
                        logger.warning(f"Failed to release phpIPAM address {vm.phpipam_address_id}: {e}")

                vm.status = RequestStatus.DECOMMISSIONED

            # Mark completed
            decom.status = DecomStatus.COMPLETED
            decom.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"Auto-decom {decom_id} completed successfully")

            if decom.jira_issue_key:
                await _jira_comment(decom.jira_issue_key, "Decommissioning complete. Resources destroyed, IPs released.")

            await _send_decom_email(decom.id, "completed")

    except Exception as e:
        logger.error(f"execute_decom({decom_id}) failed: {e}")
        # Try to record the error
        try:
            async with async_session() as db:
                result = await db.execute(select(DecomRequest).where(DecomRequest.id == decom_id))
                decom = result.scalar_one_or_none()
                if decom:
                    decom.error_message = str(e)
                    await db.commit()
        except Exception:
            pass


async def _send_decom_email(decom_id: int, event: str) -> None:
    """Background task: send decom-related email to requestor."""
    from app.database import async_session
    from app.services.email import get_email_service, render_template

    try:
        async with async_session() as db:
            svc = await get_email_service(db)
            if not svc:
                return

            result = await db.execute(select(DecomRequest).where(DecomRequest.id == decom_id))
            decom = result.scalar_one_or_none()
            if not decom:
                return

            # Build resource name for email context
            resource_name = "Unknown Resource"
            if decom.vm_request:
                resource_name = decom.vm_request.vm_name
            elif decom.deployment:
                resource_name = decom.deployment.name

            subjects = {
                "received": f"Decom Request Received: {resource_name}",
                "approved": f"Decom Request Approved: {resource_name}",
                "rejected": f"Decom Request Rejected: {resource_name}",
                "completed": f"Decommissioning Complete: {resource_name}",
            }

            template_name = f"decom_{event}.html"
            html = render_template(
                template_name,
                decom=decom,
                resource_name=resource_name,
            )
            await svc.send(
                to=decom.requestor_email,
                subject=subjects.get(event, f"Decom Update: {resource_name}"),
                html_body=html,
            )
    except Exception as e:
        logger.warning(f"Failed to send decom '{event}' email for decom request {decom_id}: {e}")
