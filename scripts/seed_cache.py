#!/usr/bin/env python3
"""
CacheMind CLI Utility: Pre-warm and seed cache from JSON files.
"""

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List
import httpx


async def seed_cache_from_file(
    base_url: str,
    api_key: str,
    file_path: str,
    project_id: str | None = None,
) -> None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"Error reading file '{file_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    items: List[Dict[str, Any]] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "items" in data:
        items = data["items"]
    else:
        print("Invalid JSON format. Expected list of items or {'items': [...]}.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(items)} items from '{file_path}'. Sending warm request to {base_url}/v1/cache/warm...")

    payload = {
        "project_id": project_id,
        "items": items,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url}/v1/cache/warm",
            json=payload,
            headers=headers,
        )

        if response.status_code == 200:
            res_data = response.json()
            print("✅ Cache warming succeeded!")
            print(f"  • Total items:      {res_data.get('total_items')}")
            print(f"  • Exact seeded:     {res_data.get('exact_seeded')}")
            print(f"  • Semantic seeded:  {res_data.get('semantic_seeded')}")
            print(f"  • Elapsed:          {res_data.get('duration_ms', 0):.2f} ms")
            if res_data.get("errors"):
                print(f"  ⚠️ Errors:          {res_data.get('errors')}")
        else:
            print(f"❌ Failed to warm cache [{response.status_code}]: {response.text}", file=sys.stderr)
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="CacheMind Cache Seeder")
    parser.add_argument("file", help="Path to JSON file containing prompt/response pairs")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--key", default="cm_live_development_key_1234567890abcdef", help="CacheMind API Key")
    parser.add_argument("--project", default=None, help="Target project ID (optional)")
    args = parser.parse_args()

    asyncio.run(seed_cache_from_file(args.url, args.key, args.file, args.project))


if __name__ == "__main__":
    main()
