from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class OSTemplateMapping(Base):
    __tablename__ = "os_template_mappings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    vmid = Column(Integer, nullable=False)
    node = Column(String(100), nullable=False)
    os_family = Column(String(20), nullable=False)  # "linux" or "windows"
    cloud_init = Column(Boolean, default=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
