from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    environment_type: str = Field("proxmox", pattern=r"^(proxmox|esxi|vcenter)$")
    location_id: Optional[int] = None
    location_name: Optional[str] = None

    # Proxmox credentials
    pve_host: Optional[str] = None
    pve_user: Optional[str] = None
    pve_token_name: Optional[str] = None
    pve_token_value: Optional[str] = None
    pve_verify_ssl: bool = False

    # vSphere/ESXi credentials
    vsphere_host: Optional[str] = None
    vsphere_user: Optional[str] = None
    vsphere_password: Optional[str] = None
    vsphere_port: int = 443
    vsphere_verify_ssl: bool = False
    vsphere_datacenter: Optional[str] = None
    vsphere_cluster: Optional[str] = None

    enabled: bool = True
    is_default: bool = False

    @model_validator(mode="after")
    def validate_credentials(self):
        if self.environment_type == "proxmox":
            if not all([self.pve_host, self.pve_user, self.pve_token_name, self.pve_token_value]):
                raise ValueError("Proxmox environments require pve_host, pve_user, pve_token_name, pve_token_value")
        elif self.environment_type in ("esxi", "vcenter"):
            if not all([self.vsphere_host, self.vsphere_user, self.vsphere_password]):
                raise ValueError("vSphere environments require vsphere_host, vsphere_user, vsphere_password")
            if self.environment_type == "vcenter" and not self.vsphere_datacenter:
                raise ValueError("vCenter environments require vsphere_datacenter")
        return self


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    environment_type: Optional[str] = Field(None, pattern=r"^(proxmox|esxi|vcenter)$")
    location_id: Optional[int] = None
    location_name: Optional[str] = None

    # Proxmox credentials
    pve_host: Optional[str] = None
    pve_user: Optional[str] = None
    pve_token_name: Optional[str] = None
    pve_token_value: Optional[str] = None
    pve_verify_ssl: Optional[bool] = None

    # vSphere/ESXi credentials
    vsphere_host: Optional[str] = None
    vsphere_user: Optional[str] = None
    vsphere_password: Optional[str] = None
    vsphere_port: Optional[int] = None
    vsphere_verify_ssl: Optional[bool] = None
    vsphere_datacenter: Optional[str] = None
    vsphere_cluster: Optional[str] = None

    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class EnvironmentResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    environment_type: str
    location_id: Optional[int]
    location_name: Optional[str]

    # Proxmox fields
    pve_host: Optional[str]
    pve_user: Optional[str]
    pve_token_name: Optional[str]
    pve_verify_ssl: bool

    # vSphere fields (password excluded)
    vsphere_host: Optional[str]
    vsphere_user: Optional[str]
    vsphere_port: int
    vsphere_verify_ssl: bool
    vsphere_datacenter: Optional[str]
    vsphere_cluster: Optional[str]

    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnvironmentListItem(BaseModel):
    """Minimal representation for the frontend dropdown."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    environment_type: str
    location_id: Optional[int]
    location_name: Optional[str]
    is_default: bool

    model_config = {"from_attributes": True}


# Backward compatibility aliases
PVEEnvironmentCreate = EnvironmentCreate
PVEEnvironmentUpdate = EnvironmentUpdate
PVEEnvironmentResponse = EnvironmentResponse
PVEEnvironmentListItem = EnvironmentListItem
