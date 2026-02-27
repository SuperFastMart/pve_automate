from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PVEEnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    pve_host: str = Field(..., min_length=1)
    pve_user: str = Field(..., min_length=1)
    pve_token_name: str = Field(..., min_length=1)
    pve_token_value: str = Field(..., min_length=1)
    pve_verify_ssl: bool = False
    enabled: bool = True
    is_default: bool = False


class PVEEnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    pve_host: Optional[str] = None
    pve_user: Optional[str] = None
    pve_token_name: Optional[str] = None
    pve_token_value: Optional[str] = None
    pve_verify_ssl: Optional[bool] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class PVEEnvironmentResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    pve_host: str
    pve_user: str
    pve_token_name: str
    pve_verify_ssl: bool
    enabled: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PVEEnvironmentListItem(BaseModel):
    """Minimal representation for the frontend dropdown."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    is_default: bool

    model_config = {"from_attributes": True}
