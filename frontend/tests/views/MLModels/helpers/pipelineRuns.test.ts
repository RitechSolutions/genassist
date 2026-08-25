import { describe, expect, it } from "vitest";
import {
  CRON_PRESETS,
  describeCron,
  formatFileSize,
  formatRunDuration,
  hasActiveRun,
  isRunActive,
  isRunDefaultPipeline,
  isRunFullyPromoted,
  isRunPromoted,
  isValidCron,
  runModelFilePath,
  runStatusMeta,
} from "@/views/MLModels/helpers/pipelineRuns";
import { PipelineRun } from "@/interfaces/ml-model-pipeline.interface";

const run = (status: PipelineRun["status"]): PipelineRun =>
  ({ id: status, model_id: "m", pipeline_config_id: "c", workflow_id: "w", status }) as PipelineRun;

describe("isRunActive", () => {
  it("is true only for pending and running", () => {
    expect(isRunActive("pending")).toBe(true);
    expect(isRunActive("running")).toBe(true);
    expect(isRunActive("completed")).toBe(false);
    expect(isRunActive("failed")).toBe(false);
    expect(isRunActive("cancelled")).toBe(false);
  });

  it("handles missing values", () => {
    expect(isRunActive(null)).toBe(false);
    expect(isRunActive(undefined)).toBe(false);
  });
});

describe("hasActiveRun", () => {
  it("detects a single in-flight run among finished ones", () => {
    expect(hasActiveRun([run("completed"), run("failed"), run("running")])).toBe(true);
    expect(hasActiveRun([run("completed"), run("failed")])).toBe(false);
    expect(hasActiveRun([])).toBe(false);
  });
});

describe("runStatusMeta", () => {
  it("marks only the in-flight statuses as spinning", () => {
    expect(runStatusMeta("running").spinning).toBe(true);
    expect(runStatusMeta("pending").spinning).toBe(true);
    expect(runStatusMeta("completed").spinning).toBe(false);
  });

  it("falls back to the raw status for unknown values", () => {
    expect(runStatusMeta("weird").label).toBe("weird");
    expect(runStatusMeta("weird").spinning).toBe(false);
  });
});

describe("formatRunDuration", () => {
  const start = "2026-01-01T00:00:00.000Z";
  const plus = (seconds: number) =>
    new Date(new Date(start).getTime() + seconds * 1000).toISOString();

  it("keeps sub-minute runs in seconds instead of rounding to 0 min", () => {
    expect(formatRunDuration(start, plus(8))).toBe("8s");
    expect(formatRunDuration(start, plus(59))).toBe("59s");
  });

  it("formats minutes with a seconds remainder", () => {
    expect(formatRunDuration(start, plus(60))).toBe("1m");
    expect(formatRunDuration(start, plus(192))).toBe("3m 12s");
  });

  it("formats hours", () => {
    expect(formatRunDuration(start, plus(3600 + 240))).toBe("1h 4m");
  });

  it("returns null when a timestamp is missing or the range is inverted", () => {
    expect(formatRunDuration(null, plus(10))).toBeNull();
    expect(formatRunDuration(start, undefined)).toBeNull();
    expect(formatRunDuration(plus(10), start)).toBeNull();
  });
});

describe("formatFileSize", () => {
  it("formats bytes through gigabytes", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatFileSize(20 * 1024 * 1024)).toBe("20 MB");
  });

  it("returns null for missing sizes", () => {
    expect(formatFileSize(null)).toBeNull();
    expect(formatFileSize(undefined)).toBeNull();
  });
});

describe("isValidCron", () => {
  it("treats an empty expression as valid (manual runs only)", () => {
    expect(isValidCron("")).toBe(true);
    expect(isValidCron("   ")).toBe(true);
  });

  it("accepts standard 5-field expressions", () => {
    expect(isValidCron("* * * * *")).toBe(true);
    expect(isValidCron("0 0 * * *")).toBe(true);
    expect(isValidCron("*/15 0-6 1,15 * 1-5")).toBe(true);
  });

  it("rejects the wrong number of fields or unsupported syntax", () => {
    expect(isValidCron("* * * *")).toBe(false);
    expect(isValidCron("* * * * * *")).toBe(false);
    expect(isValidCron("every minute")).toBe(false);
  });
});

