import { describe, it, expect } from "vitest";
import type { LocalFineTuneJobEvent } from "@/interfaces/localFineTune.interface";
import {
  buildLossSeriesFromEvents,
  parseTrainSampleCount,
  parseFinalTrainLoss,
} from "@/views/LocalFineTune/utils/trainingEvents";

const ev = (
  message: string,
  data: Record<string, unknown> | null
): LocalFineTuneJobEvent =>
  ({ job_id: "j", level: "info", message, data, timestamp: "t" }) as LocalFineTuneJobEvent;

describe("buildLossSeriesFromEvents", () => {
  it("returns [] when there are no matching events", () => {
    expect(buildLossSeriesFromEvents([])).toEqual([]);
    expect(buildLossSeriesFromEvents([ev("Something else", { loss: 1 })])).toEqual([]);
    expect(buildLossSeriesFromEvents([ev("Training metrics", null)])).toEqual([]);
  });

  it("reads `loss` from Training metrics events", () => {
    expect(buildLossSeriesFromEvents([ev("Training metrics", { loss: 0.5 })])).toEqual([
      { label: "Step 1", value: 0.5 },
    ]);
  });

  it("falls back to `train_loss` when loss is nullish", () => {
    expect(buildLossSeriesFromEvents([ev("Training metrics", { train_loss: 0.3 })])).toEqual([
      { label: "Step 1", value: 0.3 },
    ]);
    expect(
      buildLossSeriesFromEvents([ev("Training metrics", { loss: null, train_loss: 0.2 })])
    ).toEqual([{ label: "Step 1", value: 0.2 }]);
  });

  it("coerces numeric strings and skips non-numeric / missing values", () => {
    expect(buildLossSeriesFromEvents([ev("Training metrics", { loss: "0.4" })])).toEqual([
      { label: "Step 1", value: 0.4 },
    ]);
    expect(buildLossSeriesFromEvents([ev("Training metrics", { loss: "abc" })])).toEqual([]);
    expect(buildLossSeriesFromEvents([ev("Training metrics", {})])).toEqual([]);
  });

  it("numbers steps sequentially, only counting pushed points", () => {
    const result = buildLossSeriesFromEvents([
      ev("Training metrics", { loss: 1.0 }),
      ev("Other", { loss: 5 }),
      ev("Training metrics", null),
      ev("Training metrics", { train_loss: 0.5 }),
    ]);
    expect(result).toEqual([
      { label: "Step 1", value: 1.0 },
      { label: "Step 2", value: 0.5 },
    ]);
  });
});

describe("parseTrainSampleCount", () => {
  it("returns null when no matching event exists", () => {
    expect(parseTrainSampleCount([])).toBeNull();
    expect(parseTrainSampleCount([ev("Other", { train_samples: 10 })])).toBeNull();
    expect(parseTrainSampleCount([ev("Datasets loaded and formatted", null)])).toBeNull();
  });

  it("reads train_samples (number or numeric string)", () => {
    expect(
      parseTrainSampleCount([ev("Datasets loaded and formatted", { train_samples: 100 })])
    ).toBe(100);
    expect(
      parseTrainSampleCount([ev("Datasets loaded and formatted", { train_samples: "250" })])
    ).toBe(250);
  });

  it("returns the last (nearest-to-end) finite value", () => {
    expect(
      parseTrainSampleCount([
        ev("Datasets loaded and formatted", { train_samples: 100 }),
        ev("Datasets loaded and formatted", { train_samples: 200 }),
      ])
    ).toBe(200);
  });

  it("skips non-finite values and keeps scanning backward", () => {
    expect(
      parseTrainSampleCount([
        ev("Datasets loaded and formatted", { train_samples: 50 }),
        ev("Datasets loaded and formatted", { train_samples: "abc" }),
      ])
    ).toBe(50);
    expect(
      parseTrainSampleCount([ev("Datasets loaded and formatted", { other: 1 })])
    ).toBeNull();
  });
});

describe("parseFinalTrainLoss", () => {
  it("returns null when no Training metrics event has train_loss", () => {
    expect(parseFinalTrainLoss([])).toBeNull();
    expect(parseFinalTrainLoss([ev("Training metrics", { loss: 0.5 })])).toBeNull();
    expect(parseFinalTrainLoss([ev("Training metrics", { train_loss: null })])).toBeNull();
  });

  it("returns train_loss (number or numeric string)", () => {
    expect(parseFinalTrainLoss([ev("Training metrics", { train_loss: 0.25 })])).toBe(0.25);
    expect(parseFinalTrainLoss([ev("Training metrics", { train_loss: "0.1" })])).toBe(0.1);
  });

  it("returns the last (nearest-to-end) finite train_loss", () => {
    expect(
      parseFinalTrainLoss([
        ev("Training metrics", { train_loss: 0.9 }),
        ev("Training metrics", { train_loss: 0.1 }),
      ])
    ).toBe(0.1);
  });

  it("skips non-finite train_loss and keeps scanning backward", () => {
    expect(
      parseFinalTrainLoss([
        ev("Training metrics", { train_loss: 0.7 }),
        ev("Training metrics", { train_loss: "abc" }),
      ])
    ).toBe(0.7);
  });
});
