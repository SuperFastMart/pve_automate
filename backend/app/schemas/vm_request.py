from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator

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
    tshirt_size: str = Field(..., pattern=r"^(XS|S|M|L|XL|Custom)$")
    subnet_id: Optional[int] = None
    environment_id: Optional[int] = None

    # Custom size fields (required only when tshirt_size == "Custom")
    cpu_cores: Optional[int] = Field(None, ge=1, le=128)
    ram_mb: Optional[int] = Field(None, ge=512, le=524288)
    disk_gb: Optional[int] = Field(None, ge=8, le=4096)

    @model_validator(mode="after")
    def validate_custom_size(self):
        if self.tshirt_size == "Custom":
            missing = []
            if self.cpu_cores is None:
                missing.append("cpu_cores")
            if self.ram_mb is None:
                missing.append("ram_mb")
            if self.disk_gb is None:
                missing.append("disk_gb")
            if missing:
                raise ValueError(f"Custom size requires: {', '.join(missing)}")
        return self


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
    subnet_id: Optional[int]
    phpipam_address_id: Optional[int]
    environment_id: Optional[int]
    environment_name: Optional[str]
    deployment_id: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class VMRequestList(BaseModel):
    items: list[VMRequestResponse]
    total: int