describe("describeCron", () => {
  it("describes every shipped preset", () => {
    expect(describeCron("0 * * * *")).toBe("Every hour at :00");
    expect(describeCron("0 0 * * *")).toBe("Every day at 00:00");
    expect(describeCron("0 0 * * 1")).toBe("Every Monday at 00:00");
    expect(describeCron("0 0 1 * *")).toBe("Monthly on day 1 at 00:00");
  });

  it("keeps every preset (other than manual) describable", () => {
    for (const preset of CRON_PRESETS.filter((p) => p.value)) {
      expect(describeCron(preset.value)).not.toBeNull();
    }
  });

  it("describes step expressions", () => {
    expect(describeCron("*/15 * * * *")).toBe("Every 15 minutes");
    expect(describeCron("30 */6 * * *")).toBe("Every 6 hours at :30");
  });

  it("pads times and wraps day-of-week 7 back to Sunday", () => {
    expect(describeCron("5 9 * * *")).toBe("Every day at 09:05");
    expect(describeCron("0 0 * * 7")).toBe("Every Sunday at 00:00");
  });

  it("returns null for empty, invalid or non-describable expressions", () => {
    expect(describeCron("")).toBeNull();
    expect(describeCron("nonsense")).toBeNull();
    expect(describeCron("0 0 * *")).toBeNull();
    // Valid cron, but a list of weekdays is beyond the phrases we generate.
    expect(describeCron("0 3 * * 1-5")).toBeNull();
  });
});

describe("runModelFilePath", () => {
  const withOutput = (output: unknown): PipelineRun =>
    ({ ...run("completed"), execution_output: { output } }) as PipelineRun;

  it("reads the model file the workflow produced", () => {
    expect(runModelFilePath(withOutput({ model_file_path: "/train/a.pkl" }))).toBe(
      "/train/a.pkl"
    );
  });

  it("returns null when the run produced no usable path", () => {
    expect(runModelFilePath(run("completed"))).toBeNull();
    expect(runModelFilePath(withOutput(null))).toBeNull();
    expect(runModelFilePath(withOutput("done"))).toBeNull();
    expect(runModelFilePath(withOutput({}))).toBeNull();
    expect(runModelFilePath(withOutput({ model_file_path: "" }))).toBeNull();
    expect(runModelFilePath(withOutput({ model_file_path: 7 }))).toBeNull();
  });
});

describe("isRunPromoted", () => {
  const producing = (path: string): PipelineRun =>
    ({ ...run("completed"), execution_output: { output: { model_file_path: path } } }) as PipelineRun;

  it("is true when the model points at the file this run produced", () => {
    expect(isRunPromoted(producing("/train/a.pkl"), "/train/a.pkl")).toBe(true);
  });

  it("is false for a different or missing file on either side", () => {
    expect(isRunPromoted(producing("/train/a.pkl"), "/train/b.pkl")).toBe(false);
    expect(isRunPromoted(producing("/train/a.pkl"), null)).toBe(false);
    expect(isRunPromoted(run("completed"), "/train/a.pkl")).toBe(false);
  });
});

describe("promotion state", () => {
  const makeRun = (configId: string, producedFile?: string): PipelineRun =>
    ({
      ...run("completed"),
      pipeline_config_id: configId,
      execution_output: producedFile ? { output: { model_file_path: producedFile } } : undefined,
    }) as PipelineRun;

  it("flags runs that used the default pipeline config", () => {
    expect(isRunDefaultPipeline(makeRun("c1"), "c1")).toBe(true);
    expect(isRunDefaultPipeline(makeRun("c1"), "c2")).toBe(false);
    expect(isRunDefaultPipeline(makeRun("c1"), null)).toBe(false);
  });

  it("treats a file-producing run as fully promoted only when both changes landed", () => {
    const withFile = makeRun("c1", "/train/a.pkl");
    expect(isRunFullyPromoted(withFile, "/train/a.pkl", "c1")).toBe(true);
    // Default pipeline, but the model still points at an older file.
    expect(isRunFullyPromoted(withFile, "/train/old.pkl", "c1")).toBe(false);
    // Active file, but the default has since moved to another pipeline.
    expect(isRunFullyPromoted(withFile, "/train/a.pkl", "c2")).toBe(false);
  });

  it("treats a run with no model file as fully promoted once its pipeline is default", () => {
    const noFile = makeRun("c1");
    expect(isRunFullyPromoted(noFile, null, "c1")).toBe(true);
    expect(isRunFullyPromoted(noFile, null, "c2")).toBe(false);
  });
});
