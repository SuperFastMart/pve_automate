import logging
import time

from proxmoxer import ProxmoxAPI

logger = logging.getLogger(__name__)


class ProxmoxService:
    """Low-level wrapper around proxmoxer for Proxmox VE API operations."""

    def __init__(
        self,
        host: str,
        user: str,
        token_name: str,
        token_value: str,
        verify_ssl: bool = False,
    ):
        self.proxmox = ProxmoxAPI(
            host,
            user=user,
            token_name=token_name,
            token_value=token_value,
            verify_ssl=verify_ssl,
            timeout=120,
        )

    def get_version(self) -> dict:
        """Test connectivity by fetching PVE version."""
        return self.proxmox.version.get()

    def get_next_vmid(self) -> int:
        """Get the next available VMID from the cluster."""
        return int(self.proxmox.cluster.nextid.get())

    def get_nodes(self) -> list[dict]:
        """Get all cluster nodes with resource info."""
        return self.proxmox.nodes.get()

    def get_node_status(self, node: str) -> dict:
        """Get detailed status for a specific node."""
        return self.proxmox.nodes(node).status.get()

    def clone_vm(
        self,
        source_node: str,
        template_vmid: int,
        new_vmid: int,
        name: str,
        target_node: str | None = None,
        full: bool = True,
    ) -> str:
        """Clone a template VM. Returns the UPID (task ID) for tracking."""
        params = {
            "newid": new_vmid,
            "name": name,
            "full": 1 if full else 0,
        }
        if target_node and target_node != source_node:
            params["target"] = target_node
        return self.proxmox.nodes(source_node).qemu(template_vmid).clone.post(**params)

    def wait_for_task(
        self, node: str, upid: str, timeout: int = 600, poll_interval: int = 5
    ) -> bool:
        """Poll a task UPID until completion or timeout. Returns True if succeeded."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.proxmox.nodes(node).tasks(upid).status.get()
            if status.get("status") == "stopped":
                return status.get("exitstatus") == "OK"
            time.sleep(poll_interval)
        raise TimeoutError(f"Task {upid} did not complete within {timeout}s")

    def resize_vm(
        self, node: str, vmid: int, cpu_cores: int, ram_mb: int, disk_gb: int
    ):
        """Resize CPU, memory, and disk for a VM."""
        # CPU and memory
        self.proxmox.nodes(node).qemu(vmid).config.put(
            cores=cpu_cores,
            memory=ram_mb,
        )

        # Find the boot disk key
        config = self.proxmox.nodes(node).qemu(vmid).config.get()
        disk_key = None
        for key in ["scsi0", "virtio0", "ide0"]:
            if key in config:
                disk_key = key
                break

        if disk_key:
            self.proxmox.nodes(node).qemu(vmid).resize.put(
                disk=disk_key,
                size=f"{disk_gb}G",
            )

    def configure_cloud_init(
        self,
        node: str,
        vmid: int,
        ip_address: str | None = None,
        gateway: str | None = None,
        nameserver: str | None = None,
    ):
        """Set cloud-init parameters for Linux VMs."""
        params = {}
        if ip_address:
            cidr = ip_address if "/" in ip_address else f"{ip_address}/24"
            ip_config = f"ip={cidr}"
            if gateway:
                ip_config += f",gw={gateway}"
            params["ipconfig0"] = ip_config
        if nameserver:
            params["nameserver"] = nameserver
        if params:
            self.proxmox.nodes(node).qemu(vmid).config.put(**params)

    def start_vm(self, node: str, vmid: int) -> str:
        """Start a VM. Returns UPID."""
        return self.proxmox.nodes(node).qemu(vmid).status.start.post()

    def get_templates(self) -> list[dict]:
        """Get all template VMs across all nodes."""
        templates = []
        for node_info in self.get_nodes():
            node = node_info["node"]
            vms = self.proxmox.nodes(node).qemu.get()
            logger.info(f"Node {node}: found {len(vms)} VMs")
            for vm in vms:
                tmpl_flag = vm.get("template")
                logger.info(f"  VMID {vm.get('vmid')} name={vm.get('name')} template={tmpl_flag!r} (type={type(tmpl_flag).__name__})")
                if tmpl_flag in (1, "1", True):
                    templates.append({
                        "vmid": vm["vmid"],
                        "name": vm.get("name", ""),
                        "node": node,
                        "status": vm.get("status", "stopped"),
                        "disk_size": vm.get("maxdisk", 0),
                        "memory": vm.get("maxmem", 0),
                    })
        return templates
