import asyncio
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_effective_settings, load_templates, load_tshirt_sizes, load_workload_types
from app.database import get_db
from app.models.os_template import OSTemplateMapping

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])


@router.get("/tshirt-sizes")
async def get_tshirt_sizes():
    return load_tshirt_sizes()


@router.get("/os-templates")
async def get_os_templates(db: AsyncSession = Depends(get_db)):
    """Return OS templates. Reads from DB if mappings exist, else falls back to YAML."""
    result = await db.execute(
        select(OSTemplateMapping)
        .where(OSTemplateMapping.enabled == True)
        .order_by(OSTemplateMapping.os_family, OSTemplateMapping.display_name)
    )
    mappings = result.scalars().all()

    if mappings:
        return {
            m.key: {
                "display_name": m.display_name,
                "vmid": m.vmid,
                "node": m.node,
                "cloud_init": m.cloud_init,
                "os_family": m.os_family,
            }
            for m in mappings
        }

    # Fallback to YAML if no DB mappings
    return load_templates()


@router.get("/workload-types")
async def get_workload_types():
    return load_workload_types()


@router.get("/locations")
async def get_locations(db: AsyncSession = Depends(get_db)):
    """Fetch available locations from phpIPAM, filtered by allowed IDs if configured."""
    try:
        from app.services.phpipam import get_phpipam_service

        ipam = await get_phpipam_service(db)
        if not ipam:
            return []
        locations = await ipam.get_locations()
        await ipam.close()

        # Filter by allowed location IDs if configured
        settings = await get_effective_settings(db, group="phpipam")
        allowed_raw = settings.get("PHPIPAM_ALLOWED_LOCATION_IDS", "")
        if allowed_raw.strip():
            allowed_ids = {int(x.strip()) for x in allowed_raw.split(",") if x.strip()}
            locations = [loc for loc in locations if loc["id"] in allowed_ids]

        return locations
    except Exception as e:
        logger.warning(f"Failed to fetch locations from phpIPAM: {e}")
        return []


@router.get("/subnets")
async def get_subnets(db: AsyncSession = Depends(get_db)):
    """Fetch available subnets from phpIPAM, enriched with location names and filtered."""
    try:
        from app.services.phpipam import get_phpipam_service

        ipam = await get_phpipam_service(db)
        if not ipam:
            return []

        # Fetch subnets and locations concurrently
        subnets, locations = await asyncio.gather(
            ipam.get_subnets(),
            ipam.get_locations(),
        )
        await ipam.close()

        # Build location lookup
        loc_map = {loc["id"]: loc["name"] for loc in locations}

        # Read allowed location IDs
        settings = await get_effective_settings(db, group="phpipam")
        allowed_raw = settings.get("PHPIPAM_ALLOWED_LOCATION_IDS", "")
        allowed_ids = None
        if allowed_raw.strip():
            allowed_ids = {int(x.strip()) for x in allowed_raw.split(",") if x.strip()}

        # Enrich and filter subnets
        result = []
        for s in subnets:
            raw_loc = s.get("location")
            if isinstance(raw_loc, dict):
                loc_id = int(raw_loc["id"]) if raw_loc.get("id") else None
            elif raw_loc and str(raw_loc) not in ("0", ""):
                loc_id = int(raw_loc)
            else:
                loc_id = None
            loc_name = loc_map.get(loc_id) if loc_id else None

            # Filter by allowed locations if configured
            if allowed_ids is not None and loc_id not in allowed_ids:
                continue

            s["locationId"] = loc_id
            s["locationName"] = loc_name
            result.append(s)

        return result
    except Exception as e:
        logger.warning(f"Failed to fetch subnets from phpIPAM: {e}")
        return []
