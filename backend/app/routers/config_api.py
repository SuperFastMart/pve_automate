import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import load_templates, load_tshirt_sizes, load_workload_types
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


@router.get("/subnets")
async def get_subnets(db: AsyncSession = Depends(get_db)):
    """Fetch available subnets from phpIPAM. Returns empty list if not configured."""
    try:
        from app.services.phpipam import get_phpipam_service

        ipam = await get_phpipam_service(db)
        if not ipam:
            return []
        subnets = await ipam.get_subnets()
        await ipam.close()
        return subnets
    except Exception as e:
        logger.warning(f"Failed to fetch subnets from phpIPAM: {e}")
        return []
