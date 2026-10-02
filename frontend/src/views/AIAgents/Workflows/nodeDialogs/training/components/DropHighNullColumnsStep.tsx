import React from "react";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import { DropHighNullColumnsStepConfig } from "../preprocessingConfig";
import { CSVAnalysisResult } from "@/services/mlModels";

interface DropHighNullColumnsStepProps {
  config: DropHighNullColumnsStepConfig | undefined;
  onChange: (config: DropHighNullColumnsStepConfig) => void;
  analysisResult?: CSVAnalysisResult | null;
}

export const DropHighNullColumnsStep: React.FC<DropHighNullColumnsStepProps> = ({
  config,
  onChange,
  analysisResult,
}) => {
  const thresholdPercent = config?.thresholdPercent ?? 80;

  const affectedColumns =
    analysisResult?.columns_info.filter((col) => {
      const missingPercentage =
        analysisResult.row_count > 0
          ? (col.missing_count / analysisResult.row_count) * 100
          : 0;
      return missingPercentage > thresholdPercent;
    }) || [];

  return (
    <div className="space-y-4">
      <div className="space-y-0.5">
        <Label>Remove High-Null Columns</Label>
        <p className="text-xs text-muted-foreground">
          Drops any column where more than the threshold percentage of its
          values are missing.
        </p>
      </div>

      <div className="space-y-2">
        <Label className="text-sm">Missing-value threshold (%)</Label>
        <RichInput
          type="number"
          min={0}
          max={100}
          value={thresholdPercent}
          onChange={(e) => {
            const value = parseFloat(e.target.value);
            onChange({ thresholdPercent: isNaN(value) ? 80 : value });
          }}
          className="w-[140px]"
        />
      </div>

      {analysisResult && (
        <p className="text-xs text-muted-foreground">
          {affectedColumns.length > 0
            ? `${affectedColumns.length} column(s) currently exceed this threshold and would be removed: ${affectedColumns
                .map((c) => c.name)
                .join(", ")}`
            : "No columns currently exceed this threshold."}
        </p>
      )}
    </div>
  );
};
