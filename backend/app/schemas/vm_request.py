from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.vm_request import RequestStatus


class VMRequestCreate(BaseModel):
    vm_name: str = Field(
        ...,
        min_length=1,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$",
        description="VM hostname (alphanumeric and hyphens, must start with letter/number)",
    )
    description: Optional[str] = None
    requestor_name: str = Field(..., min_length=1, max_length=255)
    requestor_email: EmailStr
    workload_type: str
    os_template: str
    tshirt_size: str = Field(..., pattern=r"^(XS|S|M|L|XL)$")


class VMRequestResponse(BaseModel):
    id: int
    vm_name: str
    description: Optional[str]
    requestor_name: str
    requestor_email: str
    workload_type: str
    os_template: str
    tshirt_size: str
    cpu_cores: int
    ram_mb: int
    disk_gb: int
    status: RequestStatus
    jira_issue_key: Optional[str]
    jira_issue_url: Optional[str]
    proxmox_vmid: Optional[int]
    proxmox_node: Optional[str]
    ip_address: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class VMRequestList(BaseModel):
    items: list[VMRequestResponse]
    total: int
