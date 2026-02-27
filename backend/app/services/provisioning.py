import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_effective_settings, load_templates
from app.database import async_session
from app.models.os_template import OSTemplateMapping
from app.models.deployment import Deployment, DeploymentStatus
from app.models.vm_request import RequestStatus, VMRequest
from app.services.jira import get_jira_service
from app.services.node_selector import NodeSelector
from app.services.proxmox import ProxmoxService

logger = logging.getLogger(__name__)


async def _get_proxmox_service(db, environment_id: int | None = None) -> ProxmoxService:
    """Create a ProxmoxService from environment credentials, falling back to global settings."""
    if environment_id:
        from app.models.pve_environment import PVEEnvironment
        result = await db.execute(
            select(PVEEnvironment).where(PVEEnvironment.id == environment_id)
        )
        env = result.scalar_one_or_none()
        if env:
            return ProxmoxService(
                host=env.pve_host,
                user=env.pve_user,
                token_name=env.pve_token_name,
                token_value=env.pve_token_value,
                verify_ssl=env.pve_verify_ssl,
            )
        logger.warning(f"Environment {environment_id} not found, falling back to global settings")

    # Fallback to global settings (backward compat)
    settings = await get_effective_settings(db, group="proxmox")
    return ProxmoxService(
        host=settings["PVE_HOST"],
        user=settings["PVE_USER"],
        token_name=settings["PVE_TOKEN_NAME"],
        token_value=settings["PVE_TOKEN_VALUE"],
        verify_ssl=settings.get("PVE_VERIFY_SSL", "false").lower()
        in ("true", "1", "yes"),
    )


async def provision_vm(request_id: int) -> None:
    """Full provisioning pipeline. Runs as a background task.

    Steps:
    1. Update status to PROVISIONING
    2. Select target node (least_memory strategy)
    3. Get next available VMID
    4. Clone template to target node
    5. Wait for clone task to complete
    6. Resize CPU/RAM/disk
    7. Configure network (cloud-init for Linux)
    8. Start the VM
    9. Update status to COMPLETED (or PROVISIONING_FAILED on error)
    """
    async with async_session() as db:
        try:
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm_request = result.scalar_one_or_none()
            if not vm_request:
                logger.error(f"VM request {request_id} not found")
                return

            # Set status to PROVISIONING
            vm_request.status = RequestStatus.PROVISIONING
            vm_request.error_message = None
            await db.commit()

            # Jira comment: provisioning started
            await _jira_comment(
                db, vm_request.jira_issue_key,
                f"Provisioning started for VM '{vm_request.vm_name}'..."
            )

            # Initialize Proxmox service (environment-aware)
            pve = await _get_proxmox_service(db, vm_request.environment_id)

            # Resolve template config from DB, fallback to YAML
            tmpl_result = await db.execute(
                select(OSTemplateMapping).where(OSTemplateMapping.key == vm_request.os_template)
            )
            template_mapping = tmpl_result.scalar_one_or_none()

            if template_mapping:
                template_vmid = template_mapping.vmid
                source_node = template_mapping.node
                is_cloud_init = template_mapping.cloud_init
            else:
                templates = load_templates()
                template_config = templates.get(vm_request.os_template)
                if not template_config:
                    raise ValueError(f"Unknown OS template: {vm_request.os_template}")
                template_vmid = template_config["vmid"]
                source_node = template_config["node"]
                is_cloud_init = template_config.get("cloud_init", False)

            # Get node selection strategy
            all_settings = await get_effective_settings(db)
            strategy = all_settings.get("NODE_SELECTION_STRATEGY", "least_memory")

            # Step 1: Select target node
            selector = NodeSelector(pve)
            target_node = await asyncio.to_thread(selector.select_node, strategy)
            logger.info(f"Selected node {target_node} for VM {vm_request.vm_name}")

            # Step 2: Get next VMID
            new_vmid = await asyncio.to_thread(pve.get_next_vmid)
            logger.info(f"Allocated VMID {new_vmid} for VM {vm_request.vm_name}")

            # Step 3: Clone template
            upid = await asyncio.to_thread(
                pve.clone_vm,
                source_node,
                template_vmid,
                new_vmid,
                vm_request.vm_name,
                target_node,
                True,
            )
            logger.info(f"Clone task started: {upid}")

            # Step 4: Wait for clone to complete
            success = await asyncio.to_thread(
                pve.wait_for_task, source_node, upid, 600
            )
            if not success:
                raise RuntimeError(f"Clone task failed: {upid}")
            logger.info(f"Clone completed for VMID {new_vmid}")

            # Step 5: Resize VM
            await asyncio.to_thread(
                pve.resize_vm,
                target_node,
                new_vmid,
                vm_request.cpu_cores,
                vm_request.ram_mb,
                vm_request.disk_gb,
            )
            logger.info(
                f"Resized VMID {new_vmid}: {vm_request.cpu_cores}C / "
                f"{vm_request.ram_mb}MB / {vm_request.disk_gb}GB"
            )

            # Step 6: Configure cloud-init (Linux templates only)
            if is_cloud_init and vm_request.ip_address:
                await asyncio.to_thread(
                    pve.configure_cloud_init,
                    target_node,
                    new_vmid,
                    vm_request.ip_address,
                )
                logger.info(f"Configured cloud-init for VMID {new_vmid}")

            # Step 7: Start VM
            start_upid = await asyncio.to_thread(
                pve.start_vm, target_node, new_vmid
            )
            await asyncio.to_thread(
                pve.wait_for_task, target_node, start_upid, 120
            )
            logger.info(f"Started VMID {new_vmid}")

            # Step 8: Update DB with success
            vm_request.status = RequestStatus.COMPLETED
            vm_request.proxmox_vmid = new_vmid
            vm_request.proxmox_node = target_node
            vm_request.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(
                f"Provisioning complete for request {request_id}: "
                f"VMID {new_vmid} on {target_node}"
            )

            # Jira comment: provisioning complete
            await _jira_comment(
                db, vm_request.jira_issue_key,
                f"VM provisioned successfully.\n"
                f"VMID: {new_vmid}\n"
                f"Node: {target_node}\n"
                f"IP: {vm_request.ip_address or 'N/A'}"
            )

            # Send "VM ready" email (fire-and-forget)
            from app.services.email import send_vm_ready
            asyncio.create_task(send_vm_ready(request_id))

        except Exception as e:
            logger.exception(f"Provisioning failed for request {request_id}: {e}")
            async with async_session() as error_db:
                result = await error_db.execute(
                    select(VMRequest).where(VMRequest.id == request_id)
                )
                vm_request = result.scalar_one_or_none()
                if vm_request:
                    vm_request.status = RequestStatus.PROVISIONING_FAILED
                    vm_request.error_message = str(e)[:1000]
                    await error_db.commit()

                    # Jira comment: provisioning failed
                    await _jira_comment(
                        error_db, vm_request.jira_issue_key,
                        f"Provisioning failed: {str(e)[:500]}"
                    )

                    # Send "provisioning failed" email (fire-and-forget)
                    from app.services.email import send_provisioning_failed
                    asyncio.create_task(send_provisioning_failed(request_id))


