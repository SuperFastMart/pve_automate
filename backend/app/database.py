import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    get_settings().DATABASE_URL,
    echo=False,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


def _upgrade_os_template_table(conn):
    """Rebuild os_template_mappings to add environment_id and composite unique constraint."""
    result = conn.execute(text("PRAGMA table_info(os_template_mappings)"))
    columns = [row[1] for row in result]
    if not columns or "environment_id" in columns:
        return  # Table doesn't exist yet (create_all will handle) or already migrated

    logger.info("Migrating os_template_mappings: adding environment_id column")
    conn.execute(text("""
        CREATE TABLE os_template_mappings_new (
            id INTEGER PRIMARY KEY,
            key VARCHAR(50) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            vmid INTEGER NOT NULL,
            node VARCHAR(100) NOT NULL,
            os_family VARCHAR(20) NOT NULL,
            cloud_init BOOLEAN NOT NULL DEFAULT 1,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            environment_id INTEGER REFERENCES pve_environments(id),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE(key, environment_id)
        )
    """))
    conn.execute(text("""
        INSERT INTO os_template_mappings_new
            (id, key, display_name, vmid, node, os_family, cloud_init, enabled, created_at, updated_at)
        SELECT id, key, display_name, vmid, node, os_family, cloud_init, enabled, created_at, updated_at
        FROM os_template_mappings
    """))
    conn.execute(text("DROP TABLE os_template_mappings"))
    conn.execute(text("ALTER TABLE os_template_mappings_new RENAME TO os_template_mappings"))
    conn.execute(text("CREATE INDEX ix_os_template_mappings_key ON os_template_mappings(key)"))
    logger.info("Migration complete: os_template_mappings now has environment_id")


def _upgrade_environments_table(conn):
    """Add environment_type, location, and vSphere columns to pve_environments.

    Also rebuilds the table to make pve_* credentials nullable (they're only needed for
    Proxmox type; ESXi/vCenter use vsphere_* fields instead).
    """
    result = conn.execute(text("PRAGMA table_info(pve_environments)"))
    rows = list(result)
    columns = {row[1]: row for row in rows}
    if not columns:
        return  # Table doesn't exist yet — create_all will handle it

    if "environment_type" in columns:
        return  # Already migrated

    logger.info("Migrating pve_environments: rebuilding for multi-hypervisor support")
    conn.execute(text("""
        CREATE TABLE pve_environments_v2 (
            id INTEGER PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE,
            display_name VARCHAR(200) NOT NULL,
            description TEXT,
            environment_type VARCHAR(20) NOT NULL DEFAULT 'proxmox',
            location_id INTEGER,
            location_name VARCHAR(200),
            pve_host VARCHAR(255),
            pve_user VARCHAR(255),
            pve_token_name VARCHAR(255),
            pve_token_value TEXT,
            pve_verify_ssl BOOLEAN NOT NULL DEFAULT 0,
            vsphere_host VARCHAR(255),
            vsphere_user VARCHAR(255),
            vsphere_password TEXT,
            vsphere_port INTEGER NOT NULL DEFAULT 443,
            vsphere_verify_ssl BOOLEAN NOT NULL DEFAULT 0,
            vsphere_datacenter VARCHAR(255),
            vsphere_cluster VARCHAR(255),
            enabled BOOLEAN NOT NULL DEFAULT 1,
            is_default BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """))
    # Copy existing data — all existing rows are Proxmox type
    src_cols = "id, name, display_name, description, pve_host, pve_user, pve_token_name, pve_token_value, pve_verify_ssl, enabled, is_default, created_at, updated_at"
    conn.execute(text(f"""
        INSERT INTO pve_environments_v2
            ({src_cols}, environment_type)
        SELECT {src_cols}, 'proxmox'
        FROM pve_environments
    """))
    conn.execute(text("DROP TABLE pve_environments"))
    conn.execute(text("ALTER TABLE pve_environments_v2 RENAME TO pve_environments"))
    conn.execute(text("CREATE UNIQUE INDEX ix_pve_environments_name ON pve_environments(name)"))
    logger.info("Migration complete: pve_environments rebuilt for multi-hypervisor support")


