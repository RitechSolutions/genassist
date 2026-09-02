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
  fetchOperators,
  fetchOperatorById,
  fetchOperatorsPaginated,
  createOperator,
} from "@/services/operators";
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
  it("GETs /operators/:id and returns it", async () => {
    const operator = { id: "o1" };
    mockApiRequest.mockResolvedValue(operator as never);

    const result = await fetchOperatorById("o1");

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/operators/o1");
    expect(result).toEqual(operator);
  });

  it("returns null when the response is null", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(fetchOperatorById("o1")).resolves.toBeNull();
  });
});

describe("fetchOperatorsPaginated", () => {
  const page = <T,>(items: T[]) => ({
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
  });

  const requestedUrl = () => String(mockApiRequest.mock.calls[0][1]);

  it("defaults to the first page of 20", async () => {
    mockApiRequest.mockResolvedValue(page([{ id: "o1" }]) as never);

    await fetchOperatorsPaginated();

    expect(mockApiRequest).toHaveBeenCalledWith("get", "/operators/list?skip=0&limit=20");
  });

  it("converts page and pageSize into skip and limit", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await fetchOperatorsPaginated(3, 10);

    expect(requestedUrl()).toBe("/operators/list?skip=20&limit=10");
  });

  it("clamps pageSize to the backend maximum of 100", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await fetchOperatorsPaginated(1, 500);

    expect(requestedUrl()).toContain("limit=100");
  });

  it("clamps page and pageSize to their minimums", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await fetchOperatorsPaginated(0, 0);

    expect(requestedUrl()).toBe("/operators/list?skip=0&limit=1");
  });

  it("passes a trimmed search term", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await fetchOperatorsPaginated(1, 20, "  ana  ");

    expect(requestedUrl()).toBe("/operators/list?skip=0&limit=20&search=ana");
  });

  it("omits the search param when it is absent or blank", async () => {
    mockApiRequest.mockResolvedValue(page([]) as never);

    await fetchOperatorsPaginated(1, 20, "   ");
    expect(requestedUrl()).not.toContain("search");

    vi.clearAllMocks();
    mockApiRequest.mockResolvedValue(page([]) as never);
    await fetchOperatorsPaginated(1, 20, undefined);
    expect(requestedUrl()).not.toContain("search");
  });

  it("returns the paginated body unchanged", async () => {
    const body = page([{ id: "o1" }, { id: "o2" }]);
    mockApiRequest.mockResolvedValue(body as never);

    await expect(fetchOperatorsPaginated()).resolves.toEqual(body);
  });

  it("returns an empty page when the response is null (403)", async () => {
    mockApiRequest.mockResolvedValue(null as never);

    await expect(fetchOperatorsPaginated(2, 50)).resolves.toEqual({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      total_pages: 0,
    });
  });

  it("propagates non-403 errors", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));

    await expect(fetchOperatorsPaginated()).rejects.toThrow("boom");
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
