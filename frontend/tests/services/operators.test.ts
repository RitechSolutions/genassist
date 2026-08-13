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
import { fetchOperators, fetchOperatorById, createOperator } from "@/services/operators";
import type { Operator } from "@/interfaces/operator.interface";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("fetchOperators", () => {
  it("GETs /operators/ and returns the array", async () => {
    const operators = [{ id: "o1" }];
    mockApiRequest.mockResolvedValue(operators as never);

    const result = await fetchOperators();

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/operators/");
    expect(result).toEqual(operators);
  });

  it("returns an empty array when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchOperators()).resolves.toEqual([]);
  });

  it("returns an empty array when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue({} as never);
    await expect(fetchOperators()).resolves.toEqual([]);
  });
});

describe("fetchOperatorById", () => {
  it("GETs /operator/:id and returns it", async () => {
    const operator = { id: "o1" };
    mockApiRequest.mockResolvedValue(operator as never);

    const result = await fetchOperatorById("o1");

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/operator/o1");
    expect(result).toEqual(operator);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchOperatorById("o1")).resolves.toBeNull();
  });
});

describe("createOperator", () => {
  it("POSTs the operator to /operators/ and returns it", async () => {
    const data = { name: "Bob" } as unknown as Operator;
    const created = { id: "o2", name: "Bob" };
    mockApiRequest.mockResolvedValue(created as never);

    const result = await createOperator(data);

    expect(mockApiRequest).toHaveBeenCalledWith("post", "/operators/", data);
    expect(result).toEqual(created);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createOperator({} as Operator)).resolves.toBeNull();
  });
});
