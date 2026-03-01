"""VMware vSphere / ESXi service wrapper using pyvmomi.

All methods are synchronous (pyvmomi is blocking). The provisioning layer
wraps calls in ``asyncio.to_thread()`` to avoid blocking the event loop.
"""

import logging
import ssl
import time

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

logger = logging.getLogger(__name__)


class VSphereService:
    """Low-level wrapper around pyvmomi for ESXi / vCenter operations."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        port: int = 443,
        verify_ssl: bool = False,
        datacenter: str | None = None,
        cluster: str | None = None,
    ):
        self.host = host
        self.datacenter_name = datacenter
        self.cluster_name = cluster

        ssl_context = None
        if not verify_ssl:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        self.si = SmartConnect(
            host=host,
            user=user,
            pwd=password,
            port=port,
            sslContext=ssl_context,
        )
        self.content = self.si.RetrieveContent()

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_datacenter(self) -> vim.Datacenter:
        """Return the configured datacenter or the first one found."""
        for dc in self.content.rootFolder.childEntity:
            if isinstance(dc, vim.Datacenter):
                if not self.datacenter_name or dc.name == self.datacenter_name:
                    return dc
        raise RuntimeError(
            f"Datacenter '{self.datacenter_name}' not found"
            if self.datacenter_name else "No datacenter found"
        )

    def _get_cluster(self) -> vim.ClusterComputeResource | None:
        """Return the configured cluster or None (standalone ESXi)."""
        if not self.cluster_name:
            return None
        dc = self._get_datacenter()
        for child in dc.hostFolder.childEntity:
            if isinstance(child, vim.ClusterComputeResource) and child.name == self.cluster_name:
                return child
        raise RuntimeError(f"Cluster '{self.cluster_name}' not found in datacenter '{dc.name}'")

    def _find_obj(self, vimtype, name: str):
        """Find a managed object by type and name."""
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vimtype], True
        )
        try:
            for obj in container.view:
                if obj.name == name:
                    return obj
        finally:
            container.Destroy()
        return None

    def _wait_for_task(self, task, timeout: int = 600):
        """Block until a vSphere task completes or times out."""
        start = time.time()
        while time.time() - start < timeout:
            state = task.info.state
            if state == vim.TaskInfo.State.success:
                return task.info.result
            if state == vim.TaskInfo.State.error:
                raise RuntimeError(f"Task failed: {task.info.error.msg}")
            time.sleep(5)
        raise TimeoutError(f"Task did not complete within {timeout}s")

    # ── Public API (mirrors ProxmoxService patterns) ─────────────

    def get_version(self) -> dict:
        """Test connectivity by returning the vSphere/ESXi version."""
        about = self.content.about
        return {
            "version": about.version,
            "build": about.build,
            "fullName": about.fullName,
            "apiType": about.apiType,  # "VirtualCenter" or "HostAgent"
        }

    def get_hosts(self) -> list[dict]:
        """List ESXi hosts with resource info."""
        hosts = []
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.HostSystem], True
        )
        try:
            for host in container.view:
                summary = host.summary
                hosts.append({
                    "name": host.name,
                    "connection_state": str(summary.runtime.connectionState),
                    "power_state": str(summary.runtime.powerState),
                    "cpu_total_mhz": summary.hardware.cpuMhz * summary.hardware.numCpuCores,
                    "cpu_used_mhz": summary.quickStats.overallCpuUsage or 0,
                    "memory_total_bytes": summary.hardware.memorySize,
                    "memory_used_bytes": (summary.quickStats.overallMemoryUsage or 0) * 1024 * 1024,
                })
        finally:
            container.Destroy()
        return hosts

    def get_templates(self) -> list[dict]:
        """List all template VMs."""
        templates = []
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.VirtualMachine], True
        )
        try:
            for vm in container.view:
                if vm.config and vm.config.template:
                    templates.append({
                        "vmid": None,
                        "name": vm.name,
                        "node": vm.runtime.host.name if vm.runtime.host else None,
                        "status": str(vm.runtime.powerState),
                        "disk_size": sum(
                            d.capacityInBytes for d in vm.config.hardware.device
                            if isinstance(d, vim.vm.device.VirtualDisk)
                        ),
                        "memory": vm.config.hardware.memoryMB * 1024 * 1024,
                        "template_ref": vm.name,
                    })
        finally:
            container.Destroy()
        return templates

    def clone_vm(
        self,
        template_name: str,
        new_name: str,
        target_host: str | None = None,
        cpu_cores: int | None = None,
        ram_mb: int | None = None,
    ) -> str:
        """Clone a template VM. Returns the MoRef ID of the new VM."""
        template = self._find_obj(vim.VirtualMachine, template_name)
        if not template:
            raise RuntimeError(f"Template '{template_name}' not found")

        # Relocate spec
        relocate_spec = vim.vm.RelocateSpec()

        if target_host:
            host_obj = self._find_obj(vim.HostSystem, target_host)
            if host_obj:
                relocate_spec.host = host_obj
                # Use the host's first datastore if no specific one configured
                if host_obj.datastore:
                    relocate_spec.datastore = host_obj.datastore[0]

        # Config spec (optional resize during clone)
        config_spec = vim.vm.ConfigSpec()
        if cpu_cores:
            config_spec.numCPUs = cpu_cores
        if ram_mb:
            config_spec.memoryMB = ram_mb

        clone_spec = vim.vm.CloneSpec(
            location=relocate_spec,
            config=config_spec,
            powerOn=False,
            template=False,
        )

        # Target folder
        dc = self._get_datacenter()
        folder = dc.vmFolder

        task = template.Clone(folder=folder, name=new_name, spec=clone_spec)
        new_vm = self._wait_for_task(task, timeout=1200)

        moref = str(new_vm._moId) if new_vm else new_name
        logger.info(f"Cloned template '{template_name}' → '{new_name}' (MoRef: {moref})")
        return moref

    def resize_vm(
        self, vm_name: str, cpu_cores: int, ram_mb: int, disk_gb: int
    ):
        """Resize CPU, memory, and disk for a VM."""
        vm = self._find_obj(vim.VirtualMachine, vm_name)
        if not vm:
            raise RuntimeError(f"VM '{vm_name}' not found")

        # CPU + RAM
        config_spec = vim.vm.ConfigSpec()
        config_spec.numCPUs = cpu_cores
        config_spec.memoryMB = ram_mb
        task = vm.ReconfigVM_Task(spec=config_spec)
        self._wait_for_task(task)

        # Disk resize — find first virtual disk
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                target_kb = disk_gb * 1024 * 1024
                if device.capacityInKB < target_kb:
                    disk_spec = vim.vm.device.VirtualDeviceSpec()
                    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                    disk_spec.device = device
                    disk_spec.device.capacityInKB = target_kb

                    reconfig = vim.vm.ConfigSpec()
                    reconfig.deviceChange = [disk_spec]
                    task = vm.ReconfigVM_Task(spec=reconfig)
                    self._wait_for_task(task)
                else:
                    logger.info(
                        f"Skipping disk resize for {vm_name}: "
                        f"current {device.capacityInKB // (1024*1024)}G >= target {disk_gb}G"
                    )
                break

    def configure_network(
        self,
        vm_name: str,
        ip_address: str | None = None,
        gateway: str | None = None,
        nameserver: str | None = None,
    ):
        """Configure guest customization (IP settings) for a VM.

        Uses vSphere Guest Customization spec for Linux VMs.
        """
        if not ip_address:
            return

        vm = self._find_obj(vim.VirtualMachine, vm_name)
        if not vm:
            raise RuntimeError(f"VM '{vm_name}' not found")

        # Build IP settings
        cidr = ip_address if "/" in ip_address else f"{ip_address}/24"
        ip_part, prefix = cidr.split("/")
        subnet_mask = self._prefix_to_mask(int(prefix))

        fixed_ip = vim.vm.customization.FixedIp(ipAddress=ip_part)
        ip_settings = vim.vm.customization.IPSettings(
            ip=fixed_ip,
            subnetMask=subnet_mask,
        )
        if gateway:
            ip_settings.gateway = [gateway]

        adapter_mapping = vim.vm.customization.AdapterMapping(adapter=ip_settings)

        global_ip = vim.vm.customization.GlobalIPSettings()
        if nameserver:
            global_ip.dnsServerList = [nameserver]

        identity = vim.vm.customization.LinuxPrep(
            hostName=vim.vm.customization.FixedName(name=vm_name),
        )

        customization_spec = vim.vm.customization.Specification(
            globalIPSettings=global_ip,
            identity=identity,
            nicSettingMap=[adapter_mapping],
        )

        task = vm.CustomizeVM_Task(spec=customization_spec)
        self._wait_for_task(task)
        logger.info(f"Configured network for {vm_name}: {ip_address}")

    def start_vm(self, vm_name: str):
        """Power on a VM."""
        vm = self._find_obj(vim.VirtualMachine, vm_name)
        if not vm:
            raise RuntimeError(f"VM '{vm_name}' not found")
        task = vm.PowerOnVM_Task()
        self._wait_for_task(task, timeout=120)
        logger.info(f"Started VM '{vm_name}'")

    def disconnect(self):
        """Disconnect from vSphere."""
        try:
            Disconnect(self.si)
        except Exception:
            pass

    @staticmethod
    def _prefix_to_mask(prefix: int) -> str:
        """Convert CIDR prefix to dotted-decimal subnet mask."""
        bits = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        return f"{(bits >> 24) & 0xFF}.{(bits >> 16) & 0xFF}.{(bits >> 8) & 0xFF}.{bits & 0xFF}"
