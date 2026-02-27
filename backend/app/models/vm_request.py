import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text

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
    workload_type = Column(String(50), nullable=False)
    os_template = Column(String(100), nullable=False)
    tshirt_size = Column(String(5), nullable=False)

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
    ip_address = Column(String(45), nullable=True)
    vlan_id = Column(Integer, nullable=True)
    subnet_id = Column(Integer, nullable=True)
    phpipam_address_id = Column(Integer, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
