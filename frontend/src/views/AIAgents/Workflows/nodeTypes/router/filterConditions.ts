import type { FilterOperator } from "../../types/nodes";

type OperatorGroup = "text" | "number" | "presence";

interface FilterOperatorOption {
  value: FilterOperator;
  label: string;
  group: OperatorGroup;
}

/** Operators in display order, mirroring engine/conditions.py. */
export const FILTER_OPERATORS: FilterOperatorOption[] = [
  { value: "equal", label: "Equals", group: "text" },
  { value: "not_equal", label: "Does not equal", group: "text" },
  { value: "contains", label: "Contains", group: "text" },
  { value: "not_contain", label: "Does not contain", group: "text" },
  { value: "starts_with", label: "Starts with", group: "text" },
  { value: "not_starts_with", label: "Does not start with", group: "text" },
  { value: "ends_with", label: "Ends with", group: "text" },
  { value: "not_ends_with", label: "Does not end with", group: "text" },
  { value: "regex", label: "Matches regex", group: "text" },
  { value: "greater_than", label: "Greater than", group: "number" },
  { value: "greater_than_or_equal", label: "Greater than or equal", group: "number" },
  { value: "less_than", label: "Less than", group: "number" },
  { value: "less_than_or_equal", label: "Less than or equal", group: "number" },
  { value: "is_empty", label: "Is empty", group: "presence" },
  { value: "is_not_empty", label: "Is not empty", group: "presence" },
];

export const FILTER_OPERATOR_GROUPS: { group: OperatorGroup; label: string }[] = [
  { group: "text", label: "Text" },
  { group: "number", label: "Number" },
  { group: "presence", label: "Presence" },
];

const byValue = new Map(FILTER_OPERATORS.map((o) => [o.value, o]));

export const DEFAULT_FILTER_OPERATOR: FilterOperator = "equal";

export const filterOperatorLabel = (operator: FilterOperator | undefined): string =>
  byValue.get(operator ?? DEFAULT_FILTER_OPERATOR)?.label ?? String(operator);

/** Is empty / Is not empty check the field alone. */
export const filterOperatorNeedsValue = (operator: FilterOperator | undefined): boolean =>
  byValue.get(operator ?? DEFAULT_FILTER_OPERATOR)?.group !== "presence";

/** Case sensitivity only applies to text comparisons. */
export const filterOperatorIsText = (operator: FilterOperator | undefined): boolean =>
  byValue.get(operator ?? DEFAULT_FILTER_OPERATOR)?.group === "text";

/** One-line summary of the condition, e.g. `Greater than 0.8` or `Is empty`. */
export const describeFilterCondition = (
  operator: FilterOperator | undefined,
  value: string | undefined
): string => {
  const label = filterOperatorLabel(operator);
  if (!filterOperatorNeedsValue(operator)) return label;
  const shown = value?.trim();
  return shown ? `${label} ${shown}` : `${label} …`;
};
