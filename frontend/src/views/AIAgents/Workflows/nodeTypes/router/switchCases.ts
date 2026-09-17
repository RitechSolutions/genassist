import type {
  NodeHandler,
  SwitchCase,
  SwitchMatchMode,
} from "../../types/nodes";

export const SWITCH_DEFAULT_HANDLE_ID = "output_default";

export const SWITCH_MATCH_MODE_LABELS: Record<SwitchMatchMode, string> = {
  equal: "Equals",
  contains: "Contains",
  starts_with: "Starts with",
  ends_with: "Ends with",
  regex: "Matches regex",
};

export const DEFAULT_SWITCH_CASES: SwitchCase[] = [
  { id: "case_1", label: "Case 1", value: "" },
  { id: "case_2", label: "Case 2", value: "" },
  { id: "case_3", label: "Case 3", value: "" },
];

export const switchCaseHandleId = (caseId: string) => `output_${caseId}`;

/** Stored as boolean; string "true"/"false" may appear from persisted or generated JSON. */
export const isSwitchSmartMode = (
  value: boolean | string | undefined | null
): boolean =>
  value === true ||
  (typeof value === "string" && value.trim().toLowerCase() === "true");

/** Next free `case_<n>` id, so ids stay stable when cases are renamed or reordered. */
export const nextSwitchCaseId = (cases: SwitchCase[]): string => {
  const max = cases.reduce((acc, c) => {
    const n = Number(c.id.replace(/^case_/, ""));
    return Number.isFinite(n) ? Math.max(acc, n) : acc;
  }, 0);
  return `case_${max + 1}`;
};

/**
 * Handles for a Switch node: one input, one output per case (in case order, so
 * the handles run top-to-bottom in the same order as the case list), then the
 * default output last.
 */
export const buildSwitchHandlers = (cases: SwitchCase[]): NodeHandler[] => [
  { id: "input", type: "target", compatibility: "any", position: "left" },
  ...cases.map<NodeHandler>((c, index) => ({
    id: switchCaseHandleId(c.id),
    type: "source",
    compatibility: "any",
    position: "right",
    label: c.label || `Case ${index + 1}`,
  })),
  {
    id: SWITCH_DEFAULT_HANDLE_ID,
    type: "source",
    compatibility: "any",
    position: "right",
    label: "Default",
  },
];
