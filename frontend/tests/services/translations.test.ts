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
  getLanguages,
  getAllLanguages,
  createLanguage,
  updateLanguage,
  deleteLanguage,
  getTranslations,
  createTranslation,
  updateTranslation,
  deleteTranslation,
  getTranslationByKey,
} from "@/services/translations";

const mockApiRequest = vi.mocked(apiRequest);
beforeEach(() => vi.clearAllMocks());

describe("getLanguages", () => {
  it("GETs translations/languages and returns the array", async () => {
    const langs = [{ code: "en", name: "English" }];
    mockApiRequest.mockResolvedValue(langs as never);
    const result = await getLanguages();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "translations/languages");
    expect(result).toEqual(langs);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getLanguages()).toEqual([]);
  });
});

describe("getAllLanguages", () => {
  it("GETs translations/languages/all and returns the array", async () => {
    const langs = [{ code: "de", name: "German" }];
    mockApiRequest.mockResolvedValue(langs as never);
    const result = await getAllLanguages();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "translations/languages/all");
    expect(result).toEqual(langs);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue({ nope: true } as never);
    expect(await getAllLanguages()).toEqual([]);
  });
});

describe("createLanguage", () => {
  it("POSTs the payload and returns the created language", async () => {
    const created = { code: "fr", name: "French" };
    mockApiRequest.mockResolvedValue(created as never);
    const result = await createLanguage({ code: "fr", name: "French" });
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "translations/languages", {
      code: "fr",
      name: "French",
    });
    expect(result).toEqual(created);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(createLanguage({ code: "fr", name: "French" })).rejects.toThrow(
      "Failed to create language"
    );
  });
});

describe("updateLanguage", () => {
  it("PATCHes translations/languages/:id and returns the language", async () => {
    const updated = { code: "fr", name: "Francais" };
    mockApiRequest.mockResolvedValue(updated as never);
    const result = await updateLanguage("fr", { name: "Francais" });
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "translations/languages/fr", {
      name: "Francais",
    });
    expect(result).toEqual(updated);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateLanguage("fr", { name: "x" })).rejects.toThrow(
      "Failed to update language"
    );
  });
});

describe("deleteLanguage", () => {
  it("DELETEs translations/languages/:id", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteLanguage("fr");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "translations/languages/fr");
  });
});

describe("getTranslations", () => {
  it("GETs translations and returns the array", async () => {
    const rows = [{ key: "hello", translations: {} }];
    mockApiRequest.mockResolvedValue(rows as never);
    const result = await getTranslations();
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "translations");
    expect(result).toEqual(rows);
  });

  it("returns [] when the response is not an array", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    expect(await getTranslations()).toEqual([]);
  });
});

describe("createTranslation", () => {
  it("POSTs the translation payload and returns it", async () => {
    const created = { key: "hi", translations: { en: "Hi" } };
    mockApiRequest.mockResolvedValue(created as never);
    const payload = { key: "hi", translations: { en: "Hi" } };
    const result = await createTranslation(payload);
    expect(mockApiRequest).toHaveBeenCalledWith("POST", "translations", payload);
    expect(result).toEqual(created);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(
      createTranslation({ key: "hi", translations: {} })
    ).rejects.toThrow("Failed to create translation");
  });
});

describe("updateTranslation", () => {
  it("PATCHes translations/:encodedKey and returns the translation", async () => {
    const updated = { key: "a/b", translations: { en: "X" } };
    mockApiRequest.mockResolvedValue(updated as never);
    const result = await updateTranslation("a/b", { translations: { en: "X" } });
    expect(mockApiRequest).toHaveBeenCalledWith("PATCH", "translations/a%2Fb", {
      translations: { en: "X" },
    });
    expect(result).toEqual(updated);
  });

  it("throws when the response is falsy", async () => {
    mockApiRequest.mockResolvedValue(null as never);
    await expect(updateTranslation("k", {})).rejects.toThrow(
      "Failed to update translation"
    );
  });
});

describe("deleteTranslation", () => {
  it("DELETEs translations/:encodedKey", async () => {
    mockApiRequest.mockResolvedValue(undefined as never);
    await deleteTranslation("a/b");
    expect(mockApiRequest).toHaveBeenCalledWith("DELETE", "translations/a%2Fb");
  });
});

describe("getTranslationByKey", () => {
  it("GETs translations/:encodedKey and returns the translation", async () => {
    const row = { key: "a b", translations: {} };
    mockApiRequest.mockResolvedValue(row as never);
    const result = await getTranslationByKey("a b");
    expect(mockApiRequest).toHaveBeenCalledWith("GET", "translations/a%20b");
    expect(result).toEqual(row);
  });

  it("returns null on error", async () => {
    mockApiRequest.mockRejectedValue(new Error("boom"));
    expect(await getTranslationByKey("k")).toBeNull();
  });
});
