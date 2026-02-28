import logging
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)


class AuthenticatedUser(BaseModel):
    """Represents the authenticated user extracted from the JWT."""

    name: str
    email: str
    oid: str  # Azure object ID — unique user identifier
    roles: list[str] = []

    @property
    def is_admin(self) -> bool:
        return "Admin" in self.roles


# ── JWKS key cache ──────────────────────────────────────────────────

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour


async def _get_jwks(tenant_id: str) -> dict:
    """Fetch and cache Microsoft's JWKS (public signing keys)."""
    global _jwks_cache, _jwks_fetched_at

    now = datetime.now(timezone.utc).timestamp()
    if _jwks_cache and (now - _jwks_fetched_at) < JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
        return _jwks_cache


# ── Token extraction and validation ─────────────────────────────────


def _extract_bearer_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header[7:]


async def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency: validate JWT and return the authenticated user.

    Usage:
        @router.get("/something")
        async def endpoint(user: AuthenticatedUser = Depends(get_current_user)):
            ...
    """
    settings = get_settings()
    tenant_id = settings.ENTRA_TENANT_ID
    client_id = settings.ENTRA_CLIENT_ID

    if not tenant_id or not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra ID authentication is not configured",
        )

    token = _extract_bearer_token(request)

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        jwks = await _get_jwks(tenant_id)
        rsa_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate signing key",
            )

        unverified_claims = jwt.get_unverified_claims(token)

        # Accept both v1 and v2 issuer formats
        valid_issuers = [
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            f"https://sts.windows.net/{tenant_id}/",
        ]
        token_issuer = unverified_claims.get("iss", "")
        if token_issuer not in valid_issuers:
            raise JWTError(f"Invalid issuer: {token_issuer}")

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_iss": False},  # We already verified issuer above
        )

        return AuthenticatedUser(
            name=payload.get("name", "Unknown"),
            email=payload.get("preferred_username", payload.get("upn", payload.get("email", ""))),
            oid=payload.get("oid", ""),
            roles=payload.get("roles", []),
        )

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """FastAPI dependency: require the Admin role.

    Usage:
        @router.post("/admin-action")
        async def endpoint(user: AuthenticatedUser = Depends(require_admin)):
            ...
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
