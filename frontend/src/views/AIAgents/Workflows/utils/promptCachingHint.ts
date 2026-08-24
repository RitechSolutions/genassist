/** A builder-time note under the prompt-caching switch, with the tone it should be shown in */
export interface PromptCachingHint {
  text: string;
  tone: "info" | "warning";
}

// These cache long prompts server-side with no marker, so the toggle is moot rather than a mistake.
const AUTOMATIC_CACHING_FAMILIES = ["openai", "azure_openai", "google_genai", "google_vertexai"];

/**
 * Builder-time note for a node that asked for prompt caching but will not get it
 */
export function promptCachingHint(
  promptCaching: unknown,
  provider: { llm_model_provider?: string } | undefined,
  nodeKind: "agent" | "model",
  type: string | undefined,
): PromptCachingHint | null {
  if (promptCaching !== true) return null;

  const family = (provider?.llm_model_provider ?? "").toLowerCase();
  if (family && family !== "anthropic" && family !== "bedrock") {
    if (AUTOMATIC_CACHING_FAMILIES.includes(family)) {
      return {
        text: "Recent models on this provider cache long prompts automatically, so this setting has no effect.",
        tone: "info",
      };
    }
    return {
      text: "This provider does not support prompt caching, so the setting has no effect.",
      tone: "warning",
    };
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
