import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class RequestStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROVISIONING = "provisioning"
    PROVISIONING_FAILED = "provisioning_failed"
    COMPLETED = "completed"


def _utcnow():
    return datetime.now(timezone.utc)


class VMRequest(Base):
    __tablename__ = "vm_requests"

    id = Column(Integer, primary_key=True, index=True)

    # Request details
    vm_name = Column(String(63), nullable=False)
    description = Column(Text, nullable=True)
    requestor_name = Column(String(255), nullable=False)
    requestor_email = Column(String(255), nullable=False)
    resource_type = Column(String(10), nullable=False, default="vm")  # "vm" or "lxc"
    workload_type = Column(String(50), nullable=False)
    os_template = Column(String(100), nullable=False)
    tshirt_size = Column(String(10), nullable=False)

    # Resolved specs (denormalized from config at submission time)
    cpu_cores = Column(Integer, nullable=False)
    ram_mb = Column(Integer, nullable=False)
    disk_gb = Column(Integer, nullable=False)

    # Provisioning outcome
    status = Column(
        Enum(RequestStatus),
        default=RequestStatus.PENDING_APPROVAL,
        nullable=False,
    )
    jira_issue_key = Column(String(30), nullable=True)
    jira_issue_url = Column(String(500), nullable=True)
    proxmox_vmid = Column(Integer, nullable=True)
    proxmox_node = Column(String(100), nullable=True)
    hypervisor_vm_id = Column(String(200), nullable=True)  # Generic: VMID (PVE) or MoRef (vSphere)
    hypervisor_host = Column(String(200), nullable=True)   # Generic: node (PVE) or ESXi host (vSphere)
    ip_address = Column(String(45), nullable=True)
    ip_gateway = Column(String(45), nullable=True)  # Gateway from phpIPAM subnet
    ip_mask = Column(String(3), nullable=True)       # Subnet mask bits (e.g. "24")
    nameserver = Column(String(255), nullable=True)   # DNS nameserver from phpIPAM
    vlan_id = Column(Integer, nullable=True)
    subnet_id = Column(Integer, nullable=True)
    phpipam_address_id = Column(Integer, nullable=True)
    environment_id = Column(Integer, ForeignKey("pve_environments.id"), nullable=True)
    environment_name = Column(String(200), nullable=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=True)

    # LXC-specific options
    mtu = Column(Integer, nullable=True)  # MTU override (null = inherit from host)
    bridge = Column(String(20), nullable=True)  # Network bridge (e.g. vmbr0, vmbr1)
    vlan_tag = Column(Integer, nullable=True)  # VLAN tag (e.g. 400)
    enable_ssh_root = Column(Boolean, nullable=True)  # Enable PermitRootLogin in sshd_config
    root_password = Column(Text, nullable=True)  # Root password for LXC containers

    # Relationships
    deployment = relationship("Deployment", back_populates="vm_requests")

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
