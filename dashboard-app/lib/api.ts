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

function getSessionToken(): string | null {
  return typeof window !== "undefined" ? localStorage.getItem("cachemind_session_token") : null;
}

async function req<T>(path: string, options?: RequestInit, admin = false): Promise<T> {
  const sessionToken = getSessionToken();
  const key = admin ? getAdminKey() : getApiKey();
  const authHeader = key ? `Bearer ${key}` : (sessionToken ? `Bearer ${sessionToken}` : undefined);

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(authHeader ? { Authorization: authHeader } : {}),
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const errorText = await res.text().catch(() => "");
    let errorDetail = `HTTP error ${res.status}`;
    try {
      const parsed = JSON.parse(errorText);
      if (parsed.detail) {
        errorDetail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
      }
    } catch {}
    throw new Error(errorDetail);
  }
  return res.json();
}

export const api = {
  // 1. Authentication & Workspace Management (/v1/auth/*)
  async signup(payload: {
    email: string;
    password: string;
    full_name?: string;
    workspace_name?: string;
  }): Promise<any> {
    return req<any>("/v1/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async login(payload: { email: string; password: string }): Promise<any> {
    return req<any>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async logout(): Promise<void> {
    await req<any>("/v1/auth/logout", { method: "POST" }).catch(() => {});
  },

  async getMe(): Promise<any> {
    return req<any>("/v1/auth/me");
  },

  async listWorkspaces(): Promise<TenantInfo[]> {
    const data = await req<any>("/v1/auth/workspaces").catch(() => []);
    return Array.isArray(data) ? data : [];
  },

  async selectWorkspace(tenantId: string): Promise<any> {
    return req<any>(`/v1/auth/workspaces/${tenantId}/select`, {
      method: "POST",
    });
  },

  async createWorkspace(name: string): Promise<TenantInfo> {
    return req<TenantInfo>("/v1/auth/workspaces", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  },

  async listProjects(tenantId?: string): Promise<ProjectInfo[]> {
    try {
      const data = await req<any>("/v1/auth/projects");
      if (Array.isArray(data)) return data;
      if (data.projects) return data.projects;
    } catch {
      // Fallback to admin projects endpoint if authorized
      try {
        const query = tenantId ? `?tenant_id=${tenantId}` : "";
        const adminData = await req<any>(`/v1/admin/projects${query}`, undefined, true);
        return Array.isArray(adminData) ? adminData : (adminData.projects || []);
      } catch {
        return [];
      }
    }
    return [];
  },

  async createProject(tenantId: string, name: string): Promise<any> {
    try {
      return await req<any>("/v1/auth/projects", {
        method: "POST",
        body: JSON.stringify({ name, tenant_id: tenantId }),
      });
    } catch {
      return req<ProjectInfo>("/v1/admin/projects", {
        method: "POST",
        body: JSON.stringify({ tenant_id: tenantId, name }),
      }, true);
    }
  },

  async listAPIKeys(projectId?: string): Promise<APIKeyInfo[]> {
    try {
      const query = projectId ? `?project_id=${projectId}` : "";
      const data = await req<any>(`/v1/auth/keys${query}`);
      if (Array.isArray(data)) return data;
      if (data.api_keys) return data.api_keys;
    } catch {
      try {
        const query = projectId ? `?project_id=${projectId}` : "";
        const adminData = await req<any>(`/v1/admin/keys${query}`, undefined, true);
        return Array.isArray(adminData) ? adminData : (adminData.api_keys || []);
      } catch {
        return [];
      }
    }
    return [];
  },

  async createAPIKey(projectId: string, name: string, role = "inference"): Promise<any> {
    try {
      return await req<any>("/v1/auth/keys", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, name, role }),
      });
    } catch {
      return req<APIKeyInfo>("/v1/admin/keys", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, name, role }),
      }, true);
    }
  },

  async revokeAPIKey(keyId: string): Promise<void> {
    try {
      await req<void>(`/v1/auth/keys/${keyId}`, { method: "DELETE" });
    } catch {
      await req<void>(`/v1/admin/keys/${keyId}`, { method: "DELETE" }, true);
    }
  },

  // 2. Dashboard & Analytics
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

  // 3. Multi-Tenant Admin & Fallbacks
  async listTenants(): Promise<TenantInfo[]> {
    try {
      return await this.listWorkspaces();
    } catch {
      const data = await req<any>("/v1/admin/tenants", undefined, true).catch(() => []);
      return Array.isArray(data) ? data : (data.tenants || []);
    }
  },

  async createTenant(name: string, tenantId?: string): Promise<TenantInfo> {
    try {
      return await this.createWorkspace(name);
    } catch {
      return req<TenantInfo>("/v1/admin/tenants", {
        method: "POST",
        body: JSON.stringify({ name, tenant_id: tenantId }),
      }, true);
    }
  },

  // 4. Cache Management & Invalidation
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

  // 5. Billing & Subscriptions
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

  // 6. Interactive Chat / Inference Playground
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
      credentials: "include",
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
