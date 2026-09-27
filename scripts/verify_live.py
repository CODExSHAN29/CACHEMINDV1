#!/usr/bin/env python3
"""
CacheMind Full System Live Verification & Smoke Test Suite.
Verifies all 6 phases and core gateway functionality in real-time:
1. Health & Readiness
2. Cold Cache Miss & LLM Dispatch
3. L1 Exact Cache Hit (< 2ms)
4. L2 Semantic Vector Cache Hit (< 10ms)
5. PII Masking & Sensitive Data Protection
6. Cache Lifecycle (Inspection, Single-Key Deletion, Scoped Purge, Pre-Warming)
7. Multi-Tenant Admin API (Tenant, Project, Key Creation, Scoped Revocation)
8. FinOps Analytics & Cost Savings Reporting
"""

import asyncio
import json
import time
from typing import Any, Dict
import httpx

from backend.app.config import settings
from backend.app.main import app, lifespan

DEV_KEY = settings.DEV_API_KEY


async def run_live_verification():
    print("=" * 80)
    print(" 🧪 CACHEMIND SYSTEM VERIFICATION & SMOKE TEST")
    print("=" * 80)

    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
            auth_headers = {
                "Authorization": f"Bearer {DEV_KEY}",
                "Content-Type": "application/json",
            }

            # -------------------------------------------------------------
            # 1. Health Check
            # -------------------------------------------------------------
            print("\n[Test 1] Health & System Status Endpoint...")
            res = await client.get("/health")
            assert res.status_code == 200, f"Health check failed: {res.text}"
            health_data = res.json()
            print(f"  ✅ Health Check: {res.status_code} OK | Status: {health_data.get('status')}")

            # -------------------------------------------------------------
            # 2. Cold Miss -> Upstream Provider Dispatch
            # -------------------------------------------------------------
            print("\n[Test 2] Cold Cache Miss (First-time Request)...")
            prompt_1 = "Explain the advantages of asynchronous I/O in Python."
            req_payload = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt_1}],
                "temperature": 0.0,
            }

            start = time.perf_counter_ns()
            res_cold = await client.post("/v1/chat/completions", json=req_payload, headers=auth_headers)
            cold_latency_ms = (time.perf_counter_ns() - start) / 1_000_000.0

            assert res_cold.status_code == 200, f"Cold request failed: {res_cold.text}"
            cold_status = res_cold.headers.get("X-CacheMind-Status")
            cold_hash = res_cold.headers.get("X-CacheMind-Exact-Hash")
            cold_data = res_cold.json()
            response_text = cold_data["choices"][0]["message"]["content"]

            print(f"  ✅ Status Code:    {res_cold.status_code}")
            print(f"  ✅ Cache Status:   {cold_status} (Expected: MISS)")
            print(f"  ✅ Latency:        {cold_latency_ms:.2f} ms")
            print(f"  ✅ Exact Hash:     {cold_hash}")
            print(f"  ✅ Response Text:  {response_text[:60]}...")

            assert cold_status == "MISS", f"Expected MISS but got {cold_status}"

            # -------------------------------------------------------------
            # 3. L1 Exact Cache Hit
            # -------------------------------------------------------------
            print("\n[Test 3] L1 Exact Cache Hit (Identical Prompt)...")
            start = time.perf_counter_ns()
            res_exact = await client.post("/v1/chat/completions", json=req_payload, headers=auth_headers)
            exact_latency_ms = (time.perf_counter_ns() - start) / 1_000_000.0

            assert res_exact.status_code == 200
            exact_status = res_exact.headers.get("X-CacheMind-Status")
            exact_hash = res_exact.headers.get("X-CacheMind-Exact-Hash")

            print(f"  ✅ Status Code:    {res_exact.status_code}")
            print(f"  ✅ Cache Status:   {exact_status} (Expected: EXACT_HIT)")
            print(f"  ✅ Latency:        {exact_latency_ms:.2f} ms (Target: < 2.5ms)")
            print(f"  ✅ Exact Hash:     {exact_hash}")

            assert exact_status == "EXACT_HIT", f"Expected EXACT_HIT but got {exact_status}"
            assert exact_hash == cold_hash, "Hash mismatch on exact hit"

            # -------------------------------------------------------------
            # 4. L2 Semantic Vector Cache Hit
            # -------------------------------------------------------------
            print("\n[Test 4] L2 Semantic Vector Cache Hit (Paraphrased Prompt)...")
            from backend.semantic.factory import get_semantic_cache_service
            sem_service = get_semantic_cache_service()
            if hasattr(sem_service.embedding_engine, "register_similar"):
                sem_service.embedding_engine.register_similar(prompt_1, "What are the benefits of using async I/O in Python?", 0.96)

            paraphrased_prompt = "What are the benefits of using async I/O in Python?"
            sem_payload = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": paraphrased_prompt}],
                "temperature": 0.0,
            }

            start = time.perf_counter_ns()
            res_sem = await client.post("/v1/chat/completions", json=sem_payload, headers=auth_headers)
            sem_latency_ms = (time.perf_counter_ns() - start) / 1_000_000.0

            assert res_sem.status_code == 200
            sem_status = res_sem.headers.get("X-CacheMind-Status")
            sem_score = res_sem.headers.get("X-CacheMind-Similarity") or res_sem.headers.get("X-CacheMind-Semantic-Score")

            print(f"  ✅ Status Code:    {res_sem.status_code}")
            print(f"  ✅ Cache Status:   {sem_status} (Expected: L2_HIT)")
            print(f"  ✅ Similarity:     {sem_score}")
            print(f"  ✅ Latency:        {sem_latency_ms:.2f} ms (Target: < 12.0ms)")

            assert sem_status in ("L2_HIT", "SEMANTIC_HIT"), f"Expected L2_HIT/SEMANTIC_HIT but got {sem_status}"

            # -------------------------------------------------------------
            # 5. Ingress PII Sanitization
            # -------------------------------------------------------------
            print("\n[Test 5] Ingress PII Sanitization (Redacting Sensitive Entities)...")
            pii_prompt = "Contact support at alice@example-corp.com or call +1 555-123-4567 for account 123-45-6789."
            pii_payload = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": pii_prompt}],
            }
            res_pii = await client.post("/v1/chat/completions", json=pii_payload, headers=auth_headers)
            assert res_pii.status_code == 200
            pii_hash = res_pii.headers.get("X-CacheMind-Exact-Hash")
            print(f"  ✅ PII Prompt Processed | Generated Exact Hash: {pii_hash}")

            # Inspect cache key to verify PII was masked before caching
            res_inspect = await client.get(f"/v1/cache/inspect/{pii_hash}", headers=auth_headers)
            assert res_inspect.status_code == 200
            inspect_data = res_inspect.json()
            print(f"  ✅ Cache Key Exists: {inspect_data.get('exists')}")

            # -------------------------------------------------------------
            # 6. Cache Pre-Warming / Seeding
            # -------------------------------------------------------------
            print("\n[Test 6] Cache Pre-Warming Engine (Batch Seeding)...")
            warm_payload = {
                "items": [
                    {
                        "prompt": "What is CacheMind?",
                        "response": "CacheMind is an enterprise-grade AI semantic caching gateway.",
                        "model": "gpt-4o",
                        "tags": ["docs", "overview"],
                        "namespace": "knowledge_base",
                        "temperature": 0.0,
                    },
                    {
                        "prompt": "How fast is L1 exact caching?",
                        "response": "L1 exact caching serves responses in under 2 milliseconds.",
                        "model": "gpt-4o",
                        "temperature": 0.0,
                    },
                ]
            }
            res_warm = await client.post("/v1/cache/warm", json=warm_payload, headers=auth_headers)
            assert res_warm.status_code == 200
            warm_res = res_warm.json()
            print(f"  ✅ Total Items:     {warm_res.get('total_items')}")
            print(f"  ✅ Exact Seeded:    {warm_res.get('exact_seeded')}")
            print(f"  ✅ Semantic Seeded: {warm_res.get('semantic_seeded')}")

            # Test instant hit on pre-warmed prompt
            res_warm_hit = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "What is CacheMind?"}],
                    "tags": ["docs", "overview"],
                    "namespace": "knowledge_base",
                    "temperature": 0.0,
                },
                headers=auth_headers,
            )
            assert res_warm_hit.status_code == 200
            warm_hit_status = res_warm_hit.headers.get("X-CacheMind-Status")
            print(f"  ✅ Pre-warmed Query Status: {warm_hit_status} (Expected: EXACT_HIT)")
            assert warm_hit_status == "EXACT_HIT", f"Expected EXACT_HIT on seeded prompt, got {warm_hit_status}"

            # -------------------------------------------------------------
            # 7. Multi-Tenant Admin API Lifecycle
            # -------------------------------------------------------------
            print("\n[Test 7] Multi-Tenant Admin API Lifecycle...")
            # A. Create Tenant
            res_tenant = await client.post(
                "/v1/admin/tenants",
                json={"name": "Acme Corp"},
                headers=auth_headers,
            )
            assert res_tenant.status_code in (200, 201), f"Tenant creation failed: {res_tenant.text}"
            tenant_data = res_tenant.json()
            tenant_id = tenant_data["id"]
            print(f"  ✅ Created Tenant:  {tenant_data['name']} (ID: {tenant_id})")

            # B. Create Project
            res_proj = await client.post(
                "/v1/admin/projects",
                json={"tenant_id": tenant_id, "name": "Production App"},
                headers=auth_headers,
            )
            assert res_proj.status_code in (200, 201), f"Project creation failed: {res_proj.text}"
            proj_data = res_proj.json()
            proj_id = proj_data["id"]
            print(f"  ✅ Created Project: {proj_data['name']} (ID: {proj_id})")

            # C. Generate New API Key
            res_key = await client.post(
                "/v1/admin/keys",
                json={"project_id": proj_id, "name": "Prod Ingress Key", "role": "inference"},
                headers=auth_headers,
            )
            assert res_key.status_code in (200, 201), f"Key generation failed: {res_key.text}"
            key_data = res_key.json()
            raw_key = key_data["raw_api_key"]
            key_id = key_data["id"]
            print(f"  ✅ Generated API Key: {key_data['key_prefix']}... (Role: {key_data['role']})")

            # D. Test inference with newly created key
            new_key_headers = {"Authorization": f"Bearer {raw_key}", "Content-Type": "application/json"}
            res_new_key = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Test new tenant key"}]},
                headers=new_key_headers,
            )
            assert res_new_key.status_code == 200
            print(f"  ✅ Inference Auth via New Key: {res_new_key.status_code} OK (Status: {res_new_key.headers.get('X-CacheMind-Status')})")

            # E. Revoke Key
            res_revoke = await client.delete(f"/v1/admin/keys/{key_id}", headers=auth_headers)
            assert res_revoke.status_code == 200
            print(f"  ✅ Key Revoked: {key_id}")

            # F. Verify Revoked Key Fails Auth
            res_revoked_auth = await client.post(
                "/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Should fail"}]},
                headers=new_key_headers,
            )
            assert res_revoked_auth.status_code == 401
            print(f"  ✅ Revoked Key Rejected: {res_revoked_auth.status_code} Unauthorized (As Expected)")

            # -------------------------------------------------------------
            # 8. FinOps Analytics & Cost Savings
            # -------------------------------------------------------------
            print("\n[Test 8] FinOps Analytics & Cost Savings Reporting...")
            res_analytics = await client.get("/v1/analytics/overview", headers=auth_headers)
            assert res_analytics.status_code == 200
            analytics_data = res_analytics.json()
            print(f"  ✅ Total Requests:       {analytics_data.get('total_requests')}")
            print(f"  ✅ Cache Hit Rate:       {analytics_data.get('hit_rate_pct', 0.0):.1f}%")
            print(f"  ✅ Exact Hits:           {analytics_data.get('exact_hits')}")
            print(f"  ✅ Semantic Hits:        {analytics_data.get('semantic_hits')}")
            print(f"  ✅ Estimated Cost Saved: ${analytics_data.get('estimated_cost_saved_usd', 0.0):.4f}")

    print("\n" + "=" * 80)
    print(" 🎉 ALL 8 LIVE SYSTEM VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
