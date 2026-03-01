import asyncio
import logging
from datetime import datetime, timezone
from typing import NamedTuple

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


class TemplateInfo(NamedTuple):
    vmid: int | None  # Proxmox template VMID
    node: str | None  # Proxmox source node
    template_ref: str | None  # vSphere template name
    cloud_init: bool


async def _get_environment(db, environment_id: int | None):
    """Fetch environment record, or None if not specified / not found."""
    if not environment_id:
        return None
    from app.models.environment import Environment
    result = await db.execute(
        select(Environment).where(Environment.id == environment_id)
    )
    return result.scalar_one_or_none()


async def _get_proxmox_service(db, env=None) -> ProxmoxService:
    """Create a ProxmoxService from environment or global settings."""
    if env:
        return ProxmoxService(
            host=env.pve_host,
            user=env.pve_user,
            token_name=env.pve_token_name,
            token_value=env.pve_token_value,
            verify_ssl=env.pve_verify_ssl,
        )
    # Fallback to global settings (backward compat)
    settings = await get_effective_settings(db, group="proxmox")
    return ProxmoxService(
        host=settings["PVE_HOST"],
        user=settings["PVE_USER"],
        token_name=settings["PVE_TOKEN_NAME"],
        token_value=settings["PVE_TOKEN_VALUE"],
        verify_ssl=settings.get("PVE_VERIFY_SSL", "false").lower() in ("true", "1", "yes"),
    )


def _get_vsphere_service(env):
    """Create a VSphereService from environment credentials."""
    from app.services.vsphere import VSphereService
    return VSphereService(
        host=env.vsphere_host,
        user=env.vsphere_user,
        password=env.vsphere_password,
        port=env.vsphere_port,
        verify_ssl=env.vsphere_verify_ssl,
        datacenter=env.vsphere_datacenter,
        cluster=env.vsphere_cluster,
    )


async def _resolve_template(db, template_key: str, environment_id: int | None = None) -> TemplateInfo:
    """Resolve a template mapping, preferring environment-specific over global."""
    if environment_id:
        result = await db.execute(
            select(OSTemplateMapping)
            .where(OSTemplateMapping.key == template_key)
            .where(OSTemplateMapping.environment_id == environment_id)
        )
        mapping = result.scalar_one_or_none()
        if mapping:
            return TemplateInfo(mapping.vmid, mapping.node, mapping.template_ref, mapping.cloud_init)

    # Fall back to global (environment_id IS NULL)
    result = await db.execute(
        select(OSTemplateMapping)
        .where(OSTemplateMapping.key == template_key)
        .where(OSTemplateMapping.environment_id.is_(None))
    )
    mapping = result.scalar_one_or_none()
    if mapping:
        return TemplateInfo(mapping.vmid, mapping.node, mapping.template_ref, mapping.cloud_init)

    # Final fallback to YAML
    templates = load_templates()
    template_config = templates.get(template_key)
    if not template_config:
        raise ValueError(f"Unknown OS template: {template_key}")
    return TemplateInfo(
        template_config["vmid"], template_config["node"],
        None, template_config.get("cloud_init", False),
    )


# ── Proxmox provisioning ────────────────────────────────────────

