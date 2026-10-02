import { summaryLine } from "../../utils/promptEditorResults";
import type { PromptMeasurementState } from "./usePromptMeasurement";

export type MeasurementSection = "evaluate" | "optimize";

export const SECTION_LABEL: Record<MeasurementSection, string> = {
  evaluate: "Evaluate",
  optimize: "Optimize",
};

/** What each half reports while the other is showing, so a hidden run still says so.
 *  Shared with the dialog's live region, the only one outside the tab panels */
export const measurementStatus = (
  measurement: PromptMeasurementState,
): Record<MeasurementSection, string | null> => ({
  evaluate: measurement.evalRun
    ? `${summaryLine(measurement.evalRun.results.summary)}${
        measurement.evalRun.results.provenance.deadline_hit
          ? " · cut by the time budget"
          : ""
      }${measurement.evalStale ? " · inputs changed" : ""}`
    : null,
  optimize: measurement.optimizeResult
    ? `Suggestion ready${measurement.optimizeStale ? " · inputs changed" : ""}${
        measurement.rounds.length > 0
          ? ` · ${measurement.rounds.length} earlier round${
              measurement.rounds.length === 1 ? "" : "s"
            }`
          : ""
      }`
    : null,
});
