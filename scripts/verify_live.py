#!/usr/bin/env python3
"""
CacheMind External HTTP Runtime Smoke Verification Suite.

Exercises the live gateway over HTTP to verify:
  Phase A: Liveness probe (/health/live)
  Phase B: Readiness probe and component health (/health/ready)
  Phase C: User signup & workspace provisioning (/v1/auth/signup)
  Phase D: Session cookie verification (/v1/auth/me)
  Phase E: API key generation (/v1/auth/keys)
  Phase F: Cold cache miss & hash computation (/v1/chat/completions)
  Phase G: L1 exact cache hit verification (/v1/chat/completions)
  Phase H: Ingress PII masking before provider dispatch
  Phase I: API key revocation and inference rejection
  Phase J: Session logout and invalidation
  Phase K: Verification summary report
"""

import asyncio
import os
import sys
import uuid
import httpx


async def run_smoke_verification() -> None:
    base_url = os.getenv("CACHEMIND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout = float(os.getenv("SMOKE_TIMEOUT_SECONDS", "30.0"))
    smoke_id = uuid.uuid4().hex[:8]

    test_email = f"runtime-smoke-{smoke_id}@cachemind.local"
    test_password = "RuntimeSmokePassword123!"

    print("=" * 70)
    print(f" CacheMind Runtime Smoke Verification | Target: {base_url}")
    print("=" * 70)

    # Use httpx.AsyncClient with cookie persistence for session workflows
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, follow_redirects=True) as client:
        # -------------------------------------------------------------
        # Phase A: Liveness
        # -------------------------------------------------------------
        res = await client.get("/health/live")
        if res.status_code != 200:
            sys.exit(f"Phase A FAILED: /health/live returned HTTP {res.status_code}: {res.text}")
        live_data = res.json()
        if live_data.get("probe") != "liveness":
            sys.exit(f"Phase A FAILED: expected probe=='liveness', got: {live_data}")
        print("[PASS] Phase A: Liveness probe healthy (/health/live)")

        # -------------------------------------------------------------
        # Phase B: Readiness
        # -------------------------------------------------------------
        res = await client.get("/health/ready")
        if res.status_code != 200:
            sys.exit(f"Phase B FAILED: /health/ready returned HTTP {res.status_code}: {res.text}")
        ready_data = res.json()
        if ready_data.get("status") != "ready":
            sys.exit(f"Phase B FAILED: expected status=='ready', got: {ready_data}")

        components = ready_data.get("components", {})
        for comp_name in ("database", "cache_backend", "semantic_backend", "embedding_engine"):
            comp_status = components.get(comp_name, {}).get("status")
            if comp_status != "healthy":
                sys.exit(f"Phase B FAILED: component '{comp_name}' is not healthy (status: {comp_status})")
        print("[PASS] Phase B: Readiness probe healthy with core components operational (/health/ready)")

        # -------------------------------------------------------------
        # Phase C: User Signup
        # -------------------------------------------------------------
        signup_payload = {
            "email": test_email,
            "password": test_password,
            "full_name": "Runtime Smoke Tester",
            "workspace_name": f"Smoke Workspace {smoke_id}",
        }
        res = await client.post("/v1/auth/signup", json=signup_payload)
        if res.status_code != 201:
            sys.exit(f"Phase C FAILED: /v1/auth/signup returned HTTP {res.status_code}: {res.text}")
        signup_data = res.json()

        active_project = signup_data.get("active_project")
        if not active_project or not active_project.get("id"):
            sys.exit(f"Phase C FAILED: missing active_project in signup response: {signup_data}")
        project_id = active_project["id"]
        print(f"[PASS] Phase C: User registered and default workspace/project provisioned (project_id: {project_id})")

        # -------------------------------------------------------------
        # Phase D: Session Verification
        # -------------------------------------------------------------
        res = await client.get("/v1/auth/me")
        if res.status_code != 200:
            sys.exit(f"Phase D FAILED: /v1/auth/me returned HTTP {res.status_code}: {res.text}")
        me_data = res.json()
        user_info = me_data.get("user", {})
        if user_info.get("email") != test_email:
            sys.exit(f"Phase D FAILED: email mismatch in /v1/auth/me: expected {test_email}, got {user_info.get('email')}")
        print("[PASS] Phase D: Session verified via HttpOnly cookie (/v1/auth/me)")

        # -------------------------------------------------------------
        # Phase E: Create Project API Key
        # -------------------------------------------------------------
        key_payload = {
            "project_id": project_id,
            "name": f"Runtime Smoke Key {smoke_id}",
            "role": "inference",
        }
        res = await client.post("/v1/auth/keys", json=key_payload)
        if res.status_code != 201:
            sys.exit(f"Phase E FAILED: /v1/auth/keys returned HTTP {res.status_code}: {res.text}")
        key_data = res.json()

        raw_key = key_data.get("raw_key")
        key_id = key_data.get("id")
        if not raw_key or not key_id:
            sys.exit("Phase E FAILED: /v1/auth/keys response missing raw_key or id")
        key_prefix = key_data.get("key_prefix", "cm_...")
        print(f"[PASS] Phase E: Project API key generated (key_prefix: {key_prefix}, key_id: {key_id})")

        # Bearer client for inference requests
        chat_headers = {
            "Authorization": f"Bearer {raw_key}",
            "Content-Type": "application/json",
        }

        # -------------------------------------------------------------
        # Phase F: Cold Cache Miss
        # -------------------------------------------------------------
        unique_prompt = f"CacheMind runtime smoke request {smoke_id}"
        chat_payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": unique_prompt}],
            "temperature": 0.0,
        }
        res_cold = await client.post("/v1/chat/completions", json=chat_payload, headers=chat_headers)
        if res_cold.status_code != 200:
            sys.exit(f"Phase F FAILED: /v1/chat/completions returned HTTP {res_cold.status_code}: {res_cold.text}")

        cold_status = res_cold.headers.get("X-CacheMind-Status")
        cold_hash = res_cold.headers.get("X-CacheMind-Exact-Hash")
        if cold_status != "MISS":
            sys.exit(f"Phase F FAILED: expected X-CacheMind-Status=='MISS', got: '{cold_status}'")
        if not cold_hash:
            sys.exit("Phase F FAILED: missing X-CacheMind-Exact-Hash header in response")

        cold_body = res_cold.json()
        cold_content = cold_body["choices"][0]["message"]["content"]
        print(f"[PASS] Phase F: Cold cache miss verified (status: MISS, hash: {cold_hash})")

        # -------------------------------------------------------------
        # Phase G: L1 Exact Cache Hit
        # -------------------------------------------------------------
        res_exact = await client.post("/v1/chat/completions", json=chat_payload, headers=chat_headers)
        if res_exact.status_code != 200:
            sys.exit(f"Phase G FAILED: /v1/chat/completions returned HTTP {res_exact.status_code}: {res_exact.text}")

        exact_status = res_exact.headers.get("X-CacheMind-Status")
        exact_hash = res_exact.headers.get("X-CacheMind-Exact-Hash")
        if exact_status != "EXACT_HIT":
            sys.exit(f"Phase G FAILED: expected X-CacheMind-Status=='EXACT_HIT', got: '{exact_status}'")
        if exact_hash != cold_hash:
            sys.exit(f"Phase G FAILED: exact hash mismatch: '{exact_hash}' != '{cold_hash}'")

        exact_body = res_exact.json()
        exact_content = exact_body["choices"][0]["message"]["content"]
        if exact_content != cold_content:
            sys.exit("Phase G FAILED: response content mismatch between cold miss and exact hit")
        print("[PASS] Phase G: L1 exact cache hit verified (status: EXACT_HIT, hash preserved)")

        # -------------------------------------------------------------
        # Phase H: Ingress PII Sanitization
        # -------------------------------------------------------------
        synthetic_email = f"smoke.user.{smoke_id}@example-corp.com"
        synthetic_secret = f"cm_sec_smoke_test_secret_key_{smoke_id}00000000"
        pii_prompt = f"Contact {synthetic_email} with access key {synthetic_secret} for smoke run {smoke_id}."

        pii_payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": pii_prompt}],
            "temperature": 0.0,
        }
        res_pii = await client.post("/v1/chat/completions", json=pii_payload, headers=chat_headers)
        if res_pii.status_code != 200:
            sys.exit(f"Phase H FAILED: /v1/chat/completions returned HTTP {res_pii.status_code}: {res_pii.text}")

        pii_content = res_pii.json()["choices"][0]["message"]["content"]
        if synthetic_email in pii_content:
            sys.exit("Phase H FAILED: raw synthetic email leaked in provider response")
        if synthetic_secret in pii_content:
            sys.exit("Phase H FAILED: raw synthetic secret leaked in provider response")
        if "[REDACTED_EMAIL]" not in pii_content:
            sys.exit("Phase H FAILED: missing [REDACTED_EMAIL] token in response")
        if "[REDACTED_SECRET]" not in pii_content:
            sys.exit("Phase H FAILED: missing [REDACTED_SECRET] token in response")
        print("[PASS] Phase H: Ingress PII sanitization verified before provider dispatch ([REDACTED_EMAIL], [REDACTED_SECRET])")

        # -------------------------------------------------------------
        # Phase I: API Key Revocation
        # -------------------------------------------------------------
        res_revoke = await client.delete(f"/v1/auth/keys/{key_id}")
        if res_revoke.status_code != 200:
            sys.exit(f"Phase I FAILED: /v1/auth/keys/{key_id} returned HTTP {res_revoke.status_code}: {res_revoke.text}")

        # Retry inference with revoked key -> Must return 401 Unauthorized
        res_revoked_chat = await client.post("/v1/chat/completions", json=chat_payload, headers=chat_headers)
        if res_revoked_chat.status_code != 401:
            sys.exit(f"Phase I FAILED: expected HTTP 401 for revoked key, got: {res_revoked_chat.status_code}")
        print(f"[PASS] Phase I: API key revoked (key_id: {key_id}) and rejected on inference (HTTP 401)")

        # -------------------------------------------------------------
        # Phase J: Session Logout & Invalidation
        # -------------------------------------------------------------
        res_logout = await client.post("/v1/auth/logout")
        if res_logout.status_code != 200:
            sys.exit(f"Phase J FAILED: /v1/auth/logout returned HTTP {res_logout.status_code}: {res_logout.text}")

        res_me_logged_out = await client.get("/v1/auth/me")
        if res_me_logged_out.status_code != 401:
            sys.exit(f"Phase J FAILED: expected HTTP 401 after logout, got: {res_me_logged_out.status_code}")
        print("[PASS] Phase J: Session logged out and invalidated (HTTP 401 on /v1/auth/me)")

    print("=" * 70)
    print("CacheMind runtime smoke verification PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_smoke_verification())
