export type Role = "system" | "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface ChatCompletionParams {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  tags?: string[];
  namespace?: string;
  stream?: boolean;
}

export interface CacheTelemetry {
  status: "EXACT_HIT" | "SEMANTIC_HIT" | "CACHE_MISS";
  similarity_score?: number | null;
  tokens_saved: number;
  cost_saved_usd: number;
  latency_ms: number;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason?: string | null;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  cachemind: CacheTelemetry;
}

export interface PurgeParams {
  tenant_id: string;
  project_id?: string;
  model?: string;
  tags?: string[];
}

export interface PurgeResult {
  exact_keys_removed: number;
  semantic_vectors_removed: number;
}

export interface WarmItem {
  prompt: string;
  completion: string;
  model: string;
}

export interface WarmParams {
  tenant_id: string;
  project_id: string;
  items: WarmItem[];
}

export interface WarmResult {
  seeded: number;
}
