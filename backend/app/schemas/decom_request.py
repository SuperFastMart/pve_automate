from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.decom_request import DecomStatus


class DecomRequestCreate(BaseModel):
    vm_request_id: Optional[int] = None
    deployment_id: Optional[int] = None
    reason: str = Field(..., min_length=1, max_length=2000)
    review_date: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_target(self):
        if not self.vm_request_id and not self.deployment_id:
            raise ValueError("Either vm_request_id or deployment_id must be provided")
        if self.vm_request_id and self.deployment_id:
            raise ValueError("Only one of vm_request_id or deployment_id can be provided")
        return self


class DecomRequestResponse(BaseModel):
    id: int
    vm_request_id: Optional[int]
    deployment_id: Optional[int]
    reason: str
    requestor_name: str
    requestor_email: str
    review_date: Optional[datetime]
    notes: Optional[str]
    status: DecomStatus
    jira_issue_key: Optional[str]
    jira_issue_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]

    # Denormalized resource info for display
    resource_name: Optional[str] = None
    resource_type: Optional[str] = None
    ip_address: Optional[str] = None

    model_config = {"from_attributes": True}


class DecomRequestList(BaseModel):
    items: list[DecomRequestResponse]
    total: int