async def _provision_proxmox_vm(db, vm_request: VMRequest, pve: ProxmoxService) -> None:
    """Provision a single VM on Proxmox."""
    tmpl = await _resolve_template(db, vm_request.os_template, vm_request.environment_id)

    all_settings = await get_effective_settings(db)
    strategy = all_settings.get("NODE_SELECTION_STRATEGY", "least_memory")

    selector = NodeSelector(pve)
    target_node = await asyncio.to_thread(selector.select_node, strategy)
    logger.info(f"Selected node {target_node} for VM {vm_request.vm_name}")

    new_vmid = await asyncio.to_thread(pve.get_next_vmid)
    logger.info(f"Allocated VMID {new_vmid} for VM {vm_request.vm_name}")

    upid = await asyncio.to_thread(
        pve.clone_vm, tmpl.node, tmpl.vmid, new_vmid,
        vm_request.vm_name, target_node, True,
    )
    logger.info(f"Clone task started: {upid}")

    success = await asyncio.to_thread(pve.wait_for_task, tmpl.node, upid, 600)
    if not success:
        raise RuntimeError(f"Clone task failed: {upid}")
    logger.info(f"Clone completed for VMID {new_vmid}")

    await asyncio.to_thread(
        pve.resize_vm, target_node, new_vmid,
        vm_request.cpu_cores, vm_request.ram_mb, vm_request.disk_gb,
    )
    logger.info(f"Resized VMID {new_vmid}: {vm_request.cpu_cores}C / {vm_request.ram_mb}MB / {vm_request.disk_gb}GB")

    if tmpl.cloud_init and vm_request.ip_address:
        await asyncio.to_thread(
            pve.configure_cloud_init, target_node, new_vmid, vm_request.ip_address,
        )
        logger.info(f"Configured cloud-init for VMID {new_vmid}")

    start_upid = await asyncio.to_thread(pve.start_vm, target_node, new_vmid)
    await asyncio.to_thread(pve.wait_for_task, target_node, start_upid, 120)
    logger.info(f"Started VMID {new_vmid}")

    # Update DB — legacy + generic fields
    vm_request.status = RequestStatus.COMPLETED
    vm_request.proxmox_vmid = new_vmid
    vm_request.proxmox_node = target_node
    vm_request.hypervisor_vm_id = str(new_vmid)
    vm_request.hypervisor_host = target_node
    vm_request.completed_at = datetime.now(timezone.utc)


# ── vSphere provisioning ────────────────────────────────────────

async def _provision_vsphere_vm(db, vm_request: VMRequest, env) -> None:
    """Provision a single VM on ESXi / vCenter."""
    from app.services.vsphere import VSphereService

    tmpl = await _resolve_template(db, vm_request.os_template, vm_request.environment_id)
    template_name = tmpl.template_ref
    if not template_name:
        raise ValueError(
            f"Template '{vm_request.os_template}' has no template_ref for vSphere. "
            f"Configure a template mapping with template_ref for this environment."
        )

    vs = _get_vsphere_service(env)
    try:
        # Select target host
        hosts = await asyncio.to_thread(vs.get_hosts)
        connected = [h for h in hosts if h["connection_state"] == "connected"]
        if not connected:
            raise RuntimeError("No connected ESXi hosts found")

        # Pick host with most free memory
        target_host = min(
            connected,
            key=lambda h: h["memory_used_bytes"] / max(h["memory_total_bytes"], 1),
        )["name"]
        logger.info(f"Selected host {target_host} for VM {vm_request.vm_name}")

        # Clone template (CPU/RAM set during clone)
        moref = await asyncio.to_thread(
            vs.clone_vm, template_name, vm_request.vm_name,
            target_host, vm_request.cpu_cores, vm_request.ram_mb,
        )
        logger.info(f"Cloned template '{template_name}' → '{vm_request.vm_name}' (MoRef: {moref})")

        # Resize disk (if needed — clone already set CPU/RAM)
        await asyncio.to_thread(
            vs.resize_vm, vm_request.vm_name,
            vm_request.cpu_cores, vm_request.ram_mb, vm_request.disk_gb,
        )
        logger.info(f"Resized {vm_request.vm_name}: {vm_request.cpu_cores}C / {vm_request.ram_mb}MB / {vm_request.disk_gb}GB")

        # Network configuration
        if tmpl.cloud_init and vm_request.ip_address:
            await asyncio.to_thread(
                vs.configure_network, vm_request.vm_name, vm_request.ip_address,
            )
            logger.info(f"Configured network for {vm_request.vm_name}")

        # Start VM
        await asyncio.to_thread(vs.start_vm, vm_request.vm_name)
        logger.info(f"Started VM '{vm_request.vm_name}'")

        # Update DB — generic fields (no legacy proxmox fields)
        vm_request.status = RequestStatus.COMPLETED
        vm_request.hypervisor_vm_id = moref
        vm_request.hypervisor_host = target_host
        vm_request.completed_at = datetime.now(timezone.utc)
    finally:
        await asyncio.to_thread(vs.disconnect)


