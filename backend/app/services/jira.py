import logging
from typing import Optional

import httpx

from app.config import get_effective_settings

logger = logging.getLogger(__name__)


class JiraService:
    """Async client for Jira Cloud REST API v3 using basic auth."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=f"{self.base_url}/rest/api/3",
            auth=(email, api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def close(self):
        await self._client.aclose()

    async def test_connection(self) -> dict:
        """Verify credentials by fetching the authenticated user."""
        resp = await self._client.get("/myself")
        resp.raise_for_status()
        return resp.json()

    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Service Request",
    ) -> dict:
        """Create a Jira issue. Returns {key, url}."""
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "description": {
                    "version": 1,
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description}],
                        }
                    ],
                },
            }
        }
        resp = await self._client.post("/issue", json=payload)
        resp.raise_for_status()
        data = resp.json()
        issue_key = data["key"]
        issue_url = f"{self.base_url}/browse/{issue_key}"
        return {"key": issue_key, "url": issue_url}

    async def add_comment(self, issue_key: str, body: str) -> None:
        """Add a plain-text comment to an issue."""
        payload = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body}],
                    }
                ],
            }
        }
        resp = await self._client.post(f"/issue/{issue_key}/comment", json=payload)
        resp.raise_for_status()

    async def get_transitions(self, issue_key: str) -> list[dict]:
        """List available transitions for an issue."""
        resp = await self._client.get(f"/issue/{issue_key}/transitions")
        resp.raise_for_status()
        return resp.json().get("transitions", [])

    async def transition_issue(self, issue_key: str, transition_name: str) -> bool:
        """Transition an issue by transition name. Returns True if successful."""
        transitions = await self.get_transitions(issue_key)
        target = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                target = t
                break

        if not target:
            logger.warning(
                f"Transition '{transition_name}' not available for {issue_key}. "
                f"Available: {[t['name'] for t in transitions]}"
            )
            return False

        resp = await self._client.post(
            f"/issue/{issue_key}/transitions",
            json={"transition": {"id": target["id"]}},
        )
        resp.raise_for_status()
        return True


async def get_jira_service(db) -> Optional[JiraService]:
    """Build JiraService from effective settings. Returns None if unconfigured."""
    settings = await get_effective_settings(db, group="jira")
    base_url = settings.get("JIRA_BASE_URL", "")
    email = settings.get("JIRA_EMAIL", "")
    api_token = settings.get("JIRA_API_TOKEN", "")

    if not base_url or not email or not api_token:
        return None

    return JiraService(base_url=base_url, email=email, api_token=api_token)


async def get_jira_settings(db) -> dict:
    """Get all Jira-related effective settings."""
    return await get_effective_settings(db, group="jira")
