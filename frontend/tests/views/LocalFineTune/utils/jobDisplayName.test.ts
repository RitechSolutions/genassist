import { describe, it, expect } from "vitest";
import type { LocalFineTuneJob } from "@/interfaces/localFineTune.interface";
import {
  getLocalFineTuneJobDisplayName,
  getLocalFineTuneJobNameSubtitle,
} from "@/views/LocalFineTune/utils/jobDisplayName";

const mkJob = (over: Partial<LocalFineTuneJob>): LocalFineTuneJob =>
  ({ id: "id-1", model: "base-model", status: "running", ...over }) as LocalFineTuneJob;

describe("getLocalFineTuneJobDisplayName", () => {
  it("prefers a trimmed non-empty suffix", () => {
    expect(getLocalFineTuneJobDisplayName(mkJob({ suffix: "my-model" }))).toBe("my-model");
    expect(getLocalFineTuneJobDisplayName(mkJob({ suffix: "  spaced  " }))).toBe("spaced");
  });

  it("ignores blank/whitespace/null suffix and falls to fine_tuned_model basename", () => {
    expect(
      getLocalFineTuneJobDisplayName(
        mkJob({ suffix: "   ", fine_tuned_model: "path/to/model-v2" })
      )
    ).toBe("model-v2");
    expect(
      getLocalFineTuneJobDisplayName(mkJob({ suffix: null, fine_tuned_model: "single" }))
    ).toBe("single");
  });

  it("falls through when fine_tuned_model basename is empty (trailing slash)", () => {
    expect(
      getLocalFineTuneJobDisplayName(mkJob({ fine_tuned_model: "a/b/", model: "gpt" }))
    ).toBe("gpt");
  });

  it("falls back to trimmed model, then id, then em-dash", () => {
    expect(getLocalFineTuneJobDisplayName(mkJob({ model: "  gpt  " }))).toBe("gpt");
    expect(getLocalFineTuneJobDisplayName(mkJob({ model: "", id: "job-1" }))).toBe("job-1");
    expect(getLocalFineTuneJobDisplayName(mkJob({ model: "", id: "" }))).toBe("—");
  });
});

describe("getLocalFineTuneJobNameSubtitle", () => {
  it("returns the trimmed model when it differs from the primary name", () => {
    expect(getLocalFineTuneJobNameSubtitle(mkJob({ model: "gpt" }), "my-suffix")).toBe("gpt");
    expect(getLocalFineTuneJobNameSubtitle(mkJob({ model: "  gpt  " }), "my-suffix")).toBe("gpt");
  });

  it("returns null when model equals the primary (after trim)", () => {
    expect(getLocalFineTuneJobNameSubtitle(mkJob({ model: "gpt" }), "gpt")).toBeNull();
    expect(getLocalFineTuneJobNameSubtitle(mkJob({ model: "  gpt  " }), "gpt")).toBeNull();
  });

  it("returns null when model is blank/absent", () => {
    expect(getLocalFineTuneJobNameSubtitle(mkJob({ model: "" }), "primary")).toBeNull();
    expect(
      getLocalFineTuneJobNameSubtitle(mkJob({ model: undefined as unknown as string }), "primary")
    ).toBeNull();
  });
});
