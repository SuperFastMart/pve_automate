import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    GROUP_DISPLAY_NAMES,
    SETTINGS_REGISTRY,
    get_effective_settings,
    get_settings,
)
from app.database import get_db
from app.models.os_template import OSTemplateMapping
from app.models.setting import Setting
from app.schemas.os_template import (
    OSTemplateMappingCreate,
    OSTemplateMappingResponse,
    OSTemplateMappingUpdate,
    PVETemplateResponse,
)
from app.schemas.setting import (
    ConnectionTestResult,
    SettingResponse,
    SettingsBulkUpdate,
    SettingsGroupResponse,
    SettingUpdate,
)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _mask_value(value: str) -> str:
    if len(value) > 4:
        return "****" + value[-4:]
    return "****"


def _build_setting_response(
    key: str, value: str, meta: dict, db_keys: set[str]
) -> SettingResponse:
    source = "database" if key in db_keys else "env"
    display_value = _mask_value(value) if meta["is_secret"] and value else value
    return SettingResponse(
        key=key,
        value=display_value,
        group=meta["group"],
        display_name=meta["display_name"],
        is_secret=meta["is_secret"],
        source=source,
    )


@router.get("", response_model=list[SettingsGroupResponse])
async def list_all_settings(db: AsyncSession = Depends(get_db)):
    """List all settings grouped by integration."""
    env_settings = get_settings()

    result = await db.execute(select(Setting))
    db_keys = {s.key for s in result.scalars().all()}

    effective = await get_effective_settings(db)

    groups: dict[str, list[SettingResponse]] = {}
    for key, meta in SETTINGS_REGISTRY.items():
        group = meta["group"]
        value = effective.get(key, str(getattr(env_settings, key, "")))
        setting_resp = _build_setting_response(key, value, meta, db_keys)
        groups.setdefault(group, []).append(setting_resp)

    return [
        SettingsGroupResponse(
            group=group,
            display_name=GROUP_DISPLAY_NAMES.get(group, group),
            settings=settings,
        )
        for group, settings in groups.items()
    ]


# ── Template management (must be before /{group} and /{key} wildcards) ───


@router.get("/templates/scan", response_model=list[PVETemplateResponse])
async def scan_proxmox_templates(db: AsyncSession = Depends(get_db)):
    """Query Proxmox for all template VMs across all nodes."""
    try:
        settings = await get_effective_settings(db, group="proxmox")
        host = settings.get("PVE_HOST", "")
        if not host:
            raise HTTPException(status_code=400, detail="PVE_HOST is not configured")

        from app.services.proxmox import ProxmoxService

        pve = ProxmoxService(
            host=host,
            user=settings["PVE_USER"],
            token_name=settings["PVE_TOKEN_NAME"],
            token_value=settings["PVE_TOKEN_VALUE"],
            verify_ssl=settings.get("PVE_VERIFY_SSL", "false").lower() in ("true", "1", "yes"),
        )
        templates = await asyncio.to_thread(pve.get_templates)
        return templates
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=list[OSTemplateMappingResponse])
async def list_template_mappings(db: AsyncSession = Depends(get_db)):
    """List all saved template mappings."""
    result = await db.execute(
        select(OSTemplateMapping).order_by(OSTemplateMapping.os_family, OSTemplateMapping.display_name)
    )
    return result.scalars().all()


