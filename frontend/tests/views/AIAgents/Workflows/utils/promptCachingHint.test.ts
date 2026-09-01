import { describe, expect, it } from "vitest";
import { fallbackChainProviders, promptCachingHint } from "@/views/AIAgents/Workflows/utils/promptCachingHint";

const anthropic = { llm_model_provider: "anthropic" };
const openai = { llm_model_provider: "OpenAI" };
const cohere = { llm_model_provider: "cohere" };
const automaticFamilies = ["OpenAI", "azure_openai", "google_genai", "google_vertexai"];

describe("promptCachingHint", () => {
  it("stays silent while the toggle is off", () => {
    expect(promptCachingHint(false, openai, "agent", "ReActAgent")).toBeNull();
    expect(promptCachingHint(undefined, openai, "agent", "ReActAgent")).toBeNull();
  });

  it("treats truthy non-boolean values as off, like the backend does", () => {
    expect(promptCachingHint("true", openai, "model", "Base")).toBeNull();
    expect(promptCachingHint(1, openai, "model", "Base")).toBeNull();
  });

  it("warns about a provider that reports no caching support", () => {
    const served = { llm_model_provider: "cohere", prompt_caching_mode: "none" as const };
    expect(promptCachingHint(true, served, "model", "Base")).toEqual({
      text: "This provider does not support prompt caching, so the setting has no effect.",
      tone: "warning",
    });
  });

  it("tells a provider that caches on its own the setting is moot, never that caching is unavailable", () => {
    for (const family of automaticFamilies) {
      const served = { llm_model_provider: family, prompt_caching_mode: "automatic" as const };
      const hint = promptCachingHint(true, served, "model", "Base");
      expect(hint?.tone).toBe("info");
      expect(hint?.text).toMatch(/cache long prompts automatically/);
      expect(hint?.text).not.toMatch(/does not support|cannot cache|no caching/i);
    }
  });

  it("passes served explicit providers through", () => {
    const anthropicExplicit = { llm_model_provider: "anthropic", prompt_caching_mode: "explicit" as const };
    const bedrockExplicit = { llm_model_provider: "bedrock", prompt_caching_mode: "explicit" as const };
    expect(promptCachingHint(true, anthropicExplicit, "model", "Base")).toBeNull();
    expect(promptCachingHint(true, bedrockExplicit, "model", "Base")).toBeNull();
  });

  it("says nothing when no provider is selected yet", () => {
    expect(promptCachingHint(true, undefined, "model", "Base")).toBeNull();
    expect(promptCachingHint(true, {}, "model", "Base")).toBeNull();
  });

  it("warns about agent types that never split the prompt", () => {
    expect(promptCachingHint(true, anthropic, "agent", "ReActAgent")).toEqual({
      text: "ReActAgent does not split its system prompt, so nothing is cached.",
      tone: "warning",
    });
    expect(promptCachingHint(true, anthropic, "agent", "SimpleToolExecutor")?.text).toMatch(/does not split/);
    expect(promptCachingHint(true, anthropic, "agent", "ToolSelector")).toBeNull();
    expect(promptCachingHint(true, anthropic, "agent", "ReActAgentLC")).toBeNull();
  });

  it("warns about Chain-of-Thought on the model node only", () => {
    expect(promptCachingHint(true, anthropic, "model", "Chain-of-Thought")?.text).toMatch(/does not split/);
    expect(promptCachingHint(true, anthropic, "agent", "Chain-of-Thought")).toBeNull();
  });

  it("reports the provider first when both apply", () => {
    const noneCohere = { llm_model_provider: "cohere", prompt_caching_mode: "none" as const };
    const autoOpenai = { llm_model_provider: "OpenAI", prompt_caching_mode: "automatic" as const };
    expect(promptCachingHint(true, noneCohere, "agent", "ReActAgent")?.text).toMatch(/does not support prompt caching/);
    expect(promptCachingHint(true, autoOpenai, "agent", "ReActAgent")?.tone).toBe("info");
  });

  describe("backend-served prompt_caching_mode", () => {
    it("warns about the model, not the provider, on a non-cacheable Bedrock model", () => {
      const provider = { llm_model_provider: "bedrock", prompt_caching_mode: "none" as const };
      expect(promptCachingHint(true, provider, "model", "Base")).toEqual({
        text: "This model does not support prompt caching, so the setting has no effect.",
        tone: "warning",
      });
    });

    it("warns about the provider when a non-Bedrock family reports none", () => {
      const provider = { llm_model_provider: "cohere", prompt_caching_mode: "none" as const };
      expect(promptCachingHint(true, provider, "model", "Base")?.text).toMatch(/provider does not support/);
    });

    it("trusts the served mode for any family", () => {
      const provider = { llm_model_provider: "cohere", prompt_caching_mode: "automatic" as const };
      expect(promptCachingHint(true, provider, "model", "Base")?.tone).toBe("info");
    });

    it("an explicit mode still runs the agent-type check", () => {
      const provider = { llm_model_provider: "bedrock", prompt_caching_mode: "explicit" as const };
      expect(promptCachingHint(true, provider, "agent", "ToolSelector")).toBeNull();
      expect(promptCachingHint(true, provider, "agent", "ReActAgent")?.text).toMatch(/does not split/);
    });

    it("stays silent when the field is absent — no client-side family fallback", () => {
      expect(promptCachingHint(true, { llm_model_provider: "bedrock" }, "model", "Base")).toBeNull();
      expect(promptCachingHint(true, cohere, "model", "Base")).toBeNull();
      expect(
        promptCachingHint(true, { llm_model_provider: "bedrock", prompt_caching_mode: "none" }, "model", "Base")
      ).toEqual({
        text: "This model does not support prompt caching, so the setting has no effect.",
        tone: "warning",
      });
    });
  });

  describe("fallback chains", () => {
    const explicit = { llm_model_provider: "anthropic", prompt_caching_mode: "explicit" as const };
    const bedrockNone = { llm_model_provider: "bedrock", prompt_caching_mode: "none" as const };
    const automatic = { llm_model_provider: "OpenAI", prompt_caching_mode: "automatic" as const };
    const none = { llm_model_provider: "cohere", prompt_caching_mode: "none" as const };

    it("warns when a capable primary carries an unsupported fallback", () => {
      expect(promptCachingHint(true, explicit, "model", "Base", [none])).toEqual({
        text: "Not every model in the fallback chain can cache, so nothing is cached.",
        tone: "warning",
      });
    });

    it("names the chain, not the model, when the primary is the unsupported one", () => {
      const hint = promptCachingHint(true, bedrockNone, "model", "Base", [explicit]);
      expect(hint?.text).toMatch(/fallback chain/);
      expect(hint?.text).not.toMatch(/This model/);
    });

    it("an all-capable chain stays silent and still runs the agent-type check", () => {
      expect(promptCachingHint(true, explicit, "agent", "ToolSelector", [explicit])).toBeNull();
      expect(promptCachingHint(true, explicit, "agent", "ReActAgent", [explicit])?.text).toMatch(/does not split/);
    });

    it("an all-automatic chain gets the informational hint, never a warning", () => {
      expect(promptCachingHint(true, automatic, "model", "Base", [openai])?.tone).toBe("info");
    });

    it("mixed automatic and unsupported members warn about the chain", () => {
      expect(promptCachingHint(true, automatic, "model", "Base", [none])?.text).toMatch(/fallback chain/);
    });

    it("unclassifiable chain members are ignored, like the runtime skipping unbuildable providers", () => {
      expect(promptCachingHint(true, explicit, "model", "Base", [undefined, {}, cohere])).toBeNull();
    });
  });

  describe("fallbackChainProviders", () => {
    const primary = { id: "p1", llm_model_provider: "anthropic", prompt_caching_mode: "explicit" as const, is_active: 1 };
    const inactiveCohere = { id: "p2", llm_model_provider: "cohere", prompt_caching_mode: "none" as const, is_active: 0 };
    const all = [primary, inactiveCohere];
    const chain = { provider_ids: ["p1", "p2"] };

    it("resolves inactive members — the runtime still builds them", () => {
      expect(fallbackChainProviders(all, "p1", chain)).toEqual([inactiveCohere]);
    });

    it("an inactive unsupported fallback still poisons the chain verdict", () => {
      const hint = promptCachingHint(true, primary, "model", "Base", fallbackChainProviders(all, "p1", chain));
      expect(hint?.text).toMatch(/fallback chain/);
      expect(hint?.tone).toBe("warning");
    });

    it("excludes the primary and drops ids with no provider object", () => {
      expect(fallbackChainProviders([primary], "p1", { provider_ids: ["p1", "ghost"] })).toEqual([]);
    });

    it("yields nothing without a selected chain", () => {
      expect(fallbackChainProviders(all, "p1", undefined)).toEqual([]);
      expect(fallbackChainProviders(all, "p1", null)).toEqual([]);
    });
  });
});
