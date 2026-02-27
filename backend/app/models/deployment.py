import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DeploymentStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROVISIONING = "provisioning"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"


def _utcnow():
    return datetime.now(timezone.utc)


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, index=True)

    # Deployment details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    requestor_name = Column(String(255), nullable=False)
    requestor_email = Column(String(255), nullable=False)
    workload_type = Column(String(50), nullable=False)

    # Environment (denormalized)
    environment_id = Column(Integer, nullable=True)
    environment_name = Column(String(200), nullable=True)

    # Status
    status = Column(
        Enum(DeploymentStatus),
        default=DeploymentStatus.PENDING_APPROVAL,
        nullable=False,
    )

    # Integration
    jira_issue_key = Column(String(30), nullable=True)
    jira_issue_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    vm_requests = relationship("VMRequest", back_populates="deployment", lazy="selectin")
