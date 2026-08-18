import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// NOTE: aiAgents.ts does not use apiRequest / @/config/api at all — it is an
// in-memory mock-data module backed by setTimeout. There is therefore no
// "@/config/api" mock here; the async functions are driven with fake timers.
import {
  aiProviders,
  aiModels,
  getProviders,
  getModelsByProvider,
  getAllAgents,
  getAgentById,
  createAgent,
  updateAgent,
  deleteAgent,
} from "@/services/aiAgents";

describe("aiAgents service (in-memory mock data)", () => {
  describe("getProviders", () => {
    it("resolves the provider catalog with each provider's models populated", async () => {
      const providers = await getProviders();
      expect(providers).toBe(aiProviders);
      expect(providers.map((p) => p.id)).toEqual(["openai", "anthropic", "google", "mistral"]);
      const openai = providers.find((p) => p.id === "openai");
      expect(openai?.models).toHaveLength(3);
      expect(openai?.models.every((m) => m.providerId === "openai")).toBe(true);
    });
  });

  describe("getModelsByProvider", () => {
    it("returns the models for a known provider", async () => {
      const anthropic = await getModelsByProvider("anthropic");
      expect(anthropic).toEqual(aiModels.filter((m) => m.providerId === "anthropic"));
      expect(anthropic).toHaveLength(3);
    });

    it("returns an empty array for an unknown provider", async () => {
      expect(await getModelsByProvider("does-not-exist")).toEqual([]);
    });
  });

  describe("async mock functions", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("getAllAgents resolves the seeded agents after the delay", async () => {
      const pending = getAllAgents();
      await vi.advanceTimersByTimeAsync(500);
      const agents = await pending;
      expect(agents).toHaveLength(3);
      expect(agents.map((a) => a.id)).toEqual(["1", "2", "3"]);
    });

    it("getAgentById resolves the matching agent", async () => {
      const pending = getAgentById("2");
      await vi.advanceTimersByTimeAsync(500);
      expect((await pending)?.name).toBe("Sales Agent");
    });

    it("getAgentById resolves undefined when no agent matches", async () => {
      const pending = getAgentById("nope");
      await vi.advanceTimersByTimeAsync(500);
      expect(await pending).toBeUndefined();
    });

    it("createAgent assigns an id and derives filesCount from the files array", async () => {
      const pending = createAgent({
        name: "New",
        provider: "OpenAI",
        model: "gpt-4o",
        filesCount: 99,
        files: [{ id: "a", name: "A" }],
        systemPrompt: "",
      } as never);
      await vi.advanceTimersByTimeAsync(500);
      const created = await pending;
      expect(typeof created.id).toBe("string");
      expect(created.id.length).toBeGreaterThan(0);
      expect(created.files).toHaveLength(1);
      expect(created.filesCount).toBe(1);
    });

    it("createAgent defaults files to an empty array and filesCount to 0", async () => {
      const pending = createAgent({
        name: "New",
        provider: "OpenAI",
        model: "gpt-4o",
        filesCount: 0,
        systemPrompt: "",
      } as never);
      await vi.advanceTimersByTimeAsync(500);
      const created = await pending;
      expect(created.files).toEqual([]);
      expect(created.filesCount).toBe(0);
    });

    it("updateAgent merges the patch onto an existing agent", async () => {
      const pending = updateAgent("1", { name: "Renamed" });
      await vi.advanceTimersByTimeAsync(500);
      const updated = await pending;
      expect(updated.id).toBe("1");
      expect(updated.name).toBe("Renamed");
    });

    it("updateAgent rejects when the agent does not exist", async () => {
      const pending = updateAgent("nope", { name: "x" });
      const assertion = expect(pending).rejects.toThrow("Agent not found");
      await vi.advanceTimersByTimeAsync(500);
      await assertion;
    });

    it("deleteAgent resolves for an existing agent", async () => {
      const pending = deleteAgent("1");
      await vi.advanceTimersByTimeAsync(500);
      await expect(pending).resolves.toBeUndefined();
    });

    it("deleteAgent rejects when the agent does not exist", async () => {
      const pending = deleteAgent("nope");
      const assertion = expect(pending).rejects.toThrow("Agent not found");
      await vi.advanceTimersByTimeAsync(500);
      await assertion;
    });
  });
});
