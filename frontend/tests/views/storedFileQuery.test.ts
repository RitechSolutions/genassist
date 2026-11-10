import { describe, it, expect, vi, beforeEach } from "vitest";
import { AxiosError } from "axios";
import { QueryClient } from "@tanstack/react-query";

vi.mock("@/config/api", () => ({
  apiRequest: vi.fn(),
  getApiUrl: vi.fn(async () => "http://localhost/api/"),
  api: { request: vi.fn() },
}));

import { apiRequest } from "@/config/api";
import { storedFileQuery } from "@/views/MLModels/helpers/useStoredFileName";

const mockApiRequest = vi.mocked(apiRequest);
const record = { id: "f1", name: "f1.pkl", original_filename: "titanic.pkl", size: 10 };
const httpError = (status: number) =>
  new AxiosError("err", "ERR_BAD_RESPONSE", undefined, undefined, { status } as never);

// Same staleTime as the app's QueryClient (src/main.tsx).
const newClient = () =>
  new QueryClient({ defaultOptions: { queries: { staleTime: 1000 * 60 * 5 } } });

beforeEach(() => mockApiRequest.mockReset());

describe("storedFileQuery", () => {
  it("does not cache a failed record read: the next read asks the server again", async () => {
    const client = newClient();
    mockApiRequest.mockRejectedValueOnce(httpError(500)).mockResolvedValueOnce(record);

    await expect(client.fetchQuery(storedFileQuery("f1"))).rejects.toBeInstanceOf(AxiosError);
    const second = await client.fetchQuery(storedFileQuery("f1"));

    expect(mockApiRequest).toHaveBeenCalledTimes(2);
    expect(second).toEqual(record);
  });

  it("caches a 404 as 'no record' so the fallback name is used", async () => {
    const client = newClient();
    mockApiRequest.mockRejectedValueOnce(httpError(404));

    expect(await client.fetchQuery(storedFileQuery("f1"))).toBeNull();
    expect(await client.fetchQuery(storedFileQuery("f1"))).toBeNull();
    expect(mockApiRequest).toHaveBeenCalledTimes(1);
  });
});
