export interface DashboardSummary {
  total_requests: number;
  exact_hits: number;
  semantic_hits: number;
  cache_misses: number;
  cache_hit_ratio: number;
  tokens_saved: number;
  cost_saved_usd: number;
  average_latency_ms: number;
  cached_average_latency_ms: number;
  uncached_average_latency_ms: number;
  latency_reduction_percent: number;
}

export interface TenantInfo {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectInfo {
  id: string;
  tenant_id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface APIKeyInfo {
  id: string;
  project_id: string;
  key_prefix: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
  raw_key?: string;
}

export interface BillingPlan {
  tier: "starter" | "pro" | "enterprise" | "custom";
  name: string;
  monthly_price_usd: number;
  daily_request_limit: number;
  daily_token_limit: number;
  cache_ttl_days: number;
  overage_per_1k_requests_usd: number;
  overage_per_1k_tokens_usd: number;
}

export interface SubscriptionInfo {
  tenant_id: string;
  tier: string;
  status: string;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
  monthly_price_usd: number;
  daily_request_limit: number;
  daily_token_limit: number;
}

export interface CacheInspection {
  found: boolean;
  key_hash?: string;
  model?: string;
  prompt_preview?: string;
  response_preview?: string;
  tokens_saved?: number;
  access_count?: number;
  ttl_remaining_seconds?: number;
  created_at?: string;
}

export interface PurgeResult {
  exact_keys_removed: number;
  semantic_vectors_removed: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface PlaygroundResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  cache_status?: "EXACT_HIT" | "SEMANTIC_HIT" | "CACHE_MISS";
  latency_ms?: number;
  semantic_score?: number;
  tokens_saved?: number;
  cost_saved_usd?: number;
}
