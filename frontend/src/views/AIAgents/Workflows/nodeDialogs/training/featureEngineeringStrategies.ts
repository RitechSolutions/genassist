import { FeatureEngineeringItem, FeatureEngineeringStrategy } from "../../types/nodes";

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
  { value: "log_transform", label: "Log Transform" },
  { value: "quantile_transform", label: "Quantile Transformer" },
  { value: "power_transform", label: "Power Transformer" },
  { value: "pca", label: "PCA" },
];

/** Strategies that transform numeric sourceColumns into new columns. */
export const COLUMN_TRANSFORM_STRATEGIES: FeatureEngineeringStrategy[] = [
  "log_transform",
  "quantile_transform",
  "power_transform",
  "pca",
];

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
