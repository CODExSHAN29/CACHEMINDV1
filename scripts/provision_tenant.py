"""
Production Tenant & API Key Provisioning CLI

Use this script to create production tenants, projects, and cryptographically secure API keys.
Never commit generated API keys to source control.

Usage:
    python -m scripts.provision_tenant --tenant-name "Acme Corp" --project-name "Production Chatbot" --key-name "Default Live Key"
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from backend.auth.keys import generate_api_key
from backend.db.models import APIKey, Project, Tenant
from backend.db.session import AsyncSessionLocal, init_db


async def provision(
    tenant_name: str,
    project_name: str,
    key_name: str = "Production Key",
) -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        # 1. Create or fetch Tenant
        tenant = Tenant(name=tenant_name, is_active=True)
        session.add(tenant)
        await session.flush()

        # 2. Create Project
        project = Project(
            tenant_id=tenant.id,
            name=project_name,
            is_active=True,
        )
        session.add(project)
        await session.flush()

        # 3. Generate Cryptographic API Key
        raw_key, key_prefix, key_hash = generate_api_key(prefix="cm_live_")
        api_key = APIKey(
            project_id=project.id,
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=key_name,
            is_active=True,
        )
        session.add(api_key)
        await session.commit()

        print("\n" + "=" * 60)
        print("  PROVISIONING SUCCESSFUL")
        print("=" * 60)
        print(f"Tenant ID:    {tenant.id}")
        print(f"Tenant Name:  {tenant.name}")
        print(f"Project ID:   {project.id}")
        print(f"Project Name: {project.name}")
        print(f"Key Name:     {key_name}")
        print(f"Key Prefix:   {key_prefix}")
        print("-" * 60)
        print(f"RAW API KEY:  {raw_key}")
        print("-" * 60)
        print("WARNING: Store this key securely now. It cannot be retrieved again!")
        print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a new Tenant, Project, and API Key in CacheMind.")
    parser.add_argument("--tenant-name", required=True, help="Name of the tenant/organization")
    parser.add_argument("--project-name", required=True, help="Name of the project")
    parser.add_argument("--key-name", default="Production Key", help="Label for the API key")

    args = parser.parse_args()
    asyncio.run(provision(args.tenant_name, args.project_name, args.key_name))


if __name__ == "__main__":
    main()
