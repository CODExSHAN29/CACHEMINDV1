import {
  DashboardSummary,
  TenantInfo,
  ProjectInfo,
  APIKeyInfo,
  BillingPlan,
  SubscriptionInfo,
  CacheInspection,
  PurgeResult,
  PlaygroundResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEFAULT_DEV_KEY = "cm_live_development_test_key_000000000000000000000000";
const DEFAULT_ADMIN_KEY = "cm_admin_master_secret_key_9999999999999999";

function getApiKey(): string {
  return (typeof window !== "undefined" && localStorage.getItem("cachemind_api_key")) || DEFAULT_DEV_KEY;
}

function getAdminKey(): string {
  return (typeof window !== "undefined" && localStorage.getItem("cachemind_admin_key")) || DEFAULT_ADMIN_KEY;
}

async function req<T>(path: string, options?: RequestInit, admin = false): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${admin ? getAdminKey() : getApiKey()}`,
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`HTTP error ${res.status}`);
  return res.json();
}

export const api = {
  // 1. Dashboard & Analytics
  async getDashboardSummary(tenantId = "tenant_default"): Promise<DashboardSummary> {
    return req<DashboardSummary>(`/v1/dashboard/summary?tenant_id=${tenantId}`).catch(() => ({
      total_requests: 0,
      exact_hits: 0,
      semantic_hits: 0,
      cache_misses: 0,
      cache_hit_ratio: 0,
      tokens_saved: 0,
      cost_saved_usd: 0,
      average_latency_ms: 0,
      cached_average_latency_ms: 0,
      uncached_average_latency_ms: 0,
      latency_reduction_percent: 0,
    }));
  },

  async getTimeseriesAnalytics(days = 7): Promise<any> {
    return req<any>(`/v1/analytics/timeseries?days=${days}`).catch(() => ({ data: [] }));
  },

  // 2. Multi-Tenant Admin & Keys
  async listTenants(): Promise<TenantInfo[]> {
    const data = await req<any>("/v1/admin/tenants", undefined, true);
    return Array.isArray(data) ? data : (data.tenants || []);
  },

  async createTenant(name: string, tenantId?: string): Promise<TenantInfo> {
    return req<TenantInfo>("/v1/admin/tenants", {
      method: "POST",
      body: JSON.stringify({ name, tenant_id: tenantId }),
    }, true);
  },

  async listProjects(tenantId = "tenant_default"): Promise<ProjectInfo[]> {
    const data = await req<any>(`/v1/admin/projects?tenant_id=${tenantId}`, undefined, true);
    return Array.isArray(data) ? data : (data.projects || []);
  },

  async createProject(tenantId: string, name: string): Promise<ProjectInfo> {
    return req<ProjectInfo>("/v1/admin/projects", {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId, name }),
    }, true);
  },

  async listAPIKeys(projectId = "proj_default"): Promise<APIKeyInfo[]> {
    const data = await req<any>(`/v1/admin/keys?project_id=${projectId}`, undefined, true);
    return Array.isArray(data) ? data : (data.api_keys || []);
  },

  async createAPIKey(projectId: string, name: string, role = "inference"): Promise<APIKeyInfo> {
    return req<APIKeyInfo>("/v1/admin/keys", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, name, role }),
    }, true);
  },

  async revokeAPIKey(keyId: string): Promise<void> {
    await req<void>(`/v1/admin/keys/${keyId}`, { method: "DELETE" }, true);
  },

  // 3. Cache Management & Invalidation
  async purgeCache(params: {
    tenant_id: string;
    project_id?: string;
    model?: string;
    tags?: string[];
  }): Promise<PurgeResult> {
    return req<PurgeResult>("/v1/cache/purge", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async inspectCacheKey(keyHash: string): Promise<CacheInspection> {
    return req<CacheInspection>(`/v1/cache/inspect/${keyHash}`);
  },

  async deleteCacheKey(keyHash: string): Promise<void> {
    await req<void>(`/v1/cache/keys/${keyHash}`, { method: "DELETE" });
  },

  async warmCache(items: Array<{ prompt: string; completion: string; model: string }>): Promise<{ seeded: number }> {
    return req<{ seeded: number }>("/v1/cache/warm", {
      method: "POST",
      body: JSON.stringify({
        tenant_id: "tenant_default",
        project_id: "proj_default",
        items,
      }),
    });
  },

  // 4. Billing & Subscriptions
  async listPlans(): Promise<BillingPlan[]> {
    const data = await req<any>("/v1/billing/plans", undefined, true);
    if (Array.isArray(data)) return data;
    if (data.plans) return Array.isArray(data.plans) ? data.plans : Object.values(data.plans);
    return [];
  },

  async listSubscriptions(): Promise<SubscriptionInfo[]> {
    const data = await req<any>("/v1/billing/subscriptions", undefined, true);
    return Array.isArray(data) ? data : (data.subscriptions || []);
  },

  async subscribeTenant(tenantId: string, tier: string): Promise<SubscriptionInfo> {
    return req<SubscriptionInfo>("/v1/billing/subscribe", {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId, tier }),
    }, true);
  },

  // 5. Interactive Chat / Inference Playground
  async sendPlaygroundInference(
    prompt: string,
    model = "gpt-4o-mini",
    tags?: string[],
    namespace?: string
  ): Promise<PlaygroundResponse> {
    const startTime = performance.now();
    const headers: Record<string, string> = {};
    if (tags?.length) headers["X-CacheMind-Tags"] = tags.join(",");
    if (namespace) headers["X-CacheMind-Namespace"] = namespace;

    const res = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getApiKey()}`,
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        temperature: 0.7,
      }),
    });

    const latency_ms = Math.round(performance.now() - startTime);
    if (!res.ok) throw new Error(`Inference failed (${res.status}): ${await res.text()}`);

    const data = await res.json();
    return {
      ...data,
      cache_status: (res.headers.get("x-cachemind-cache") || "CACHE_MISS") as any,
      latency_ms,
      tokens_saved: parseInt(res.headers.get("x-cachemind-tokens-saved") || "0", 10),
      cost_saved_usd: parseFloat(res.headers.get("x-cachemind-cost-saved") || "0"),
      semantic_score: parseFloat(res.headers.get("x-cachemind-similarity") || "0"),
    };
  },
};
