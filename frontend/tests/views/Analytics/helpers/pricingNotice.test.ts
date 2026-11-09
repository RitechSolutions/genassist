import { describe, expect, it } from "vitest";
import { pricingNoticeCopy } from "@/views/Analytics/helpers/pricingNotice";

const COVERAGE_BODY =
  "Totals below are the priced subtotal. Rates added under LLM Settings › LLM Providers apply to new calls only.";

describe("pricingNoticeCopy", () => {
  it("joins both notices into one sentence with one dismiss label", () => {
    expect(pricingNoticeCopy(12.3, 412, true, true)).toEqual({
      lead: "12.3% of tokens have no configured rate and 412 calls used bundled fallback rates.",
      body: COVERAGE_BODY,
      dismissLabel: "Dismiss pricing notices",
    });
  });

  it("keeps each notice's own copy when only one shows", () => {
    expect(pricingNoticeCopy(0.3, 412, true, false)).toEqual({
      lead: "0.3% of tokens have no configured rate.",
      body: COVERAGE_BODY,
      dismissLabel: "Dismiss pricing coverage notice",
    });
    expect(pricingNoticeCopy(0, 412, false, true)).toEqual({
      lead: "412 calls used bundled fallback rates.",
      body: "Add matching rates to price new calls from your own configuration.",
      dismissLabel: "Dismiss fallback rates notice",
    });
  });

  it("is null when neither shows", () => {
    expect(pricingNoticeCopy(12.3, 412, false, false)).toBeNull();
  });
});
