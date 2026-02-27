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


async def _upgrade_os_template_table(conn):
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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade_os_template_table)
        await conn.run_sync(Base.metadata.create_all)
