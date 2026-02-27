from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PVETemplateResponse(BaseModel):
    """A template VM discovered from Proxmox."""
    vmid: int
    name: str
    node: str
    status: str
    disk_size: int
    memory: int
    environment_id: Optional[int] = None
    environment_name: Optional[str] = None


class OSTemplateMappingCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: str = Field(..., min_length=1, max_length=200)
    vmid: int
    node: str
    os_family: str = Field(..., pattern=r"^(linux|windows)$")
    cloud_init: bool = True
    enabled: bool = True
    environment_id: Optional[int] = None


class OSTemplateMappingUpdate(BaseModel):
    key: Optional[str] = Field(None, min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    vmid: Optional[int] = None
    node: Optional[str] = None
    os_family: Optional[str] = Field(None, pattern=r"^(linux|windows)$")
    cloud_init: Optional[bool] = None
    enabled: Optional[bool] = None
    environment_id: Optional[int] = None


class OSTemplateMappingResponse(BaseModel):
    id: int
    key: str
    display_name: str
    vmid: int
    node: str
    os_family: str
    cloud_init: bool
    enabled: bool
    environment_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