@router.post("/templates", response_model=OSTemplateMappingResponse, status_code=201)
async def create_template_mapping(
    payload: OSTemplateMappingCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new template mapping."""
    existing = await db.execute(
        select(OSTemplateMapping).where(OSTemplateMapping.key == payload.key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Template key '{payload.key}' already exists")

    mapping = OSTemplateMapping(**payload.model_dump())
    db.add(mapping)
    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.put("/templates/{template_id}", response_model=OSTemplateMappingResponse)
async def update_template_mapping(
    template_id: int, payload: OSTemplateMappingUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a template mapping."""
    result = await db.execute(
        select(OSTemplateMapping).where(OSTemplateMapping.id == template_id)
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Template mapping not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mapping, field, value)

    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template_mapping(
    template_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete a template mapping."""
    result = await db.execute(
        select(OSTemplateMapping).where(OSTemplateMapping.id == template_id)
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise HTTPException(status_code=404, detail="Template mapping not found")

    await db.delete(mapping)
    await db.commit()


@router.post("/proxmox/test", response_model=ConnectionTestResult)
async def test_proxmox_connection(db: AsyncSession = Depends(get_db)):
    """Test connectivity to Proxmox with current effective settings."""
    try:
        settings = await get_effective_settings(db, group="proxmox")

        host = settings.get("PVE_HOST", "")
        if not host:
            return ConnectionTestResult(success=False, message="PVE_HOST is not configured")

        from app.services.proxmox import ProxmoxService

        pve = ProxmoxService(
            host=host,
            user=settings["PVE_USER"],
            token_name=settings["PVE_TOKEN_NAME"],
            token_value=settings["PVE_TOKEN_VALUE"],
            verify_ssl=settings.get("PVE_VERIFY_SSL", "false").lower() in ("true", "1", "yes"),
        )

        version = await asyncio.to_thread(pve.get_version)
        return ConnectionTestResult(
            success=True,
            message=f"Connected to Proxmox VE {version.get('version', 'unknown')} (release {version.get('release', 'unknown')})",
        )
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))


@router.post("/jira/test", response_model=ConnectionTestResult)
async def test_jira_connection(db: AsyncSession = Depends(get_db)):
    """Test connectivity to Jira Cloud with current effective settings."""
    try:
        from app.services.jira import get_jira_service

        jira = await get_jira_service(db)
        if not jira:
            return ConnectionTestResult(
                success=False,
                message="Jira is not configured (missing URL, email, or API token)",
            )

        user_info = await jira.test_connection()
        display = user_info.get("displayName", user_info.get("emailAddress", "unknown"))
        await jira.close()
        return ConnectionTestResult(
            success=True,
            message=f"Connected to Jira as {display}",
        )
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))


@router.post("/phpipam/test", response_model=ConnectionTestResult)
async def test_phpipam_connection(db: AsyncSession = Depends(get_db)):
    """Test connectivity to phpIPAM with current effective settings."""
    try:
        from app.services.phpipam import get_phpipam_service

        ipam = await get_phpipam_service(db)
        if not ipam:
            return ConnectionTestResult(
                success=False,
                message="phpIPAM is not configured (missing URL, App ID, or Token)",
            )

        subnets = await ipam.test_connection()
        await ipam.close()
        return ConnectionTestResult(
            success=True,
            message=f"Connected to phpIPAM — {len(subnets)} subnet(s) available",
        )
    except Exception as e:
        return ConnectionTestResult(success=False, message=str(e))


# ── Settings CRUD (wildcard routes last) ─────────────────────────────


@router.get("/{group}", response_model=SettingsGroupResponse)
async def list_group_settings(group: str, db: AsyncSession = Depends(get_db)):
    """List settings for a specific integration group."""
    if group not in GROUP_DISPLAY_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown group: {group}")

    env_settings = get_settings()
    result = await db.execute(select(Setting).where(Setting.group == group))
    db_keys = {s.key for s in result.scalars().all()}

    effective = await get_effective_settings(db, group=group)

    settings = []
    for key, meta in SETTINGS_REGISTRY.items():
        if meta["group"] != group:
            continue
        value = effective.get(key, str(getattr(env_settings, key, "")))
        settings.append(_build_setting_response(key, value, meta, db_keys))

    return SettingsGroupResponse(
        group=group,
        display_name=GROUP_DISPLAY_NAMES[group],
        settings=settings,
    )


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str, payload: SettingUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a single setting (upsert)."""
    if key not in SETTINGS_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")

    meta = SETTINGS_REGISTRY[key]

    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = payload.value
    else:
        setting = Setting(
            key=key,
            value=payload.value,
            group=meta["group"],
            display_name=meta["display_name"],
            is_secret=meta["is_secret"],
        )
        db.add(setting)

    await db.commit()
    await db.refresh(setting)

    display_value = _mask_value(setting.value) if meta["is_secret"] and setting.value else setting.value
    return SettingResponse(
        key=setting.key,
        value=display_value,
        group=setting.group,
        display_name=setting.display_name,
        is_secret=setting.is_secret,
        source="database",
    )


@router.put("/{group}/bulk", response_model=list[SettingResponse])
async def bulk_update_settings(
    group: str, payload: SettingsBulkUpdate, db: AsyncSession = Depends(get_db)
):
    """Bulk-update all settings for a group."""
    if group not in GROUP_DISPLAY_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown group: {group}")

    responses = []
    for key, value in payload.settings.items():
        if key not in SETTINGS_REGISTRY:
            continue
        meta = SETTINGS_REGISTRY[key]
        if meta["group"] != group:
            continue

        result = await db.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
        else:
            setting = Setting(
                key=key,
                value=value,
                group=meta["group"],
                display_name=meta["display_name"],
                is_secret=meta["is_secret"],
            )
            db.add(setting)

    await db.commit()

    # Re-fetch all for response
    effective = await get_effective_settings(db, group=group)
    result = await db.execute(select(Setting).where(Setting.group == group))
    db_keys = {s.key for s in result.scalars().all()}

    for key, meta in SETTINGS_REGISTRY.items():
        if meta["group"] != group:
            continue
        value = effective.get(key, "")
        responses.append(_build_setting_response(key, value, meta, db_keys))

    return responses


@router.delete("/{key}", response_model=SettingResponse)
async def delete_setting(key: str, db: AsyncSession = Depends(get_db)):
    """Remove a DB override, reverting to .env default."""
    if key not in SETTINGS_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")

    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if setting:
        await db.delete(setting)
        await db.commit()

    meta = SETTINGS_REGISTRY[key]
    env_value = str(getattr(get_settings(), key, ""))
    display_value = _mask_value(env_value) if meta["is_secret"] and env_value else env_value

    return SettingResponse(
        key=key,
        value=display_value,
        group=meta["group"],
        display_name=meta["display_name"],
        is_secret=meta["is_secret"],
        source="env",
    )
