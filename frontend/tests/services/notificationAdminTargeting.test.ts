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
  fetchNotificationAdminTargeting,
  putNotificationAdminTargeting,
} from "@/services/notificationAdminTargeting";

const mockApiRequest = vi.mocked(apiRequest);

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("fetchNotificationAdminTargeting", () => {
  it("GETs the targeting endpoint and maps each type to camelCase", async () => {
    mockApiRequest.mockResolvedValue({
      types: [
        {
          type_key: "conversation_started",
          allow_all_tenant_users: true,
          user_ids: ["u1"],
          group_ids: ["g1"],
        },
      ],
    } as never);
    const result = await fetchNotificationAdminTargeting();
    expect(mockApiRequest).toHaveBeenCalledWith("get", "/notifications/admin/targeting");
    expect(result).toEqual([
      {
        typeKey: "conversation_started",
        allowAllTenantUsers: true,
        userIds: ["u1"],
        groupIds: ["g1"],
      },
    ]);
  });

  it("defaults missing user_ids / group_ids to empty arrays", async () => {
    mockApiRequest.mockResolvedValue({
      types: [
        {
          type_key: "x",
          allow_all_tenant_users: false,
          user_ids: undefined,
          group_ids: undefined,
        },
      ],
    } as never);
    const result = await fetchNotificationAdminTargeting();
    expect(result).toEqual([
      { typeKey: "x", allowAllTenantUsers: false, userIds: [], groupIds: [] },
    ]);
  });

  it("returns null when there are no types", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    expect(await fetchNotificationAdminTargeting()).toBeNull();
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await fetchNotificationAdminTargeting()).toBeNull();
  });

  it("returns null (and logs) on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await fetchNotificationAdminTargeting()).toBeNull();
  });
});

describe("putNotificationAdminTargeting", () => {
  it("PUTs the snake_case body to the encoded type key and maps the result", async () => {
    mockApiRequest.mockResolvedValue({
      type_key: "a/b",
      allow_all_tenant_users: false,
      user_ids: ["u1"],
      group_ids: [],
    } as never);
    const result = await putNotificationAdminTargeting("a/b", {
      allowAllTenantUsers: false,
      userIds: ["u1"],
      groupIds: [],
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "put",
      "/notifications/admin/targeting/a%2Fb",
      {
        allow_all_tenant_users: false,
        user_ids: ["u1"],
        group_ids: [],
      }
    );
    expect(result).toEqual({
      typeKey: "a/b",
      allowAllTenantUsers: false,
      userIds: ["u1"],
      groupIds: [],
    });
  });

  it("returns null when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    const result = await putNotificationAdminTargeting("k", {
      allowAllTenantUsers: true,
      userIds: [],
      groupIds: [],
    });
    expect(result).toBeNull();
  });

  it("re-throws (and logs) on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    await expect(
      putNotificationAdminTargeting("k", {
        allowAllTenantUsers: true,
        userIds: [],
        groupIds: [],
      })
    ).rejects.toThrow("boom");
  });
});