async def _provision_single_vm(db, vm_request: VMRequest, pve: ProxmoxService) -> None:
    """Provision a single VM. Used by both provision_vm and provision_deployment."""
    # Resolve template config from DB, fallback to YAML
    tmpl_result = await db.execute(
        select(OSTemplateMapping).where(OSTemplateMapping.key == vm_request.os_template)
    )
    template_mapping = tmpl_result.scalar_one_or_none()

    if template_mapping:
        template_vmid = template_mapping.vmid
        source_node = template_mapping.node
        is_cloud_init = template_mapping.cloud_init
    else:
        templates = load_templates()
        template_config = templates.get(vm_request.os_template)
        if not template_config:
            raise ValueError(f"Unknown OS template: {vm_request.os_template}")
        template_vmid = template_config["vmid"]
        source_node = template_config["node"]
        is_cloud_init = template_config.get("cloud_init", False)

    # Get node selection strategy
    all_settings = await get_effective_settings(db)
    strategy = all_settings.get("NODE_SELECTION_STRATEGY", "least_memory")

    # Select target node
    selector = NodeSelector(pve)
    target_node = await asyncio.to_thread(selector.select_node, strategy)
    logger.info(f"Selected node {target_node} for VM {vm_request.vm_name}")

    # Get next VMID
    new_vmid = await asyncio.to_thread(pve.get_next_vmid)
    logger.info(f"Allocated VMID {new_vmid} for VM {vm_request.vm_name}")

    # Clone template
    upid = await asyncio.to_thread(
        pve.clone_vm, source_node, template_vmid, new_vmid,
        vm_request.vm_name, target_node, True,
    )
    logger.info(f"Clone task started: {upid}")

    # Wait for clone
    success = await asyncio.to_thread(pve.wait_for_task, source_node, upid, 600)
    if not success:
        raise RuntimeError(f"Clone task failed: {upid}")
    logger.info(f"Clone completed for VMID {new_vmid}")

    # Resize VM
    await asyncio.to_thread(
        pve.resize_vm, target_node, new_vmid,
        vm_request.cpu_cores, vm_request.ram_mb, vm_request.disk_gb,
    )
    logger.info(
        f"Resized VMID {new_vmid}: {vm_request.cpu_cores}C / "
        f"{vm_request.ram_mb}MB / {vm_request.disk_gb}GB"
    )

    # Configure cloud-init
    if is_cloud_init and vm_request.ip_address:
        await asyncio.to_thread(
            pve.configure_cloud_init, target_node, new_vmid, vm_request.ip_address,
        )
        logger.info(f"Configured cloud-init for VMID {new_vmid}")

    # Start VM
    start_upid = await asyncio.to_thread(pve.start_vm, target_node, new_vmid)
    await asyncio.to_thread(pve.wait_for_task, target_node, start_upid, 120)
    logger.info(f"Started VMID {new_vmid}")

    # Update DB
    vm_request.status = RequestStatus.COMPLETED
    vm_request.proxmox_vmid = new_vmid
    vm_request.proxmox_node = target_node
    vm_request.completed_at = datetime.now(timezone.utc)


