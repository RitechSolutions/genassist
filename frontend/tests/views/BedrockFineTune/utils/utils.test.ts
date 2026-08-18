import { describe, it, expect } from "vitest";
import type { BedrockFineTuneJob } from "@/interfaces/bedrockFineTune.interface";
import {
  bedrockInProgressStatuses,
  bedrockTerminalStatuses,
  bedrockActiveDeploymentStatuses,
  formatBedrockStatusLabel,
  isBedrockJobInProgress,
  isBedrockJobCompleted,
} from "@/views/BedrockFineTune/utils/utils";

const job = (status?: unknown): BedrockFineTuneJob =>
  ({ id: "j", base_model_id: "m", status }) as BedrockFineTuneJob;

describe("bedrock status sets", () => {
  it("in-progress set", () => {
    expect([...bedrockInProgressStatuses].sort()).toEqual(["inprogress", "stopping"]);
  });
  it("terminal set", () => {
    expect([...bedrockTerminalStatuses].sort()).toEqual(["completed", "failed", "stopped"]);
  });
  it("active deployment set", () => {
    expect([...bedrockActiveDeploymentStatuses].sort()).toEqual(["active", "creating"]);
  });
});

describe("formatBedrockStatusLabel", () => {
  it("returns 'Unknown' for empty input", () => {
    expect(formatBedrockStatusLabel("")).toBe("Unknown");
  });

  it("splits PascalCase and title-cases", () => {
    expect(formatBedrockStatusLabel("InProgress")).toBe("In Progress");
  });

  it("replaces underscores with spaces and title-cases", () => {
    expect(formatBedrockStatusLabel("in_progress")).toBe("In Progress");
  });

  it("title-cases a lowercase single token (no spacing inserted)", () => {
    expect(formatBedrockStatusLabel("inprogress")).toBe("Inprogress");
    expect(formatBedrockStatusLabel("failed")).toBe("Failed");
    expect(formatBedrockStatusLabel("completed")).toBe("Completed");
  });

  it("handles mixed camelCase + underscore", () => {
    expect(formatBedrockStatusLabel("someStatus_here")).toBe("Some Status Here");
  });
});

describe("isBedrockJobInProgress", () => {
  it("is true for inprogress/stopping (case-insensitive)", () => {
    expect(isBedrockJobInProgress(job("InProgress"))).toBe(true);
    expect(isBedrockJobInProgress(job("inprogress"))).toBe(true);
    expect(isBedrockJobInProgress(job("Stopping"))).toBe(true);
  });

  it("is false for terminal statuses", () => {
    expect(isBedrockJobInProgress(job("Completed"))).toBe(false);
    expect(isBedrockJobInProgress(job("Failed"))).toBe(false);
  });

  it("is false when status is missing/nullish", () => {
    expect(isBedrockJobInProgress(job(undefined))).toBe(false);
    expect(isBedrockJobInProgress(job(null))).toBe(false);
    expect(isBedrockJobInProgress(job(""))).toBe(false);
  });
});

describe("isBedrockJobCompleted", () => {
  it("is true only for 'completed' (case-insensitive)", () => {
    expect(isBedrockJobCompleted(job("Completed"))).toBe(true);
    expect(isBedrockJobCompleted(job("completed"))).toBe(true);
  });

  it("is false for any other or missing status", () => {
    expect(isBedrockJobCompleted(job("InProgress"))).toBe(false);
    expect(isBedrockJobCompleted(job("Failed"))).toBe(false);
    expect(isBedrockJobCompleted(job(undefined))).toBe(false);
  });
});
