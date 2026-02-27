from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class PVEEnvironment(Base):
    __tablename__ = "pve_environments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    pve_host = Column(String(255), nullable=False)
    pve_user = Column(String(255), nullable=False)
    pve_token_name = Column(String(255), nullable=False)
    pve_token_value = Column(Text, nullable=False)
    pve_verify_ssl = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
