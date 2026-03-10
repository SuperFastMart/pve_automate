import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DecomStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _utcnow():
    return datetime.now(timezone.utc)


class DecomRequest(Base):
    __tablename__ = "decom_requests"

    id = Column(Integer, primary_key=True, index=True)

    # What to decommission (exactly one must be set)
    vm_request_id = Column(Integer, ForeignKey("vm_requests.id"), nullable=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=True)

    # Request details
    reason = Column(Text, nullable=False)
    requestor_name = Column(String(255), nullable=False)
    requestor_email = Column(String(255), nullable=False)
    review_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)  # Admin notes

    # Status
    status = Column(
        Enum(DecomStatus),
        default=DecomStatus.PENDING_APPROVAL,
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
    vm_request = relationship("VMRequest", lazy="selectin")
    deployment = relationship("Deployment", lazy="selectin")
