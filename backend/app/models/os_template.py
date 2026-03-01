from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class OSTemplateMapping(Base):
    __tablename__ = "os_template_mappings"
    __table_args__ = (
        UniqueConstraint("key", "environment_id", name="uq_template_key_env"),
    )

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    vmid = Column(Integer, nullable=True)       # Proxmox template VMID
    node = Column(String(100), nullable=True)    # Proxmox source node
    template_ref = Column(String(500), nullable=True)  # vSphere template name/path
    os_family = Column(String(20), nullable=False)  # "linux" or "windows"
    cloud_init = Column(Boolean, default=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    environment_id = Column(Integer, ForeignKey("pve_environments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
