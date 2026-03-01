# Backward-compatibility shim — canonical schemas are now in environment.py
from app.schemas.environment import (
    EnvironmentCreate as PVEEnvironmentCreate,
    EnvironmentUpdate as PVEEnvironmentUpdate,
    EnvironmentResponse as PVEEnvironmentResponse,
    EnvironmentListItem as PVEEnvironmentListItem,
)

__all__ = [
    "PVEEnvironmentCreate",
    "PVEEnvironmentUpdate",
    "PVEEnvironmentResponse",
    "PVEEnvironmentListItem",
]
