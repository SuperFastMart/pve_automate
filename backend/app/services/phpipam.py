import logging
from typing import Optional

import httpx

from app.config import get_effective_settings

logger = logging.getLogger(__name__)


class PhpIpamService:
    """Async client for phpIPAM REST API using static token auth."""

    def __init__(self, base_url: str, app_id: str, token: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/api/{app_id}",
            headers={
                "token": token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
            verify=False,
        )

    async def close(self):
        await self._client.aclose()

    async def test_connection(self) -> list[dict]:
        """Verify auth by fetching subnets. Returns the subnet list."""
        resp = await self._client.get("/subnets/")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(data.get("message", "phpIPAM returned an error"))
        return data.get("data", [])

    async def get_subnets(self) -> list[dict]:
        """Get all subnets with usage info."""
        resp = await self._client.get("/subnets/")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        subnets = []
        for s in data.get("data", []):
            subnets.append({
                "id": int(s["id"]),
                "subnet": s.get("subnet", ""),
                "mask": s.get("mask", ""),
                "description": s.get("description", ""),
                "vlanId": s.get("vlanId"),
                "sectionId": s.get("sectionId"),
                "location": s.get("location"),
                "usage": s.get("usage", {}),
            })
        return subnets

    async def get_locations(self) -> list[dict]:
        """Fetch all locations from phpIPAM."""
        resp = await self._client.get("/tools/locations/")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        return [
            {
                "id": int(loc["id"]),
                "name": loc.get("name", ""),
                "description": loc.get("description", ""),
                "address": loc.get("address", ""),
            }
            for loc in data.get("data", [])
        ]

    async def allocate_ip(
        self, subnet_id: int, hostname: str, description: str = "",
        owner: str = "",
    ) -> dict:
        """Allocate the first available IP in a subnet.

        Returns {"id": <phpipam_record_id>, "ip": "<address>"}.
        """
        payload = {
            "hostname": hostname,
            "description": description,
        }
        if owner:
            payload["owner"] = owner
        resp = await self._client.post(
            f"/addresses/first_free/{subnet_id}/",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(
                data.get("message", f"Failed to allocate IP from subnet {subnet_id}")
            )
        return {
            "id": int(data["id"]),
            "ip": data["data"],
        }

    async def update_ip(self, address_id: int, **fields) -> None:
        """Update fields on an existing IP address record."""
        resp = await self._client.patch(f"/addresses/{address_id}/", json=fields)
        resp.raise_for_status()

    async def release_ip(self, address_id: int) -> None:
        """Delete an IP address record by its phpIPAM ID."""
        resp = await self._client.delete(f"/addresses/{address_id}/")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise Exception(
                data.get("message", f"Failed to release address {address_id}")
            )


async def get_phpipam_service(db) -> Optional[PhpIpamService]:
    """Build PhpIpamService from effective settings. Returns None if unconfigured."""
    settings = await get_effective_settings(db, group="phpipam")
    base_url = settings.get("PHPIPAM_URL", "")
    app_id = settings.get("PHPIPAM_APP_ID", "")
    token = settings.get("PHPIPAM_TOKEN", "")

    if not base_url or not app_id or not token:
        return None

    return PhpIpamService(base_url=base_url, app_id=app_id, token=token)
