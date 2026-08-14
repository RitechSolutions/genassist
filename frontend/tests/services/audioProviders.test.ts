import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  getApiUrlString: "http://localhost/api/",
  formatUploadOrNetworkError: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  API_DEFAULT_TIMEOUT_MS: 1000,
  API_UPLOAD_TIMEOUT_MS: 1000,
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import {
  getAllAudioProviders,
  getAudioProvidersMinimal,
  getAudioProvidersByCapability,
  getAudioProvider,
  createAudioProvider,
  updateAudioProvider,
  deleteAudioProvider,
  getAudioProviderFormSchemas,
  getAudioProviderNodeSchemas,
  testAudioProviderConnection,
} from "@/services/audioProviders";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllAudioProviders", () => {
  it("returns the providers", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getAllAudioProviders()).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/");
  });
});

describe("getAudioProvidersMinimal", () => {
  it("returns the minimal providers", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getAudioProvidersMinimal()).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/minimal");
  });
});

describe("getAudioProvidersByCapability", () => {
  it("returns providers filtered by capability", async () => {
    const providers = [{ id: "p1" }];
    mockApiRequest.mockResolvedValue(providers as never);
    expect(await getAudioProvidersByCapability("tts")).toBe(providers);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/by-capability/tts");
  });
});

describe("getAudioProvider", () => {
  it("returns the provider", async () => {
    const provider = { id: "p1" };
    mockApiRequest.mockResolvedValue(provider as never);
    expect(await getAudioProvider("p1")).toBe(provider);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/p1");
  });
});

describe("createAudioProvider", () => {
  it("posts a JSON-cloned payload", async () => {
    const data = { name: "x", config: { a: 1 } } as never;
    const created = { id: "p1" };
    mockApiRequest.mockResolvedValue(created as never);
    expect(await createAudioProvider(data)).toBe(created);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "audio-providers", {
      name: "x",
      config: { a: 1 },
    });
  });
});

describe("updateAudioProvider", () => {
  it("patches a JSON-cloned payload", async () => {
    const data = { name: "x" } as never;
    const updated = { id: "p1" };
    mockApiRequest.mockResolvedValue(updated as never);
    expect(await updateAudioProvider("p1", data)).toBe(updated);
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "audio-providers/p1", { name: "x" });
  });
});

describe("deleteAudioProvider", () => {
  it("deletes the provider", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteAudioProvider("p1");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "audio-providers/p1");
  });
});

describe("getAudioProviderFormSchemas", () => {
  it("fetches the form schemas", async () => {
    const schema = { fields: [] };
    mockApiRequest.mockResolvedValue(schema as never);
    expect(await getAudioProviderFormSchemas()).toBe(schema);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/form-schemas");
  });
});

describe("getAudioProviderNodeSchemas", () => {
  it("fetches the node schemas", async () => {
    const schema = { nodes: [] };
    mockApiRequest.mockResolvedValue(schema as never);
    expect(await getAudioProviderNodeSchemas()).toBe(schema);
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "audio-providers/node-schemas");
  });
});

describe("testAudioProviderConnection", () => {
  it("posts without a provider_id query when none is given", async () => {
    const result = { success: true, message: "ok" };
    mockApiRequest.mockResolvedValue(result as never);
    const res = await testAudioProviderConnection("elevenlabs", "tts", { api_key: "k" });
    expect(res).toBe(result);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "audio-providers/test-connection", {
      provider_type: "elevenlabs",
      capability: "tts",
      connection_data: { api_key: "k" },
    });
  });

  it("appends the provider_id query when given", async () => {
    mockApiRequest.mockResolvedValue({ success: true, message: "ok" } as never);
    await testAudioProviderConnection("elevenlabs", "tts", { api_key: "k" }, "p1");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "audio-providers/test-connection?provider_id=p1",
      { provider_type: "elevenlabs", capability: "tts", connection_data: { api_key: "k" } }
    );
  });
});
