import { describe, it, expect } from "vitest";
import {
  inProgressStatuses,
  formatStatusLabel,
  normalizePercent,
  normalizeNumber,
  normalizeSeconds,
  formatNumber,
  getAccuracyColor,
  formatDate,
  getAccuracyFromMetrics,
  buildAccuracySeries,
} from "@/views/FineTune/utils/utils";

describe("inProgressStatuses", () => {
  it("contains the four in-progress statuses", () => {
    expect(inProgressStatuses.has("running")).toBe(true);
    expect(inProgressStatuses.has("queued")).toBe(true);
    expect(inProgressStatuses.has("validating_files")).toBe(true);
    expect(inProgressStatuses.has("saving_model")).toBe(true);
    expect(inProgressStatuses.size).toBe(4);
  });

  it("does not contain terminal statuses", () => {
    expect(inProgressStatuses.has("succeeded")).toBe(false);
    expect(inProgressStatuses.has("failed")).toBe(false);
  });
});

describe("formatStatusLabel", () => {
  it("returns 'Unknown' for empty/falsy input", () => {
    expect(formatStatusLabel("")).toBe("Unknown");
  });

  it("title-cases a single word", () => {
    expect(formatStatusLabel("running")).toBe("Running");
  });

  it("splits on underscores and title-cases each part", () => {
    expect(formatStatusLabel("validating_files")).toBe("Validating Files");
    expect(formatStatusLabel("saving_model")).toBe("Saving Model");
  });

  it("only upper-cases the first character of each part", () => {
    expect(formatStatusLabel("someTHING_here")).toBe("SomeTHING Here");
  });
});

describe("normalizePercent", () => {
  it("returns null for null/undefined", () => {
    expect(normalizePercent(undefined)).toBeNull();
    expect(normalizePercent(null)).toBeNull();
  });

  it("returns null for non-finite / non-numeric values", () => {
    expect(normalizePercent("abc")).toBeNull();
    expect(normalizePercent(Infinity)).toBeNull();
    expect(normalizePercent(NaN)).toBeNull();
  });

  it("scales fractional (<=1) values to percent and rounds", () => {
    expect(normalizePercent(0.85)).toBe(85);
    expect(normalizePercent(0.856)).toBe(86);
    expect(normalizePercent(1)).toBe(100);
    expect(normalizePercent("0.5")).toBe(50);
  });

  it("leaves values >1 as-is (just rounds)", () => {
    expect(normalizePercent(50)).toBe(50);
    expect(normalizePercent(1.5)).toBe(2);
    expect(normalizePercent(99.4)).toBe(99);
  });

  it("treats 0 and empty-string (coerces to 0) as 0", () => {
    expect(normalizePercent(0)).toBe(0);
    expect(normalizePercent("")).toBe(0);
  });
});

describe("normalizeNumber", () => {
  it("returns null for null/undefined", () => {
    expect(normalizeNumber(undefined)).toBeNull();
    expect(normalizeNumber(null)).toBeNull();
  });

  it("returns null for non-finite values", () => {
    expect(normalizeNumber("abc")).toBeNull();
    expect(normalizeNumber(Infinity)).toBeNull();
    expect(normalizeNumber(NaN)).toBeNull();
  });

  it("returns the finite number, without scaling", () => {
    expect(normalizeNumber("5")).toBe(5);
    expect(normalizeNumber(0)).toBe(0);
    expect(normalizeNumber(-3.5)).toBe(-3.5);
    expect(normalizeNumber("")).toBe(0);
  });
});

describe("normalizeSeconds", () => {
  it("returns null for null/undefined", () => {
    expect(normalizeSeconds(undefined)).toBeNull();
    expect(normalizeSeconds(null)).toBeNull();
  });

  it("returns null for non-finite or negative values", () => {
    expect(normalizeSeconds("abc")).toBeNull();
    expect(normalizeSeconds(Infinity)).toBeNull();
    expect(normalizeSeconds(-1)).toBeNull();
  });

  it("rounds non-negative values", () => {
    expect(normalizeSeconds(5.6)).toBe(6);
    expect(normalizeSeconds(0)).toBe(0);
    expect(normalizeSeconds("10.9")).toBe(11);
    expect(normalizeSeconds(3.2)).toBe(3);
  });
});

describe("formatNumber", () => {
  it("returns em-dash for null/undefined/NaN", () => {
    expect(formatNumber(undefined)).toBe("—");
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(NaN)).toBe("—");
    expect(formatNumber("abc")).toBe("—");
  });

  it("formats numbers using the default Intl.NumberFormat (locale-agnostic assertion)", () => {
    const fmt = new Intl.NumberFormat();
    expect(formatNumber(1000)).toBe(fmt.format(1000));
    expect(formatNumber(1234567)).toBe(fmt.format(1234567));
    expect(formatNumber("42")).toBe(fmt.format(42));
    expect(formatNumber(0)).toBe(fmt.format(0));
    // empty string coerces to 0 (not NaN) so it formats rather than dashes
    expect(formatNumber("")).toBe(fmt.format(0));
  });
});

describe("getAccuracyColor", () => {
  it("returns text-foreground for null/non-finite", () => {
    expect(getAccuracyColor(null)).toBe("text-foreground");
    expect(getAccuracyColor(NaN)).toBe("text-foreground");
    expect(getAccuracyColor(Infinity)).toBe("text-foreground");
  });

  it("uses emerald for >=80", () => {
    expect(getAccuracyColor(80)).toBe("text-emerald-600");
    expect(getAccuracyColor(100)).toBe("text-emerald-600");
  });

  it("uses amber for [60, 80)", () => {
    expect(getAccuracyColor(60)).toBe("text-amber-600");
    expect(getAccuracyColor(79.99)).toBe("text-amber-600");
  });

  it("uses rose for <60", () => {
    expect(getAccuracyColor(59)).toBe("text-rose-600");
    expect(getAccuracyColor(0)).toBe("text-rose-600");
  });
});