def _upgrade_vm_requests_table(conn):
    """Add generic hypervisor outcome fields to vm_requests."""
    result = conn.execute(text("PRAGMA table_info(vm_requests)"))
    columns = [row[1] for row in result]
    if not columns or "hypervisor_vm_id" in columns:
        return

    logger.info("Migrating vm_requests: adding generic hypervisor fields")
    conn.execute(text("ALTER TABLE vm_requests ADD COLUMN hypervisor_vm_id VARCHAR(200)"))
    conn.execute(text("ALTER TABLE vm_requests ADD COLUMN hypervisor_host VARCHAR(200)"))
    # Backfill from existing Proxmox fields
    conn.execute(text("""
        UPDATE vm_requests SET
            hypervisor_vm_id = CAST(proxmox_vmid AS TEXT),
            hypervisor_host = proxmox_node
        WHERE proxmox_vmid IS NOT NULL
    """))
    logger.info("Migration complete: vm_requests now has generic hypervisor fields")


def _upgrade_os_templates_add_template_ref(conn):
    """Add template_ref column and make vmid/node nullable for vSphere support.

    SQLite can't ALTER COLUMN, so we rebuild the table when vmid is still NOT NULL.
    """
    result = conn.execute(text("PRAGMA table_info(os_template_mappings)"))
    rows = list(result)
    columns = {row[1]: row for row in rows}  # name -> full row
    if not columns:
        return  # Table doesn't exist yet

    has_template_ref = "template_ref" in columns
    # Check if vmid is still NOT NULL (index 3 = notnull flag)
    vmid_not_null = columns.get("vmid", (None,) * 4)[3] == 1 if "vmid" in columns else False

    if has_template_ref and not vmid_not_null:
        return  # Fully migrated already

    if not has_template_ref and not vmid_not_null:
        # Just need to add template_ref
        logger.info("Migrating os_template_mappings: adding template_ref column")
        conn.execute(text("ALTER TABLE os_template_mappings ADD COLUMN template_ref VARCHAR(500)"))
        logger.info("Migration complete: os_template_mappings now has template_ref")
        return

    # Need to rebuild table to fix nullable + add template_ref
    logger.info("Migrating os_template_mappings: rebuilding for nullable vmid/node + template_ref")
    conn.execute(text("""
        CREATE TABLE os_template_mappings_v2 (
            id INTEGER PRIMARY KEY,
            key VARCHAR(50) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            vmid INTEGER,
            node VARCHAR(100),
            template_ref VARCHAR(500),
            os_family VARCHAR(20) NOT NULL,
            cloud_init BOOLEAN NOT NULL DEFAULT 1,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            environment_id INTEGER REFERENCES pve_environments(id),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE(key, environment_id)
        )
    """))
    # Copy existing data (template_ref will be NULL for all existing rows)
    src_cols = "id, key, display_name, vmid, node, os_family, cloud_init, enabled, environment_id, created_at, updated_at"
    conn.execute(text(f"""
        INSERT INTO os_template_mappings_v2 ({src_cols})
        SELECT {src_cols} FROM os_template_mappings
    """))
    conn.execute(text("DROP TABLE os_template_mappings"))
    conn.execute(text("ALTER TABLE os_template_mappings_v2 RENAME TO os_template_mappings"))
    conn.execute(text("CREATE INDEX ix_os_template_mappings_key ON os_template_mappings(key)"))
    logger.info("Migration complete: os_template_mappings rebuilt with nullable vmid/node + template_ref")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade_os_template_table)
        await conn.run_sync(_upgrade_environments_table)
        await conn.run_sync(_upgrade_vm_requests_table)
        await conn.run_sync(_upgrade_os_templates_add_template_ref)
        await conn.run_sync(Base.metadata.create_all)
