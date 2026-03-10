from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.deployment import DeploymentStatus
from app.schemas.vm_request import VMRequestResponse


class DeploymentVMItem(BaseModel):
    """Single VM/LXC definition within a deployment creation request."""
    vm_name: str = Field(
        ...,
        min_length=1,
        max_length=63,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$",
    )
    description: Optional[str] = None
    os_template: str
    tshirt_size: str = Field(..., pattern=r"^(XS|S|M|L|XL|Custom)$")
    subnet_id: Optional[int] = None

    # Custom size fields
    cpu_cores: Optional[int] = Field(None, ge=1, le=128)
    ram_mb: Optional[int] = Field(None, ge=512, le=524288)
    disk_gb: Optional[int] = Field(None, ge=8, le=4096)

    # LXC-specific options (per-item override)
    mtu: Optional[int] = Field(None, ge=576, le=9216)
    bridge: Optional[str] = None
    vlan_tag: Optional[int] = None
    enable_ssh_root: Optional[bool] = None


class DeploymentCreate(BaseModel):
    """Create a multi-VM/LXC deployment."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    resource_type: str = Field("vm", pattern=r"^(vm|lxc)$")
    workload_type: str
    environment_id: Optional[int] = None
    vms: list[DeploymentVMItem] = Field(..., min_length=1, max_length=20)


class DeploymentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    requestor_name: str
    requestor_email: str
    resource_type: str = "vm"
    workload_type: str
    environment_id: Optional[int]
    environment_name: Optional[str]
    status: DeploymentStatus
    jira_issue_key: Optional[str]
    jira_issue_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]
    vm_requests: list[VMRequestResponse]

    model_config = {"from_attributes": True}


class DeploymentListItem(BaseModel):
    id: int
    name: str
    requestor_name: str
    requestor_email: str
    resource_type: str = "vm"
    workload_type: str
    environment_name: Optional[str]
    status: DeploymentStatus
    jira_issue_key: Optional[str]
    vm_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DeploymentList(BaseModel):
    items: list[DeploymentListItem]
    total: int
