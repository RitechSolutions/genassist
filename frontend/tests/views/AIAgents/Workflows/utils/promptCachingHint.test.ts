import { describe, expect, it } from "vitest";
import { promptCachingHint } from "@/views/AIAgents/Workflows/utils/promptCachingHint";

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

  it("warns about a provider family that takes no cache markers", () => {
    expect(promptCachingHint(true, cohere, "model", "Base")).toEqual({
      text: "This provider does not support prompt caching, so the setting has no effect.",
      tone: "warning",
    });
  });

  it("tells a family that caches on its own the setting is moot, never that caching is unavailable", () => {
    for (const family of automaticFamilies) {
      const hint = promptCachingHint(true, { llm_model_provider: family }, "model", "Base");
      expect(hint?.tone).toBe("info");
      expect(hint?.text).toMatch(/cache long prompts automatically/);
      expect(hint?.text).not.toMatch(/does not support|cannot cache|no caching/i);
    }
  });

  it("passes anthropic and bedrock through", () => {
    expect(promptCachingHint(true, anthropic, "model", "Base")).toBeNull();
    expect(promptCachingHint(true, { llm_model_provider: "bedrock" }, "model", "Base")).toBeNull();
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
    expect(promptCachingHint(true, cohere, "agent", "ReActAgent")?.text).toMatch(/does not support prompt caching/);
    expect(promptCachingHint(true, openai, "agent", "ReActAgent")?.tone).toBe("info");
  });
});
