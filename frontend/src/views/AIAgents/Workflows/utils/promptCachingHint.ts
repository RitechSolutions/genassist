/** A builder-time note under the prompt-caching switch, with the tone it should be shown in */
export interface PromptCachingHint {
  text: string;
  tone: "info" | "warning";
}

/** The provider fields the hint consults; a full LLMProvider satisfies it. */
export interface PromptCachingHintProvider {
  llm_model_provider?: string;
  prompt_caching_mode?: string;
}

type CachingMode = "explicit" | "automatic" | "none";

const AUTOMATIC_HINT: PromptCachingHint = {
  text: "Recent models on this provider cache long prompts automatically, so this setting has no effect.",
  tone: "info",
};

const UNSUPPORTED_PROVIDER_HINT: PromptCachingHint = {
  text: "This provider does not support prompt caching, so the setting has no effect.",
  tone: "warning",
};

const UNSUPPORTED_MODEL_HINT: PromptCachingHint = {
  text: "This model does not support prompt caching, so the setting has no effect.",
  tone: "warning",
};

const MIXED_CHAIN_HINT: PromptCachingHint = {
  text: "Not every model in the fallback chain can cache, so nothing is cached.",
  tone: "warning",
};

/**
 * Every provider the chain references excep the primary, 
 * resolved from the COMPLETE provider list, the runtime does not skip a
 * provider an existing chain references merely because it is inactive.
 */
export function fallbackChainProviders<T extends { id: string }>(
  allProviders: T[],
  primaryProviderId: string | undefined,
  chain: { provider_ids: string[] } | null | undefined,
): T[] {
  return (chain?.provider_ids ?? [])
    .filter((id) => id !== primaryProviderId)
    .map((id) => allProviders.find((p) => p.id === id))
    .filter((p): p is T => p !== undefined);
}

const resolveMode = (provider: PromptCachingHintProvider | undefined): CachingMode | undefined => {
  const mode = provider?.prompt_caching_mode;
  if (mode === "explicit" || mode === "automatic" || mode === "none") return mode;
  // The backend serves prompt_caching_mode on every provider read and owns the
  // classification (it is model-conditional for Bedrock)
  return undefined;
};

/**
 * Builder-time note for a node that asked for prompt caching but will not get it.
 */
export function promptCachingHint(
  promptCaching: unknown,
  provider: PromptCachingHintProvider | undefined,
  nodeKind: "agent" | "model",
  type: string | undefined,
  fallbackProviders: Array<PromptCachingHintProvider | undefined> = [],
): PromptCachingHint | null {
  if (promptCaching !== true) return null;

  // Providers the hint cannot classify (none selected, or deleted chain members the
  // runtime would skip anyway) stay out of the verdict.
  const classified = [provider, ...fallbackProviders]
    .map((p) => ({ family: (p?.llm_model_provider ?? "").toLowerCase(), mode: resolveMode(p) }))
    .filter((c): c is { family: string; mode: CachingMode } => c.mode !== undefined);

  if (classified.length > 0) {
    const modes = classified.map((c) => c.mode);
    if (modes.every((mode) => mode === "automatic")) return AUTOMATIC_HINT;
    if (!modes.every((mode) => mode === "explicit")) {
      if (classified.length > 1) return MIXED_CHAIN_HINT;
      return classified[0].family === "bedrock" ? UNSUPPORTED_MODEL_HINT : UNSUPPORTED_PROVIDER_HINT;
    }
  }

  const nonSplitting =
    nodeKind === "model"
      ? ["Chain-of-Thought"]
      : ["ReActAgent", "SimpleToolExecutor"];
  if (type && nonSplitting.includes(type)) {
    return {
      text: `${type} does not split its system prompt, so nothing is cached.`,
      tone: "warning",
    };
  }

  return null;
}
