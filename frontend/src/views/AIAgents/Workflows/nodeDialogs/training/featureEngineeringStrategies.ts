import { FeatureEngineeringStrategy } from "../../types/nodes";

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
];

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
