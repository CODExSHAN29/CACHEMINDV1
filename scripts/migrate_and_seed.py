"""
Enterprise Database Migration & Initialization CLI Utility

Supports running asynchronous migrations, checking schema status,
verifying pool connectivity, and seeding initial tenant records.

Usage:
    python -m scripts.migrate_and_seed --upgrade
    python -m scripts.migrate_and_seed --check
    python -m scripts.migrate_and_seed --seed
"""

import argparse
import asyncio
import logging
import sys
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from backend.app.config import settings
from backend.auth.keys import generate_api_key
from backend.db.models import APIKey, Project, Tenant
from backend.db.session import AsyncSessionLocal, create_engine_for_url, get_pool_status, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cachemind.migration_cli")


def get_alembic_config() -> Config:
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return alembic_cfg


def run_upgrade(revision: str = "head") -> None:
    """Executes database upgrade to the specified target revision."""
    logger.info("Applying database migrations up to '%s' on %s...", revision, settings.DATABASE_URL)
    cfg = get_alembic_config()
    command.upgrade(cfg, revision)
    logger.info("Database migration completed successfully.")


def run_downgrade(revision: str) -> None:
    """Executes database downgrade to the specified target revision."""
    logger.info("Downgrading database to '%s' on %s...", revision, settings.DATABASE_URL)
    cfg = get_alembic_config()
    command.downgrade(cfg, revision)
    logger.info("Database downgrade completed successfully.")


async def verify_connectivity() -> bool:
    """Verifies database connectivity and inspects pool status."""
    logger.info("Testing async database connectivity...")
    try:
        engine = create_engine_for_url(settings.DATABASE_URL)
        async with engine.connect() as conn:
            from sqlalchemy import text
            result = await conn.execute(text("SELECT 1"))
            val = result.scalar()
            assert val == 1
        await engine.dispose()
        pool_status = get_pool_status()
        logger.info("Database connectivity verified! Pool status: %s", pool_status)
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed: %s", exc)
        return False


async def seed_default_dev_fixtures() -> None:
    """Seeds default dev tenant and project if not already present."""
    logger.info("Checking for default dev fixtures in database...")
    import backend.db.session as db_session_mod
    async with db_session_mod.AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == settings.DEV_TENANT_ID)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            logger.info("Creating default tenant '%s'...", settings.DEV_TENANT_ID)
            tenant = Tenant(
                id=settings.DEV_TENANT_ID,
                name="Default Development Tenant",
                is_active=True,
            )
            session.add(tenant)
            await session.flush()

        result = await session.execute(
            select(Project).where(Project.id == settings.DEV_PROJECT_ID)
        )
        project = result.scalar_one_or_none()

        if not project:
            logger.info("Creating default project '%s'...", settings.DEV_PROJECT_ID)
            project = Project(
                id=settings.DEV_PROJECT_ID,
                tenant_id=tenant.id,
                name="Default Development Project",
                is_active=True,
            )
            session.add(project)
            await session.flush()

        # Check for dev key
        import hashlib
        key_hash = hashlib.sha256(settings.DEV_API_KEY.encode()).hexdigest()
        result = await session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            logger.info("Registering default development API Key...")
            api_key = APIKey(
                project_id=project.id,
                key_prefix=settings.DEV_API_KEY[:8],
                key_hash=key_hash,
                name="Default Dev Key",
                role="admin",
                is_active=True,
            )
            session.add(api_key)

        await session.commit()
        logger.info("Default fixtures seeded successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Database Migration & Operations CLI")
    parser.add_argument("--upgrade", nargs="?", const="head", help="Run migrations up to revision (default: head)")
    parser.add_argument("--downgrade", help="Downgrade migrations to specified revision (e.g. -1, base)")
    parser.add_argument("--check", action="store_true", help="Verify database connection and pool health")
    parser.add_argument("--seed", action="store_true", help="Seed default development tenant and fixtures")

    args = parser.parse_args()

    if args.upgrade:
        run_upgrade(args.upgrade)
    elif args.downgrade:
        run_downgrade(args.downgrade)

    if args.check:
        connected = asyncio.run(verify_connectivity())
        if not connected:
            sys.exit(1)

    if args.seed:
        asyncio.run(seed_default_dev_fixtures())

    if not any([args.upgrade, args.downgrade, args.check, args.seed]):
        parser.print_help()


if __name__ == "__main__":
    main()
