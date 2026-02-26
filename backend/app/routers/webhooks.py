import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_effective_settings
from app.database import get_db
from app.models.vm_request import RequestStatus, VMRequest
from app.services.provisioning import provision_vm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/jira")
async def jira_webhook(
    request: Request,
    secret: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive Jira webhook events. Auto-approves/rejects VM requests based on issue transitions."""
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

    # Find the VM request linked to this Jira issue
    result = await db.execute(
        select(VMRequest).where(VMRequest.jira_issue_key == issue_key)
    )
    vm_request = result.scalar_one_or_none()
    if not vm_request:
        logger.debug(f"No VM request found for Jira issue {issue_key}")
        return {"status": "ignored", "reason": f"no matching request for {issue_key}"}

    # Only act on requests that are still pending
    if vm_request.status != RequestStatus.PENDING_APPROVAL:
        return {
            "status": "ignored",
            "reason": f"request {vm_request.id} is in '{vm_request.status.value}' state",
        }

    approve_status = jira_settings.get("JIRA_APPROVE_STATUS", "Approved")
    reject_status = jira_settings.get("JIRA_REJECT_STATUS", "Declined")

    if new_status.lower() == approve_status.lower():
        vm_request.status = RequestStatus.APPROVED
        vm_request.approved_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Auto-approved request {vm_request.id} via Jira webhook ({issue_key})")

        # Fire provisioning
        asyncio.create_task(provision_vm(vm_request.id))

        return {"status": "approved", "request_id": vm_request.id}

    elif new_status.lower() == reject_status.lower():
        vm_request.status = RequestStatus.REJECTED
        await db.commit()
        logger.info(f"Auto-rejected request {vm_request.id} via Jira webhook ({issue_key})")

        return {"status": "rejected", "request_id": vm_request.id}

    return {"status": "ignored", "reason": f"unhandled status: {new_status}"}
