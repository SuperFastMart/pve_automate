from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./peevinator.db"

    # Proxmox
    PVE_HOST: str = ""
    PVE_USER: str = ""
    PVE_TOKEN_NAME: str = ""
    PVE_TOKEN_VALUE: str = ""
    PVE_VERIFY_SSL: bool = False

    # Jira Cloud
    JIRA_BASE_URL: str = ""
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_PROJECT_KEY: str = "INFRA"
    JIRA_ISSUE_TYPE: str = "Service Request"
    JIRA_APPROVE_STATUS: str = "Approved"
    JIRA_REJECT_STATUS: str = "Declined"
    JIRA_WEBHOOK_SECRET: str = ""

    # phpIPAM
    PHPIPAM_URL: str = ""
    PHPIPAM_APP_ID: str = ""
    PHPIPAM_TOKEN: str = ""
    PHPIPAM_USER: str = ""
    PHPIPAM_PASSWORD: str = ""
    PHPIPAM_DEFAULT_SUBNET_ID: int = 10

    # SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: str = "peevinator@example.com"

    # Application
    APP_BASE_URL: str = "http://localhost:8000"
    NODE_SELECTION_STRATEGY: str = "least_memory"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Registry of all configurable settings with metadata
SETTINGS_REGISTRY: dict[str, dict] = {
    # Proxmox
    "PVE_HOST":        {"group": "proxmox", "display_name": "Proxmox Host",    "is_secret": False},
    "PVE_USER":        {"group": "proxmox", "display_name": "Proxmox User",    "is_secret": False},
    "PVE_TOKEN_NAME":  {"group": "proxmox", "display_name": "API Token Name",  "is_secret": False},
    "PVE_TOKEN_VALUE": {"group": "proxmox", "display_name": "API Token Value", "is_secret": True},
    "PVE_VERIFY_SSL":  {"group": "proxmox", "display_name": "Verify SSL",      "is_secret": False},
    # Jira
    "JIRA_BASE_URL":       {"group": "jira", "display_name": "Jira Base URL",    "is_secret": False},
    "JIRA_EMAIL":          {"group": "jira", "display_name": "Jira Email",       "is_secret": False},
    "JIRA_API_TOKEN":      {"group": "jira", "display_name": "Jira API Token",   "is_secret": True},
    "JIRA_PROJECT_KEY":    {"group": "jira", "display_name": "Jira Project Key", "is_secret": False},
    "JIRA_ISSUE_TYPE":     {"group": "jira", "display_name": "Issue Type",       "is_secret": False},
    "JIRA_APPROVE_STATUS": {"group": "jira", "display_name": "Approve Status",  "is_secret": False},
    "JIRA_REJECT_STATUS":  {"group": "jira", "display_name": "Reject Status",   "is_secret": False},
    "JIRA_WEBHOOK_SECRET": {"group": "jira", "display_name": "Webhook Secret",  "is_secret": True},
    # phpIPAM
    "PHPIPAM_URL":               {"group": "phpipam", "display_name": "phpIPAM URL",         "is_secret": False},
    "PHPIPAM_APP_ID":            {"group": "phpipam", "display_name": "App ID",              "is_secret": False},
    "PHPIPAM_TOKEN":             {"group": "phpipam", "display_name": "API Token",           "is_secret": True},
    "PHPIPAM_USER":              {"group": "phpipam", "display_name": "phpIPAM User",        "is_secret": False},
    "PHPIPAM_PASSWORD":          {"group": "phpipam", "display_name": "phpIPAM Password",    "is_secret": True},
    "PHPIPAM_DEFAULT_SUBNET_ID": {"group": "phpipam", "display_name": "Default Subnet ID",  "is_secret": False},
    # SMTP
    "SMTP_HOST":     {"group": "smtp", "display_name": "SMTP Host",           "is_secret": False},
    "SMTP_PORT":     {"group": "smtp", "display_name": "SMTP Port",           "is_secret": False},
    "SMTP_USER":     {"group": "smtp", "display_name": "SMTP User",           "is_secret": False},
    "SMTP_PASSWORD": {"group": "smtp", "display_name": "SMTP Password",       "is_secret": True},
    "SMTP_USE_TLS":  {"group": "smtp", "display_name": "Use TLS",             "is_secret": False},
    "EMAIL_FROM":    {"group": "smtp", "display_name": "Email From Address",  "is_secret": False},
}

GROUP_DISPLAY_NAMES = {
    "proxmox": "Proxmox",
    "jira": "Jira Cloud",
    "phpipam": "phpIPAM",
    "smtp": "SMTP / Email",
}


async def get_effective_settings(
    db, group: Optional[str] = None
) -> dict[str, str]:
    """Return all settings with DB values overriding .env defaults."""
    from sqlalchemy import select
    from app.models.setting import Setting

    env_settings = get_settings()

    query = select(Setting)
    if group:
        query = query.where(Setting.group == group)
    result = await db.execute(query)
    db_settings = {s.key: s.value for s in result.scalars().all()}

    effective = {}
    for key, meta in SETTINGS_REGISTRY.items():
        if group and meta["group"] != group:
            continue
        if key in db_settings and db_settings[key] != "":
            effective[key] = db_settings[key]
        else:
            effective[key] = str(getattr(env_settings, key, ""))

    return effective


async def get_effective_setting(key: str, db) -> str:
    """Get a single setting value with DB override."""
    from sqlalchemy import select
    from app.models.setting import Setting

    result = await db.execute(select(Setting).where(Setting.key == key))
    db_setting = result.scalar_one_or_none()
    if db_setting and db_setting.value != "":
        return db_setting.value
    return str(getattr(get_settings(), key, ""))


CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_tshirt_sizes() -> dict:
    with open(CONFIG_DIR / "tshirt_sizes.yaml") as f:
        return yaml.safe_load(f)["sizes"]


def load_templates() -> dict:
    with open(CONFIG_DIR / "templates.yaml") as f:
        return yaml.safe_load(f)["templates"]


def load_workload_types() -> list:
    with open(CONFIG_DIR / "templates.yaml") as f:
        return yaml.safe_load(f)["workload_types"]
