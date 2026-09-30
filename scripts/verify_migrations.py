#!/usr/bin/env python3
"""
Verify Database Schema, Migrations, and pgvector Extension.

Used by CI and deployment pipelines to assert that Alembic migrations have
been applied completely and that required PostgreSQL extensions are active.
"""

import asyncio
import os
import sys
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_migrations")


async def verify_schema() -> None:
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://cachemind:cachemind@localhost:5432/cachemind_test",
    )
    logger.info("Connecting to database: %s", db_url.split("@")[-1] if "@" in db_url else db_url)

    engine = create_async_engine(db_url, echo=False)

    try:
        async with engine.connect() as conn:
            # 1. Check basic database connectivity
            res = await conn.execute(text("SELECT 1"))
            assert res.scalar() == 1, "Database connectivity test failed"
            logger.info("[PASS] Database connection verified.")

            # 2. Check alembic_version table exists and has revisions
            res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = [r[0] for r in res.fetchall()]
            if not versions:
                raise RuntimeError("alembic_version table is empty. No migrations applied.")
            logger.info("[PASS] Alembic migrations active revision: %s", versions)

            # 3. Check core application tables exist
            tables_to_check = [
                "tenants",
                "projects",
                "api_keys",
                "request_logs",
                "semantic_cache_entries",
            ]
            for table in tables_to_check:
                res = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = res.scalar()
                logger.info("[PASS] Table '%s' confirmed (current row count: %d).", table, count)

            # 4. Check pgvector extension on PostgreSQL
            dialect_name = engine.dialect.name
            if dialect_name == "postgresql":
                res = await conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                )
                ext = res.scalar_one_or_none()
                if ext != "vector":
                    raise RuntimeError(
                        "pgvector extension ('vector') is NOT installed in PostgreSQL."
                    )
                logger.info("[PASS] PostgreSQL 'vector' (pgvector) extension is active.")
            else:
                logger.info("[INFO] Non-PostgreSQL dialect (%s), skipping pg_extension check.", dialect_name)

        logger.info("All schema and extension verifications passed successfully.")

    except Exception as exc:
        logger.error("[FAIL] Database verification failed: %s", exc)
        sys.exit(1)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(verify_schema())


if __name__ == "__main__":
    main()
