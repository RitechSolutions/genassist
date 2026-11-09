import {
  DatetimePart,
  FeatureEngineeringItem,
  FeatureEngineeringStrategy,
  MathFunction,
} from "../../types/nodes";

/**
 * Feature engineering strategies offered for new features in Train Model.
 *
 * "normalize" and "standardize" are retired: they rescale numeric columns
 * into new columns, which is what Train Model's Scaling Method already does
 * for every numeric feature (fit on the training split only) - so they
 * scaled the same values twice and fed the model a duplicate of the column.
 * Features saved with them still load, train and predict (see
 * isRetiredFeatureStrategy), they just can't be picked for new features.
 */
export const FEATURE_ENGINEERING_STRATEGY_OPTIONS: {
  value: FeatureEngineeringStrategy;
  label: string;
}[] = [
  { value: "custom_expression", label: "Custom Expression" },
  { value: "bin_numeric", label: "Bin Numeric" },
  { value: "polynomial", label: "Polynomial" },
  { value: "datetime_features", label: "Date-Time Features" },
  { value: "log_transform", label: "Log Transform" },
  { value: "math_transform", label: "Math Function" },
  { value: "quantile_transform", label: "Quantile Transformer" },
  { value: "power_transform", label: "Power Transformer" },
  { value: "pca", label: "PCA" },
];

/** Strategies that transform numeric sourceColumns into new columns. */
export const COLUMN_TRANSFORM_STRATEGIES: FeatureEngineeringStrategy[] = [
  "log_transform",
  "math_transform",
  "quantile_transform",
  "power_transform",
  "pca",
];

export const MATH_FUNCTION_OPTIONS: { value: MathFunction; label: string }[] = [
  { value: "sin", label: "Sine - sin(x)" },
  { value: "cos", label: "Cosine - cos(x)" },
  { value: "sqrt", label: "Square root - sqrt(x), values 0 or more" },
  { value: "abs", label: "Absolute value - |x|" },
  { value: "square", label: "Square - x²" },
  { value: "cbrt", label: "Cube root - ∛x" },
];

export const DATETIME_PART_OPTIONS: { value: DatetimePart; label: string }[] = [
  { value: "year", label: "Year" },
  { value: "month", label: "Month" },
  { value: "day", label: "Day of month" },
  { value: "day_of_week", label: "Day of week (0 = Monday)" },
  { value: "quarter", label: "Quarter" },
  { value: "hour", label: "Hour (if the values have a time)" },
  { value: "is_weekend", label: "Weekend (1 or 0)" },
];

export const ALL_DATETIME_PARTS: DatetimePart[] = DATETIME_PART_OPTIONS.map((option) => option.value);

/** The parts a Date-Time feature creates: the ticked ones, or all of them when none were saved. */
export const datetimePartsOf = (feature: FeatureEngineeringItem): DatetimePart[] =>
  feature.datetimeParts ?? ALL_DATETIME_PARTS;

/**
 * The columns an earlier feature adds that a later feature can use. Date-Time
 * Features add one column per part (<name>_<part>), never <name> itself.
 */
export const featureOutputColumns = (feature: FeatureEngineeringItem): string[] => {
  const name = feature.newColumnName;
  if (!name) return [];
  if (feature.strategy === "datetime_features") {
    return datetimePartsOf(feature).map((part) => `${name}_${part}`);
  }
  return [name];
};

export const isColumnTransformStrategy = (strategy: FeatureEngineeringStrategy): boolean =>
  COLUMN_TRANSFORM_STRATEGIES.includes(strategy);

/** One-line explanation shown under the strategy select. */
export const STRATEGY_HINTS: Partial<Record<FeatureEngineeringStrategy, string>> = {
  log_transform:
    "log(1 + x) of each column - compresses large values and long right tails. Values must be 0 or more.",
  quantile_transform:
    "Maps each column onto a uniform or normal distribution using quantiles learned from the training rows. Robust to outliers.",
  power_transform:
    "Makes each column more normally distributed. Yeo-Johnson accepts any values; Box-Cox needs values above 0.",
  pca: "Combines the columns into a few uncorrelated components (PCA), learned from the training rows.",
  math_transform:
    "Applies a math function to each column. sin and cos suit cyclic values such as an angle or an hour scaled to 2π.",
  datetime_features:
    "Splits a date/time column into calendar parts (year, month, day, ...). The model is trained on the parts instead of the raw dates, which are still needed as inputs at prediction.",
};

/**
 * Settings a feature gets when it switches to a strategy, so a new
 * feature always starts from a valid, sensible configuration. Existing
 * settings for that strategy are kept.
 */
export const defaultsForStrategy = (
  strategy: FeatureEngineeringStrategy
): Partial<FeatureEngineeringItem> => {
  switch (strategy) {
    case "log_transform":
      return { replaceSourceColumns: false };
    case "math_transform":
      return { mathFunction: "sqrt", replaceSourceColumns: false };
    case "datetime_features":
      return { datetimeParts: ALL_DATETIME_PARTS };
    case "quantile_transform":
      return { quantileOutputDistribution: "uniform", nQuantiles: 1000, replaceSourceColumns: false };
    case "power_transform":
      return { powerMethod: "yeo-johnson", replaceSourceColumns: false };
    case "pca":
      return { pcaComponents: 2, pcaStandardize: true, replaceSourceColumns: true };
    default:
      return {};
  }
};

/** What the feature's output column(s) will be called, for the hint under its settings. */
export const outputColumnsHint = (feature: FeatureEngineeringItem): string => {
  const name = feature.newColumnName || "<name>";
  const sources = feature.sourceColumns || [];
  if (feature.strategy === "pca") return `Creates ${name}_1, ${name}_2, ...`;
  if (feature.strategy === "datetime_features") {
    const parts = datetimePartsOf(feature);
    if (!parts.length) return "Choose at least one part";
    const created = `Creates ${parts.map((part) => `${name}_${part}`).join(", ")}`;
    return parts.includes("hour") ? `${created} (${name}_hour only if the values have a time of day)` : created;
  }
  if (sources.length <= 1) return `Creates ${name}`;
  return `Creates ${sources.map((c) => `${name}_${c}`).join(", ")}`;
};

const RETIRED_FEATURE_STRATEGY_LABELS: Partial<Record<FeatureEngineeringStrategy, string>> = {
  normalize: "Normalize (retired)",
  standardize: "Standardize (retired)",
};

export const isRetiredFeatureStrategy = (strategy: FeatureEngineeringStrategy): boolean =>
  strategy in RETIRED_FEATURE_STRATEGY_LABELS;

/**
 * The options to show for one feature: the current ones, plus the feature's
 * own strategy if it's a retired one - so a saved feature still shows what it
 * is instead of an empty select.
 */
export const strategyOptionsFor = (current: FeatureEngineeringStrategy) =>
  isRetiredFeatureStrategy(current)
    ? [
        ...FEATURE_ENGINEERING_STRATEGY_OPTIONS,
        { value: current, label: RETIRED_FEATURE_STRATEGY_LABELS[current] as string },
      ]
    : FEATURE_ENGINEERING_STRATEGY_OPTIONS;
