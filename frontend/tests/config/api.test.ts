import { beforeEach, describe, expect, it, vi } from "vitest";

const request = vi.fn();

vi.mock("axios", () => {
  class AxiosError extends Error {}
  const create = () => ({
    request,
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  });
  return {
    default: { create, get: vi.fn(), post: vi.fn() },
    AxiosError,
    create,
  };
});

vi.mock("@sentry/react", () => ({ captureException: vi.fn() }));

vi.stubEnv("VITE_PUBLIC_API_URL", "http://localhost/api/");

const { apiRequest } = await import("@/config/api");
const { isServerDown, setServerUp } = await import("@/config/serverStatus");

const httpError = (status: number, data: unknown) => ({
  response: { status, data },
});

beforeEach(() => {
  vi.clearAllMocks();
  setServerUp();
});

describe("apiRequest server status", () => {
  it("keeps the server up when a 502 carries this API's error envelope", async () => {
    request.mockRejectedValue(
      httpError(502, { error_key: "PROMPT_MODEL_CALL_FAILED", error: "Nope" }),
    );

    await expect(apiRequest("POST", "genagent/prompt-editor/evaluate/x")).rejects.toBeDefined();
    expect(isServerDown()).toBe(false);
  });

  it("keeps the server up when a 504 carries this API's error envelope", async () => {
    request.mockRejectedValue(
      httpError(504, { error_key: "PROMPT_EXECUTION_TIMEOUT" }),
    );

    await expect(apiRequest("POST", "genagent/prompt-editor/evaluate/x")).rejects.toBeDefined();
    expect(isServerDown()).toBe(false);
  });

  it("marks the server down for an infrastructure 502 with a proxy body", async () => {
    request.mockRejectedValue(httpError(502, "<html>Bad Gateway</html>"));

    await expect(apiRequest("GET", "anything")).rejects.toBeDefined();
    expect(isServerDown()).toBe(true);
  });

  it("marks the server down for a 503 whose body is an unrelated object", async () => {
    request.mockRejectedValue(httpError(503, { detail: "upstream unavailable" }));

    await expect(apiRequest("GET", "anything")).rejects.toBeDefined();
    expect(isServerDown()).toBe(true);
  });

  it("returns null and leaves the server up on a 403", async () => {
    request.mockRejectedValue(httpError(403, { error_key: "FORBIDDEN" }));

    await expect(apiRequest("GET", "anything")).resolves.toBeNull();
    expect(isServerDown()).toBe(false);
  });

  it("leaves a 500 alone, envelope or not", async () => {
    request.mockRejectedValue(httpError(500, { error_key: "SOMETHING" }));

    await expect(apiRequest("GET", "anything")).rejects.toBeDefined();
    expect(isServerDown()).toBe(false);
  });
});
