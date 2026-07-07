export interface RetryPolicy {
  retry_count: number;
  backoff_seconds: number;
  /** Default max seconds to wait for a provider's reply before failing over (0 = no limit). */
  timeout_seconds?: number;
  /** Per-provider response timeout overrides, keyed by provider id (seconds). */
  provider_timeouts?: Record<string, number>;
}

export interface FallbackChain {
  id: string;
  name: string;
  description?: string | null;
  /** Ordered list of LLM provider ids; index 0 is highest priority. */
  provider_ids: string[];
  retry_policy?: RetryPolicy | null;
  is_active: number;
  created_at: string;
  updated_at: string;
}

export interface FallbackChainMinimal {
  id: string;
  name: string;
  is_active: number;
}
