import { vi, describe, expect, it, afterEach } from "vitest";

// `@/helpers/utils` re-imports the axios/env-backed api module purely for an
// (unused) re-export. Mock it so these pure helpers stay hermetic and never
// depend on Vite env being present.
vi.mock("@/config/api", () => ({ getApiUrlString: "http://localhost/api/" }));

import {
  cn,
  formatDate,
  formatDateTime,
  formatChartDate,
  getTimeFromDatetime,
  formatFeedbackDate,
  tryParse,
  maskInput,
  escapeHtml,
  getFileDownloadUrl,
  downloadBlob,
} from "@/helpers/utils";

describe("cn", () => {
  it("joins truthy class names", () => {
    expect(cn("a", null, undefined, false as unknown as string, "b")).toBe("a b");
  });

  it("merges conflicting tailwind classes (last wins)", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("formatDate", () => {
  it("formats a Date as a long en-US date", () => {
    expect(formatDate(new Date(2026, 1, 17))).toBe("February 17, 2026");
  });
});

describe("formatChartDate", () => {
  it("formats a date-only string as a short month/day label", () => {
    expect(formatChartDate("2026-02-17")).toBe("Feb 17");
  });
});

describe("getTimeFromDatetime", () => {
  it("returns zero-padded H:MM:SS in local time", () => {
    expect(getTimeFromDatetime("2026-02-17T09:05:03")).toBe("9:05:03");
  });
});

describe("formatFeedbackDate", () => {
  it("formats a month/day with zero-padded time", () => {
    expect(formatFeedbackDate("2026-02-17T09:05:00")).toBe("February 17, 09:05");
  });
});

describe("tryParse", () => {
  it("parses JSON objects and numbers", () => {
    expect(tryParse('{"a":1}')).toEqual({ a: 1 });
    expect(tryParse("123")).toBe(123);
  });

  it("double-parses a JSON-encoded JSON string", () => {
    expect(tryParse('"[1,2,3]"')).toEqual([1, 2, 3]);
  });

  it("returns the inner string when the second parse fails", () => {
    expect(tryParse('"hello"')).toBe("hello");
  });

  it("returns the original value when it is not JSON", () => {
    expect(tryParse("plain")).toBe("plain");
  });
});

describe("maskInput", () => {
  it("masks the whole string with asterisks", () => {
    expect(maskInput("secret")).toBe("******");
    expect(maskInput("")).toBe("");
  });

  it("caps the mask length at maxLength", () => {
    expect(maskInput("a".repeat(40))).toBe("*".repeat(36));
    expect(maskInput("abcd", 2)).toBe("**");
  });
});

describe("escapeHtml", () => {
  it("escapes all five HTML-sensitive characters", () => {
    expect(escapeHtml("<b>\"&'")).toBe("&lt;b&gt;&quot;&amp;&#39;");
  });
});

describe("getFileDownloadUrl", () => {
  it("builds a source URL with the tenant query param", () => {
    expect(getFileDownloadUrl("f1", "https://api.example.com/", "t1")).toBe(
      "https://api.example.com/file-manager/files/f1/source?X-Tenant-Id=t1"
    );
  });

  it("supports the download variant", () => {
    expect(
      getFileDownloadUrl("f1", "https://api.example.com/", "t1", "download")
    ).toBe(
      "https://api.example.com/file-manager/files/f1/download?X-Tenant-Id=t1"
    );
  });

  it("omits the tenant param when tenant id is empty", () => {
    expect(getFileDownloadUrl("f1", "https://api.example.com/", "")).toBe(
      "https://api.example.com/file-manager/files/f1/source"
    );
  });
});

describe("formatDateTime", () => {
  it("returns an em dash for empty values", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
    expect(formatDateTime("")).toBe("—");
  });

  it("returns a non-empty locale string for a valid date", () => {
    const out = formatDateTime("2026-02-17T09:05:00");
    expect(out).not.toBe("—");
    expect(out).toMatch(/\d/);
  });
});

describe("downloadBlob", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const setup = () => {
    const anchor = {
      href: "",
      download: "",
      rel: "",
      style: {} as Record<string, string>,
      click: vi.fn(),
      remove: vi.fn(),
    };
    const appendChild = vi.fn();
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:fake"),
      revokeObjectURL,
    });
    vi.stubGlobal("document", {
      createElement: vi.fn(() => anchor),
      body: { appendChild },
    });
    return { anchor, appendChild, revokeObjectURL };
  };

  it("attaches the anchor before clicking so Firefox honours the download", () => {
    vi.useFakeTimers();
    const { anchor, appendChild } = setup();

    downloadBlob(new Blob(["x"]), "model.pkl");

    expect(appendChild).toHaveBeenCalledWith(anchor);
    expect(appendChild.mock.invocationCallOrder[0]).toBeLessThan(
      anchor.click.mock.invocationCallOrder[0]
    );
    expect(anchor.href).toBe("blob:fake");
    expect(anchor.download).toBe("model.pkl");
    expect(anchor.remove).toHaveBeenCalled();
  });

  it("defers revoking the object URL instead of racing the download", () => {
    vi.useFakeTimers();
    const { revokeObjectURL } = setup();

    downloadBlob(new Blob(["x"]), "model.pkl");
    // Revoking in the same tick cancels the download in Firefox/Safari.
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:fake");
  });
});