async def provision_deployment(deployment_id: int) -> None:
    """Provision all VMs in a deployment sequentially. Runs as a background task."""
    async with async_session() as db:
        try:
            from sqlalchemy.orm import selectinload
            result = await db.execute(
                select(Deployment)
                .options(selectinload(Deployment.vm_requests))
                .where(Deployment.id == deployment_id)
            )
            deployment = result.scalar_one_or_none()
            if not deployment:
                logger.error(f"Deployment {deployment_id} not found")
                return

            deployment.status = DeploymentStatus.PROVISIONING
            await db.commit()

            # Initialize Proxmox service once for the deployment
            pve = await _get_proxmox_service(db, deployment.environment_id)

            completed = 0
            failed = 0

            for vm_req in deployment.vm_requests:
                try:
                    vm_req.status = RequestStatus.PROVISIONING
                    vm_req.error_message = None
                    await db.commit()

                    # Jira comment per VM
                    await _jira_comment(
                        db, deployment.jira_issue_key,
                        f"Provisioning VM '{vm_req.vm_name}'...",
                    )

                    await _provision_single_vm(db, vm_req, pve)
                    await db.commit()
                    completed += 1

                    await _jira_comment(
                        db, deployment.jira_issue_key,
                        f"VM '{vm_req.vm_name}' provisioned: VMID {vm_req.proxmox_vmid} "
                        f"on {vm_req.proxmox_node}, IP: {vm_req.ip_address or 'N/A'}",
                    )

                    # Send "VM ready" email per VM
                    from app.services.email import send_vm_ready
                    asyncio.create_task(send_vm_ready(vm_req.id))

                except Exception as e:
                    logger.exception(
                        f"Failed to provision VM {vm_req.vm_name} "
                        f"in deployment {deployment_id}: {e}"
                    )
                    vm_req.status = RequestStatus.PROVISIONING_FAILED
                    vm_req.error_message = str(e)[:1000]
                    await db.commit()
                    failed += 1

                    await _jira_comment(
                        db, deployment.jira_issue_key,
                        f"VM '{vm_req.vm_name}' provisioning failed: {str(e)[:500]}",
                    )

            # Determine final deployment status
            total = len(deployment.vm_requests)
            if completed == total:
                deployment.status = DeploymentStatus.COMPLETED
                deployment.completed_at = datetime.now(timezone.utc)
            elif failed == total:
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = "All VMs failed to provision"
            else:
                deployment.status = DeploymentStatus.PARTIALLY_COMPLETED
                deployment.completed_at = datetime.now(timezone.utc)
                deployment.error_message = f"{failed}/{total} VMs failed"

            await db.commit()

            # Final Jira summary comment
            await _jira_comment(
                db, deployment.jira_issue_key,
                f"Deployment complete: {completed}/{total} VMs provisioned successfully"
                + (f" ({failed} failed)" if failed else ""),
            )

            logger.info(
                f"Deployment {deployment_id} done: "
                f"{completed} completed, {failed} failed out of {total}"
            )

        except Exception as e:
            logger.exception(f"Deployment provisioning failed for {deployment_id}: {e}")
            async with async_session() as error_db:
                result = await error_db.execute(
                    select(Deployment).where(Deployment.id == deployment_id)
                )
                deployment = result.scalar_one_or_none()
                if deployment:
                    deployment.status = DeploymentStatus.FAILED
                    deployment.error_message = str(e)[:1000]
                    await error_db.commit()


async def _jira_comment(db, issue_key: str | None, comment: str) -> None:
    """Post a comment to Jira. Silently swallows errors."""
    if not issue_key:
        return
    try:
        jira = await get_jira_service(db)
        if jira:
            await jira.add_comment(issue_key, comment)
            await jira.close()
    except Exception as e:
        logger.warning(f"Failed to post Jira comment on {issue_key}: {e}")
