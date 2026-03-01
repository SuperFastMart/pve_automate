from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Environment(Base):
    __tablename__ = "pve_environments"  # keep old table name for SQLite compat

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Hypervisor type: "proxmox", "esxi", "vcenter"
    environment_type = Column(String(20), nullable=False, default="proxmox")

    # Location binding (phpIPAM location)
    location_id = Column(Integer, nullable=True)
    location_name = Column(String(200), nullable=True)

    # Proxmox credentials (nullable — only required for type=proxmox)
    pve_host = Column(String(255), nullable=True)
    pve_user = Column(String(255), nullable=True)
    pve_token_name = Column(String(255), nullable=True)
    pve_token_value = Column(Text, nullable=True)
    pve_verify_ssl = Column(Boolean, default=False, nullable=False)

    # vSphere/ESXi credentials (nullable — only required for type=esxi|vcenter)
    vsphere_host = Column(String(255), nullable=True)
    vsphere_user = Column(String(255), nullable=True)
    vsphere_password = Column(Text, nullable=True)
    vsphere_port = Column(Integer, default=443, nullable=False)
    vsphere_verify_ssl = Column(Boolean, default=False, nullable=False)
    vsphere_datacenter = Column(String(255), nullable=True)  # vCenter only
    vsphere_cluster = Column(String(255), nullable=True)     # vCenter only

    enabled = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


# Backward compatibility alias
PVEEnvironment = Environment
