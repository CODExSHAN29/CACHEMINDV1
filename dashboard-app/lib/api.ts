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

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
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
    const data = await req<any>("/v1/auth/workspaces");
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
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
    const data = await req<any>(`/v1/auth/projects${query}`);
    if (Array.isArray(data)) return data;
    if (data.projects) return data.projects;
    return [];
  },

  async createProject(tenantId: string, name: string): Promise<any> {
    return req<any>("/v1/auth/projects", {
      method: "POST",
      body: JSON.stringify({ name, tenant_id: tenantId }),
    });
  },

  async listAPIKeys(projectId?: string): Promise<APIKeyInfo[]> {
    const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
    const data = await req<any>(`/v1/auth/keys${query}`);
    if (Array.isArray(data)) return data;
    if (data.api_keys) return data.api_keys;
    return [];
  },

  async createAPIKey(projectId: string, name: string, role = "inference"): Promise<any> {
    return req<any>("/v1/auth/keys", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, name, role }),
    });
  },

  async revokeAPIKey(keyId: string): Promise<void> {
    await req<void>(`/v1/auth/keys/${keyId}`, { method: "DELETE" });
  },

  // 2. Dashboard & Analytics
  async getDashboardSummary(tenantId?: string): Promise<DashboardSummary> {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
    return req<DashboardSummary>(`/v1/dashboard/summary${query}`);
  },

  async getTimeseriesAnalytics(days = 7, tenantId?: string): Promise<any> {
    const params = new URLSearchParams({ days: String(days) });
    if (tenantId) params.set("tenant_id", tenantId);
    return req<any>(`/v1/analytics/timeseries?${params.toString()}`);
  },

  // 3. Cache Management & Invalidation
  async purgeCache(params: {
    tenant_id?: string;
    project_id?: string;
    model?: string;
    namespace?: string;
    tags?: string[];
  }): Promise<PurgeResult> {
    return req<PurgeResult>("/v1/cache/purge", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async inspectCacheKey(keyHash: string): Promise<any> {
    return req<any>(`/v1/cache/inspect/${keyHash}`);
  },

  async deleteCacheKey(keyHash: string): Promise<void> {
    await req<void>(`/v1/cache/keys/${keyHash}`, { method: "DELETE" });
  },

  async warmCache(
    params:
      | {
          tenant_id?: string;
          project_id?: string;
          items: Array<{ prompt: string; completion: string; model: string }>;
        }
      | Array<{ prompt: string; completion: string; model: string }>,
    tenantId?: string,
    projectId?: string
  ): Promise<{ seeded: number; seeded_l1?: number; seeded_l2?: number }> {
    const payload = Array.isArray(params)
      ? { items: params, tenant_id: tenantId, project_id: projectId }
      : params;
    return req<any>("/v1/cache/warm", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // 4. Billing & Subscriptions
  async listPlans(): Promise<BillingPlan[]> {
    const data = await req<any>("/v1/billing/plans");
    if (Array.isArray(data)) return data;
    if (data.plans) return Array.isArray(data.plans) ? data.plans : Object.values(data.plans);
    return [];
  },

  async listSubscriptions(tenantId?: string): Promise<SubscriptionInfo[]> {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
    const data = await req<any>(`/v1/billing/subscriptions${query}`);
    return Array.isArray(data) ? data : (data.subscriptions || []);
  },

  async subscribeTenant(tenantId: string, tier: string): Promise<SubscriptionInfo> {
    return req<SubscriptionInfo>("/v1/billing/subscribe", {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId, tier }),
    });
  },

  // 5. Interactive Chat / Inference Playground (Using session or direct inference)
  async sendPlaygroundInference(
    prompt: string,
    model = "gpt-4o-mini",
    tags?: string[],
    namespace?: string,
    apiKey?: string
  ): Promise<PlaygroundResponse> {
    const startTime = performance.now();
    const headers: Record<string, string> = {};
    if (tags?.length) headers["X-CacheMind-Tags"] = tags.join(",");
    if (namespace) headers["X-CacheMind-Namespace"] = namespace;
    if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;

    const res = await fetch(`${API_BASE}/v1/chat/completions`, {
      method: "POST",
      credentials: "include",
      headers: {
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