# ── Dispatch ─────────────────────────────────────────────────────

async def _provision_single_vm(db, vm_request: VMRequest, env=None, pve: ProxmoxService | None = None) -> None:
    """Provision a single VM, dispatching by environment type."""
    env_type = getattr(env, "environment_type", "proxmox") if env else "proxmox"

    if env_type == "proxmox":
        if pve is None:
            pve = await _get_proxmox_service(db, env)
        await _provision_proxmox_vm(db, vm_request, pve)
    elif env_type in ("esxi", "vcenter"):
        await _provision_vsphere_vm(db, vm_request, env)
    else:
        raise ValueError(f"Unknown environment type: {env_type}")


# ── Public entry points ──────────────────────────────────────────

async def provision_vm(request_id: int) -> None:
    """Full provisioning pipeline. Runs as a background task."""
    async with async_session() as db:
        try:
            result = await db.execute(
                select(VMRequest).where(VMRequest.id == request_id)
            )
            vm_request = result.scalar_one_or_none()
            if not vm_request:
                logger.error(f"VM request {request_id} not found")
                return

            vm_request.status = RequestStatus.PROVISIONING
            vm_request.error_message = None
            await db.commit()

            await _jira_comment(
                db, vm_request.jira_issue_key,
                f"Provisioning started for VM '{vm_request.vm_name}'..."
            )

            env = await _get_environment(db, vm_request.environment_id)
            await _provision_single_vm(db, vm_request, env=env)
            await db.commit()

            logger.info(
                f"Provisioning complete for request {request_id}: "
                f"VM ID {vm_request.hypervisor_vm_id} on {vm_request.hypervisor_host}"
            )

            await _jira_comment(
                db, vm_request.jira_issue_key,
                f"VM provisioned successfully.\n"
                f"VM ID: {vm_request.hypervisor_vm_id or vm_request.proxmox_vmid}\n"
                f"Host: {vm_request.hypervisor_host or vm_request.proxmox_node}\n"
                f"IP: {vm_request.ip_address or 'N/A'}"
            )

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

                    await _jira_comment(
                        error_db, vm_request.jira_issue_key,
                        f"Provisioning failed: {str(e)[:500]}"
                    )

                    from app.services.email import send_provisioning_failed
                    asyncio.create_task(send_provisioning_failed(request_id))


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

            # Resolve environment once for the whole deployment
            env = await _get_environment(db, deployment.environment_id)
            env_type = getattr(env, "environment_type", "proxmox") if env else "proxmox"

            # For Proxmox, create service once and reuse
            pve = None
            if env_type == "proxmox":
                pve = await _get_proxmox_service(db, env)

            completed = 0
            failed = 0

            for vm_req in deployment.vm_requests:
                if vm_req.status == RequestStatus.COMPLETED:
                    completed += 1
                    continue

                try:
                    vm_req.status = RequestStatus.PROVISIONING
                    vm_req.error_message = None
                    await db.commit()

                    await _jira_comment(
                        db, deployment.jira_issue_key,
                        f"Provisioning VM '{vm_req.vm_name}'...",
                    )

                    await _provision_single_vm(db, vm_req, env=env, pve=pve)
                    await db.commit()
                    completed += 1

                    vm_id = vm_req.hypervisor_vm_id or vm_req.proxmox_vmid
                    host = vm_req.hypervisor_host or vm_req.proxmox_node
                    await _jira_comment(
                        db, deployment.jira_issue_key,
                        f"VM '{vm_req.vm_name}' provisioned: ID {vm_id} "
                        f"on {host}, IP: {vm_req.ip_address or 'N/A'}",
                    )

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
