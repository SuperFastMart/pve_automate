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
            # Parse current disk size to avoid shrink errors
            # Format: "local-lvm:vm-100-disk-0,size=32G" or similar
            import re
            current_size_gb = 0
            disk_val = str(config.get(disk_key, ""))
            size_match = re.search(r"size=(\d+)G", disk_val)
            if size_match:
                current_size_gb = int(size_match.group(1))

            if disk_gb > current_size_gb:
                self.proxmox.nodes(node).qemu(vmid).resize.put(
                    disk=disk_key,
                    size=f"{disk_gb}G",
                )
            else:
                logger.info(
                    f"Skipping disk resize for VMID {vmid}: "
                    f"current {current_size_gb}G >= target {disk_gb}G"
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
            for vm in self.proxmox.nodes(node).qemu.get():
                if vm.get("template") in (1, "1", True):
                    templates.append({
                        "vmid": vm["vmid"],
                        "name": vm.get("name", ""),
                        "node": node,
                        "status": vm.get("status", "stopped"),
                        "disk_size": vm.get("maxdisk", 0),
                        "memory": vm.get("maxmem", 0),
                    })
        return templates

    # ── LXC Container Methods ──────────────────────────────────────

    def get_ct_templates(self) -> list[dict]:
        """Get all CT templates (vztmpl) across all nodes/storage."""
        ct_templates = []
        seen = set()
        for node_info in self.get_nodes():
            node = node_info["node"]
            try:
                storages = self.proxmox.nodes(node).storage.get()
            except Exception:
                continue
            for storage in storages:
                storage_id = storage["storage"]
                try:
                    content = self.proxmox.nodes(node).storage(storage_id).content.get(
                        content="vztmpl"
                    )
                except Exception:
                    continue
                for item in content:
                    volid = item.get("volid", "")
                    if volid in seen:
                        continue
                    seen.add(volid)
                    # Filename from volid e.g. "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
                    filename = volid.split("/")[-1] if "/" in volid else volid
                    ct_templates.append({
                        "template_ref": volid,
                        "name": filename,
                        "node": node,
                        "status": "template",
                        "disk_size": item.get("size", 0),
                        "memory": 0,
                    })
        return ct_templates

    def create_lxc(
        self,
        node: str,
        vmid: int,
        ostemplate: str,
        hostname: str,
        cores: int,
        memory_mb: int,
        disk_gb: int,
        net_config: str,
        nameserver: str | None = None,
        searchdomain: str | None = None,
        ssh_public_keys: str | None = None,
        unprivileged: bool = True,
        storage: str = "local-lvm",
        password: str | None = None,
    ) -> str:
        """Create an LXC container. Returns the UPID (task ID)."""
        params = {
            "vmid": vmid,
            "ostemplate": ostemplate,
            "hostname": hostname,
            "cores": cores,
            "memory": memory_mb,
            "rootfs": f"{storage}:{disk_gb}",
            "net0": net_config,
            "unprivileged": 1 if unprivileged else 0,
            "start": 0,
        }
        if nameserver:
            params["nameserver"] = nameserver
        if searchdomain:
            params["searchdomain"] = searchdomain
        if ssh_public_keys:
            params["ssh-public-keys"] = ssh_public_keys
        if password:
            params["password"] = password
        return self.proxmox.nodes(node).lxc.post(**params)

    def resize_lxc(
        self, node: str, vmid: int, cpu_cores: int, ram_mb: int, disk_gb: int
    ):
        """Resize CPU, memory, and disk for an LXC container."""
        self.proxmox.nodes(node).lxc(vmid).config.put(
            cores=cpu_cores,
            memory=ram_mb,
        )
        # Resize rootfs if larger than current
        config = self.proxmox.nodes(node).lxc(vmid).config.get()
        import re
        rootfs_val = str(config.get("rootfs", ""))
        size_match = re.search(r"size=(\d+)G", rootfs_val)
        current_gb = int(size_match.group(1)) if size_match else 0
        if disk_gb > current_gb:
            self.proxmox.nodes(node).lxc(vmid).resize.put(
                disk="rootfs",
                size=f"{disk_gb}G",
            )

    def start_lxc(self, node: str, vmid: int) -> str:
        """Start an LXC container. Returns UPID."""
        return self.proxmox.nodes(node).lxc(vmid).status.start.post()

    def get_lxc_status(self, node: str, vmid: int) -> dict:
        """Get the current status of an LXC container."""
        return self.proxmox.nodes(node).lxc(vmid).status.current.get()

    def exec_on_node(self, node: str, command: str, timeout: int = 30) -> str:
        """SSH into a Proxmox node and execute a command via pct exec.

        Uses the Proxmox API host and token credentials for SSH are NOT
        available, so this requires the API user to have SSH access via
        key-based auth from the machine running the backend.  For lab setups
        using root@pam, the Proxmox nodes typically accept SSH from localhost
        or via agent forwarding.

        Alternatively, resolves the node's IP from the cluster and connects.
        """
        import paramiko

        # Resolve node IP from cluster status
        node_ip = None
        try:
            cluster_status = self.proxmox.cluster.status.get()
            for member in cluster_status:
                if member.get("name") == node and member.get("ip"):
                    node_ip = member["ip"]
                    break
        except Exception:
            pass

        # Fall back to the API host itself (works for single-node or if API host IS the node)
        if not node_ip:
            node_ip = self.proxmox._store["host"]

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            # Try key-based auth (agent or default keys)
            client.connect(node_ip, username="root", timeout=timeout)
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            err_output = stderr.read().decode().strip()
            if exit_code != 0:
                logger.warning(f"Command on {node} returned {exit_code}: {err_output}")
            return output
        finally:
            client.close()

    def configure_lxc_ssh_root(self, node: str, vmid: int) -> None:
        """Enable root SSH login inside a running LXC container.

        Uses the Proxmox host API to run 'pct exec' commands on the node.
        The API token must have Sys.Console or root-equivalent permissions.
        """
        # Proxmox API: POST /nodes/{node}/exec — runs a command on the host
        # We use this to call 'pct exec' which runs inside the container.
        script = (
            f"pct exec {vmid} -- sed -i 's/^#*PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config && "
            f"pct exec {vmid} -- sh -c 'systemctl restart sshd 2>/dev/null || service ssh restart'"
        )

        # Method 1: Try via Proxmox API node exec (PVE 8.4+)
        try:
            self.proxmox.nodes(node).execute.post(command="bash", **{"input-data": script})
            logger.info(f"Configured SSH root login for LXC {vmid} on {node} via API node exec")
            return
        except Exception as e:
            logger.info(f"API node exec not available for {node}: {e}, trying SSH fallback")

        # Method 2: SSH to node
        try:
            self.exec_on_node(node, f"bash -c '{script}'")
            logger.info(f"Configured SSH root login for LXC {vmid} on {node} via SSH")
        except Exception as e:
            logger.warning(f"Failed to configure SSH root for LXC {vmid}: {e}")