describe("formatDate", () => {
  const opts = {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  } as const;

  it("returns em-dash for falsy / unparseable values", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate(0)).toBe("—");
    expect(formatDate("")).toBe("—");
    expect(formatDate("garbage")).toBe("—");
  });

  it("formats a Date instance with the pinned option set", () => {
    const d = new Date(2021, 5, 15, 13, 30, 45);
    expect(formatDate(d)).toBe(d.toLocaleString(undefined, opts));
  });

  it("treats numbers below 1e12 as unix seconds", () => {
    const secs = 1623758400; // seconds
    expect(formatDate(secs)).toBe(new Date(secs * 1000).toLocaleString(undefined, opts));
  });

  it("treats numbers >= 1e12 as milliseconds", () => {
    const ms = 1623758400000;
    expect(formatDate(ms)).toBe(new Date(ms).toLocaleString(undefined, opts));
  });

  it("parses ISO date strings", () => {
    const iso = "2021-06-15T12:00:00.000Z";
    expect(formatDate(iso)).toBe(new Date(iso).toLocaleString(undefined, opts));
  });
});

describe("getAccuracyFromMetrics", () => {
  it("returns null when metrics is undefined", () => {
    expect(getAccuracyFromMetrics(undefined, true)).toBeNull();
    expect(getAccuracyFromMetrics(undefined, false)).toBeNull();
  });

  it("returns null when no numeric accuracy field is present", () => {
    expect(getAccuracyFromMetrics({}, true)).toBeNull();
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: "abc" }, true)).toBeNull();
  });

  it("scales a fractional accuracy field to percent", () => {
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: 0.9 }, true)).toBe(90);
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: 0.856 }, true)).toBe(86);
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: "0.9" }, true)).toBe(90);
  });

  it("leaves accuracy fields already >1 as-is", () => {
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: 85 }, true)).toBe(85);
  });

  it("honors the running vs completed field priority order", () => {
    const metrics = {
      valid_mean_token_accuracy: 0.7,
      train_mean_token_accuracy: 0.6,
      full_valid_mean_token_accuracy: 0.9,
      full_valid_loss: 0.1,
    };
    expect(getAccuracyFromMetrics(metrics, true)).toBe(70); // valid first when running
    expect(getAccuracyFromMetrics(metrics, false)).toBe(90); // full_valid first when completed
  });

  it("derives accuracy from a loss field via (1-loss)*100 with clamping", () => {
    expect(getAccuracyFromMetrics({ full_valid_loss: 0.2 }, false)).toBe(80);
    expect(getAccuracyFromMetrics({ full_valid_loss: 1.5 }, false)).toBe(0); // clamped low
    expect(getAccuracyFromMetrics({ full_valid_loss: -0.5 }, false)).toBe(100); // clamped high
    expect(getAccuracyFromMetrics({ full_valid_loss: 0 }, false)).toBe(100);
  });

  it("treats an explicit null field as numeric 0 (Number(null) === 0)", () => {
    expect(getAccuracyFromMetrics({ valid_mean_token_accuracy: null }, true)).toBe(0);
  });
});

describe("buildAccuracySeries", () => {
  it("returns [] for non-array / empty input", () => {
    expect(buildAccuracySeries(undefined)).toEqual([]);
    expect(buildAccuracySeries([])).toEqual([]);
  });

  it("builds a point per event using the accuracy field precedence", () => {
    expect(
      buildAccuracySeries([{ metrics: { train_mean_token_accuracy: 0.8 } }])
    ).toEqual([{ label: "Step 1", value: 80 }]);
    expect(
      buildAccuracySeries([{ metrics: { full_valid_mean_token_accuracy: 0.9, valid_mean_token_accuracy: 0.5 } }])
    ).toEqual([{ label: "Step 1", value: 90 }]);
  });

  it("uses metrics.step when finite and > 0, otherwise a running counter", () => {
    expect(
      buildAccuracySeries([{ metrics: { valid_mean_token_accuracy: 0.6, step: 5 } }])
    ).toEqual([{ label: "Step 5", value: 60 }]);
    // step <= 0 falls back to the counter
    expect(
      buildAccuracySeries([{ metrics: { valid_mean_token_accuracy: 0.6, step: 0 } }])
    ).toEqual([{ label: "Step 1", value: 60 }]);
    expect(
      buildAccuracySeries([{ metrics: { valid_mean_token_accuracy: 0.6, step: -2 } }])
    ).toEqual([{ label: "Step 1", value: 60 }]);
  });

  it("skips events with no usable accuracy without incrementing the counter", () => {
    const result = buildAccuracySeries([
      { metrics: { train_mean_token_accuracy: 0.8 } },
      { metrics: {} },
      {},
      { metrics: { valid_mean_token_accuracy: 0.6, step: 3 } },
    ]);
    expect(result).toEqual([
      { label: "Step 1", value: 80 },
      { label: "Step 3", value: 60 },
    ]);
  });

  it("leaves already-percentage accuracy values as-is", () => {
    expect(
      buildAccuracySeries([{ metrics: { train_mean_token_accuracy: 92 } }])
    ).toEqual([{ label: "Step 1", value: 92 }]);
  });
});
