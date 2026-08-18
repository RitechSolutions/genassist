import { describe, expect, it } from "vitest";

import { formatUsd } from "@/helpers/formatCurrency";

const EM_DASH = "—";

describe("formatUsd", () => {
  it("formats a positive amount to four decimals by default", () => {
    expect(formatUsd(1.2345)).toBe("$1.2345");
  });

  it("keeps a real zero distinct from missing data", () => {
    expect(formatUsd(0)).toBe("$0.0000");
  });

  it("renders an em dash for null and undefined", () => {
    expect(formatUsd(null)).toBe(EM_DASH);
    expect(formatUsd(undefined)).toBe(EM_DASH);
  });

  it("renders an em dash for non-finite numbers", () => {
    expect(formatUsd(NaN)).toBe(EM_DASH);
    expect(formatUsd(Infinity)).toBe(EM_DASH);
    expect(formatUsd(-Infinity)).toBe(EM_DASH);
  });

  it("honours a custom fraction digit count", () => {
    expect(formatUsd(1.239, 2)).toBe("$1.24");
    expect(formatUsd(0, 2)).toBe("$0.00");
  });

  it("rounds to the requested precision", () => {
    expect(formatUsd(0.00005)).toBe("$0.0001");
    expect(formatUsd(0.000004)).toBe("$0.0000");
  });

  it("formats negative amounts", () => {
    expect(formatUsd(-2.5)).toBe("$-2.5000");
  });
});
