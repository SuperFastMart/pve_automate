import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_effective_settings
from app.database import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.vm_request import RequestStatus, VMRequest
from app.services.provisioning import provision_deployment, provision_vm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/jira")
async def jira_webhook(
    request: Request,
    secret: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive Jira webhook events. Auto-approves/rejects VM requests and deployments based on issue transitions."""
    # Validate webhook secret if configured
    jira_settings = await get_effective_settings(db, group="jira")
    expected_secret = jira_settings.get("JIRA_WEBHOOK_SECRET", "")
    if expected_secret and secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()

    # We only care about issue_updated events with status changes
    event = body.get("webhookEvent", "")
    if event not in ("jira:issue_updated",):
        return {"status": "ignored", "reason": f"unhandled event: {event}"}

    # Extract issue key
    issue = body.get("issue", {})
    issue_key = issue.get("key", "")
    if not issue_key:
        return {"status": "ignored", "reason": "no issue key"}

    # Check changelog for status transitions
    changelog = body.get("changelog", {})
    items = changelog.get("items", [])

    new_status = None
    for item in items:
        if item.get("field") == "status":
            new_status = item.get("toString", "")
            break

    if not new_status:
        return {"status": "ignored", "reason": "no status change"}

    approve_status = jira_settings.get("JIRA_APPROVE_STATUS", "Approved")
    reject_status = jira_settings.get("JIRA_REJECT_STATUS", "Declined")

    # Try individual VM request first
    result = await db.execute(
        select(VMRequest).where(VMRequest.jira_issue_key == issue_key)
    )
    vm_request = result.scalar_one_or_none()
    if vm_request:
        return await _handle_vm_request_webhook(
            db, vm_request, issue_key, new_status, approve_status, reject_status
        )

    # Try deployment
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vm_requests))
        .where(Deployment.jira_issue_key == issue_key)
    )
    deployment = result.scalar_one_or_none()
    if deployment:
        return await _handle_deployment_webhook(
            db, deployment, issue_key, new_status, approve_status, reject_status
        )

    logger.debug(f"No VM request or deployment found for Jira issue {issue_key}")
    return {"status": "ignored", "reason": f"no matching request for {issue_key}"}


async def _handle_vm_request_webhook(
    db: AsyncSession,
    vm_request: VMRequest,
    issue_key: str,
    new_status: str,
    approve_status: str,
    reject_status: str,
):
    """Handle a Jira webhook for an individual VM request."""
    if vm_request.status != RequestStatus.PENDING_APPROVAL:
        return {
            "status": "ignored",
            "reason": f"request {vm_request.id} is in '{vm_request.status.value}' state",
        }

    if new_status.lower() == approve_status.lower():
        vm_request.status = RequestStatus.APPROVED
        vm_request.approved_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Auto-approved request {vm_request.id} via Jira webhook ({issue_key})")

        asyncio.create_task(provision_vm(vm_request.id))
        return {"status": "approved", "request_id": vm_request.id}

    elif new_status.lower() == reject_status.lower():
        vm_request.status = RequestStatus.REJECTED
        await db.commit()
        logger.info(f"Auto-rejected request {vm_request.id} via Jira webhook ({issue_key})")

        if vm_request.phpipam_address_id:
            from app.routers.vm_requests import _release_phpipam_ip
            asyncio.create_task(_release_phpipam_ip(vm_request.phpipam_address_id))

        from app.services.email import send_request_rejected
        asyncio.create_task(send_request_rejected(vm_request.id))
        return {"status": "rejected", "request_id": vm_request.id}

    return {"status": "ignored", "reason": f"unhandled status: {new_status}"}


async def _handle_deployment_webhook(
    db: AsyncSession,
    deployment: Deployment,
    issue_key: str,
    new_status: str,
    approve_status: str,
    reject_status: str,
):
    """Handle a Jira webhook for a deployment."""
    if deployment.status != DeploymentStatus.PENDING_APPROVAL:
        return {
            "status": "ignored",
            "reason": f"deployment {deployment.id} is in '{deployment.status.value}' state",
        }

    if new_status.lower() == approve_status.lower():
        now = datetime.now(timezone.utc)
        deployment.status = DeploymentStatus.APPROVED
        deployment.approved_at = now

        for vm_req in deployment.vm_requests:
            vm_req.status = RequestStatus.APPROVED
            vm_req.approved_at = now

        await db.commit()
        logger.info(f"Auto-approved deployment {deployment.id} via Jira webhook ({issue_key})")

        asyncio.create_task(provision_deployment(deployment.id))
        return {"status": "approved", "deployment_id": deployment.id}

    elif new_status.lower() == reject_status.lower():
        deployment.status = DeploymentStatus.REJECTED

        for vm_req in deployment.vm_requests:
            vm_req.status = RequestStatus.REJECTED
            if vm_req.phpipam_address_id:
                from app.routers.vm_requests import _release_phpipam_ip
                asyncio.create_task(_release_phpipam_ip(vm_req.phpipam_address_id))

        await db.commit()
        logger.info(f"Auto-rejected deployment {deployment.id} via Jira webhook ({issue_key})")

        from app.services.email import send_request_rejected
        if deployment.vm_requests:
            asyncio.create_task(send_request_rejected(deployment.vm_requests[0].id))

        return {"status": "rejected", "deployment_id": deployment.id}

    return {"status": "ignored", "reason": f"unhandled status: {new_status}"}
