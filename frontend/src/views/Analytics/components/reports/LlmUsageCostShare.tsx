interface LlmUsageCostShareProps {
  costUsd: number;
  /** Always the overall Usage by Type cost, so parent and subordinate rows share one denominator */
  totalCostUsd: number;
}

/** Share rail used by both breakdown rows and their subordinate rows */
export function LlmUsageCostShare({ costUsd, totalCostUsd }: LlmUsageCostShareProps) {
  const percentage =
    Number.isFinite(costUsd) && Number.isFinite(totalCostUsd) && totalCostUsd > 0 ? (costUsd / totalCostUsd) * 100 : 0;
  // Rail is clamped so a parent/subordinate snapshot mismatch cannot overflow the track
  const fillPercentage = Math.min(100, Math.max(0, percentage));

  return (
    <div className="flex items-center gap-2 tabular-nums">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-muted">
        <span className="block h-full rounded-full bg-primary" style={{ width: `${fillPercentage}%` }} />
      </span>
      {percentage.toFixed(1)}%
    </div>
  );
}
