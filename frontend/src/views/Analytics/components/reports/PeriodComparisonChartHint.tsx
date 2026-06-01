interface PeriodComparisonChartHintProps {
  comparedWithLabel?: string | null;
}

export function PeriodComparisonChartHint({ comparedWithLabel }: PeriodComparisonChartHintProps) {
  if (!comparedWithLabel) return null;

  return (
    <p className="mb-3 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="inline-block h-0 w-4 border-t-2 border-zinc-700" aria-hidden />
        Selected period
      </span>
      <span className="mx-2 text-muted-foreground/40">·</span>
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block h-0 w-4 border-t-2 border-dashed border-zinc-500"
          aria-hidden
        />
        {comparedWithLabel}
      </span>
      <span className="ml-2 text-muted-foreground/60">— aligned by day index</span>
    </p>
  );
}
