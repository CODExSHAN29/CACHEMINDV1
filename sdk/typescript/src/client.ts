import {
  ChatCompletionParams,
  ChatCompletionResponse,
  PurgeParams,
  PurgeResult,
  WarmParams,
  WarmResult,
  CacheTelemetry,
} from "./types";

export interface CacheMindClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export class ChatCompletions {
  constructor(private client: CacheMindClient) {}

  async create(params: ChatCompletionParams): Promise<ChatCompletionResponse> {
    const startTime = Date.now();
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.client.apiKey}`,
      "Content-Type": "application/json",
      "User-Agent": "CacheMind-TypeScript-SDK/0.1.0",
    };

    if (params.tags && params.tags.length > 0) {
      headers["X-CacheMind-Tags"] = params.tags.join(",");
    }
    if (params.namespace) {
      headers["X-CacheMind-Namespace"] = params.namespace;
    }

    const payload = {
      model: params.model,
      messages: params.messages,
      temperature: params.temperature ?? 0.7,
      max_tokens: params.max_tokens,
      stream: params.stream ?? false,
    };

    const res = await fetch(`${this.client.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    const elapsedMs = Date.now() - startTime;

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`CacheMind Gateway Error (${res.status}): ${errBody}`);
    }

    const data = await res.json();

    const cacheStatus = (res.headers.get("x-cachemind-cache") || "CACHE_MISS") as any;
    const tokensSaved = parseInt(res.headers.get("x-cachemind-tokens-saved") || "0", 10);
    const costSaved = parseFloat(res.headers.get("x-cachemind-cost-saved") || "0.0");
    const similarityHeader = res.headers.get("x-cachemind-similarity");
    const similarityScore = similarityHeader ? parseFloat(similarityHeader) : null;

    const cachemind: CacheTelemetry = {
      status: cacheStatus,
      similarity_score: similarityScore,
      tokens_saved: tokensSaved,
      cost_saved_usd: costSaved,
      latency_ms: elapsedMs,
    };

    return {
      ...data,
      cachemind,
    };
  }
}

export class CacheManagement {
  constructor(private client: CacheMindClient) {}

  async purge(params: PurgeParams): Promise<PurgeResult> {
    const res = await fetch(`${this.client.baseUrl}/v1/cache/purge`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.client.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      throw new Error(`Purge failed (${res.status}): ${await res.text()}`);
    }
    return await res.json();
  }

  async warm(params: WarmParams): Promise<WarmResult> {
    const res = await fetch(`${this.client.baseUrl}/v1/cache/warm`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.client.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      throw new Error(`Warm failed (${res.status}): ${await res.text()}`);
    }
    return await res.json();
  }
}

export class CacheMindClient {
  public apiKey: string;
  public baseUrl: string;
  public timeoutMs: number;

  public chat: { completions: ChatCompletions };
  public cache: CacheManagement;

  constructor(options: CacheMindClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || "http://localhost:8000").replace(/\/$/, "");
    this.timeoutMs = options.timeoutMs || 30000;

    this.chat = {
      completions: new ChatCompletions(this),
    };
    this.cache = new CacheManagement(this);
  }
}
