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
  fetchNotificationUserSettings,
  updateNotificationUserSettings,
} from "@/services/notificationSettings";

const mockApiRequest = vi.mocked(apiRequest);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

const RAW = {
  conversation_started: true,
  conversation_hostility: false,
  conversation_finalized_hostility: true,
  workflow_failed: false,
  can_manage_workflow_failed: true,
};

const MAPPED = {
  conversationStarted: true,
  conversationHostility: false,
  conversationFinalizedHostility: true,
  workflowFailed: false,
  canManageWorkflowFailed: true,
};

describe("fetchNotificationUserSettings", () => {
  it("GETs /notifications and maps the raw payload to camelCase", async () => {
    mockApiRequest.mockResolvedValue(RAW as never);
    const result = await fetchNotificationUserSettings();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/notifications");
    expect(result).toEqual(MAPPED);
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchNotificationUserSettings()).toBeNull();
  });

  it("returns null (and logs) on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchNotificationUserSettings()).toBeNull();
  });
});

describe("updateNotificationUserSettings", () => {
  it("PATCHes /notifications with only the provided boolean fields and maps the result", async () => {
    mockApiRequest.mockResolvedValue(RAW as never);
    const result = await updateNotificationUserSettings({
      conversationStarted: true,
      workflowFailed: false,
    });
    expect(mockApiRequest).toHaveBeenCalledWith("patch", "/notifications", {
      conversation_started: true,
      workflow_failed: false,
    });
    expect(result).toEqual(MAPPED);
  });

  it("returns null without calling the API when there is nothing to update", async () => {
    const result = await updateNotificationUserSettings({});
    expect(result).toBeNull();
    expect(mockApiRequest).not.toHaveBeenCalled();
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(
      await updateNotificationUserSettings({ conversationStarted: true })
    ).toBeNull();
  });

  it("returns null (and logs) on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(
      await updateNotificationUserSettings({ conversationStarted: true })
    ).toBeNull();
  });
});
