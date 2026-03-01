# Backward-compatibility shim — canonical model is now in environment.py
from app.models.environment import Environment as PVEEnvironment

__all__ = ["PVEEnvironment"]
