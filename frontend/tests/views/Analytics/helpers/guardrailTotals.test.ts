import { describe, expect, it } from "vitest";
import type { GuardrailTotalsItem } from "@/interfaces/analyticsReports.interface";
import { segmentWidth, summarizeGuardrailTotals } from "@/views/Analytics/helpers/guardrailTotals";

const item = (check_type: string, blocked: number, flagged: number, errors = 0): GuardrailTotalsItem => ({
  check_type,
  blocked,
  flagged,
  errors,
});

const SAMPLE = [
  item("blocked_words", 12, 3),
  item("denied_topic", 184, 41),
  item("detector_error", 0, 0, 9),
  item("grounding", 6, 0),
  item("harmful_content", 37, 1204),
  item("malformed_verdict", 2, 1),
  item("prompt_attack", 2318, 96),
  item("provider_refusal", 4, 0),
  item("too_long", 1, 0),
  item("untrusted_content", 0, 58),
];

describe("summarizeGuardrailTotals", () => {
  it("ranks checks by blocked plus flagged and leaves check failures out of the rows", () => {
    const summary = summarizeGuardrailTotals(SAMPLE);
    expect(summary.rows.map((row) => row.label)).toEqual([
      "Prompt attack",
      "Harmful content",
      "Denied topic",
      "Hidden instructions",
      "Blocked word",
      "Grounding",
      "Provider refusal",
      "No clear verdict",
      "Too long to check",
    ]);
    expect(summary.busiest).toBe(2414);
  });

  it("totals the legend from every item and counts check failures apart", () => {
    const summary = summarizeGuardrailTotals(SAMPLE);
    expect([summary.blocked, summary.flagged, summary.failed]).toEqual([2564, 1403, 9]);
  });

  it("orders checks with equal totals by label", () => {
    const summary = summarizeGuardrailTotals([item("too_long", 2, 0), item("grounding", 1, 1)]);
    expect(summary.rows.map((row) => row.label)).toEqual(["Grounding", "Too long to check"]);
  });

  it("gives no rows but keeps the failures when checks only failed", () => {
    const summary = summarizeGuardrailTotals([item("detector_error", 0, 0, 3)]);
    expect(summary.rows).toEqual([]);
    expect([summary.blocked, summary.flagged, summary.failed, summary.busiest]).toEqual([0, 0, 3, 0]);
  });
});

describe("segmentWidth", () => {
  it.each([
    [1, 2414, "1.5%"],
    [0, 2414, "0%"],
    [2414, 2414, "100%"],
    [1207, 2414, "50%"],
    [3, 0, "0%"],
  ])("sizes %i against a busiest row of %i as %s", (count, busiest, width) => {
    expect(segmentWidth(count, busiest)).toBe(width);
  });
});
