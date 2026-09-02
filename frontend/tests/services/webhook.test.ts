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
  getAllWebhooks,
  getWebhook,
  createWebhook,
  updateWebhook,
  deleteWebhook,
  executeWebhook,
} from "@/services/webhook";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getAllWebhooks", () => {
  it("GETs webhooks and returns the array", async () => {
    const rows = [{ id: "1", name: "hook" }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getAllWebhooks();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "webhooks");
    expect(result).toEqual(rows);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getAllWebhooks()).toEqual([]);
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getAllWebhooks()).rejects.toThrow("boom");
  });
});

describe("getWebhook", () => {
  it("GETs webhooks/:id and returns the webhook", async () => {
    const row = { id: "5", name: "hook" };
    mockApiRequest.mockResolvedValue(row as never);
    const result = await getWebhook("5");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "webhooks/5");
    expect(result).toEqual(row);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getWebhook("5")).toBeNull();
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(getWebhook("5")).rejects.toThrow("boom");
  });
});

describe("createWebhook", () => {
  it("POSTs webhooks and returns the created webhook", async () => {
    const created = { id: "1", name: "hook" };
    mockApiRequest.mockResolvedValue(created as never);
    const payload = { name: "hook", url: "https://x.test" };
    const result = await createWebhook(payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "webhooks", payload);
    expect(result).toEqual(created);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createWebhook({ name: "hook" } as never)).rejects.toThrow(
      "Failed to create webhook"
    );
  });
});

describe("updateWebhook", () => {
  it("PUTs webhooks/:id and returns the updated webhook", async () => {
    const updated = { id: "2", name: "hook2" };
    mockApiRequest.mockResolvedValue(updated as never);
    const payload = { name: "hook2" };
    const result = await updateWebhook("2", payload as never);
    expect(mockApiRequest).toHaveBeenCalledWith("PUT", "webhooks/2", payload);
    expect(result).toEqual(updated);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateWebhook("2", { name: "x" } as never)).rejects.toThrow(
      "Failed to update webhook"
    );
  });
});

describe("deleteWebhook", () => {
  it("DELETEs webhooks/:id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteWebhook("3");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "webhooks/3");
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(deleteWebhook("3")).rejects.toThrow("boom");
  });
});

describe("executeWebhook", () => {
  it("POSTs to execute-workflow by default", async () => {
    mockApiRequest.mockResolvedValue({ ok: true } as never);
    const payload = { foo: "bar" };
    const result = await executeWebhook("7", payload);
    expect(mockApiRequest).toHaveBeenCalledWith(
      "POST",
      "webhooks/7/execute-workflow",
      payload
    );
    expect(result).toEqual({ ok: true });
  });

  it("GETs execute-workflow when method is GET", async () => {
    mockApiRequest.mockResolvedValue({ ok: true } as never);
    const payload = { foo: "bar" };
    await executeWebhook("7", payload, "GET");
    expect(mockApiRequest).toHaveBeenCalledWith(
      "GET",
      "webhooks/7/execute-workflow",
      payload
    );
  });

  it("re-throws on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(executeWebhook("7", {})).rejects.toThrow("boom");
  });
});
