import { Skeleton } from "@/components/skeleton";
import { formatUsd } from "@/helpers/formatCurrency";
import type { LlmUsageBreakdownItem } from "@/interfaces/llmUsage.interface";

interface LlmUsageEvaluationMethodsProps {
  items: LlmUsageBreakdownItem[];
  loading?: boolean;
  error?: boolean;
}

const HEAD_CLASS = "py-1.5 text-right font-medium";

/** Inline split of the Evaluations row into its judge methods. */
export function LlmUsageEvaluationMethods({ items, loading, error }: LlmUsageEvaluationMethodsProps) {
  const total = items.reduce((sum, i) => sum + i.cost_usd, 0);

  return (
    <div className="border-l-2 border-primary/40 py-3 pl-6 pr-4">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Evaluation methods</p>
      {loading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      ) : error ? (
        <p className="py-1 text-xs text-destructive">Failed to load evaluation breakdown.</p>
      ) : items.length === 0 ? (
        <p className="py-1 text-xs text-muted-foreground">No evaluation LLM spend in this period.</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="py-1.5 text-left font-medium">Method</th>
              <th className={HEAD_CLASS}>Calls</th>
              <th className={HEAD_CLASS}>Tokens</th>
              <th className={HEAD_CLASS}>Cost</th>
              <th className={HEAD_CLASS}>Share of Evaluations</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.key} className="border-t border-border/60">
                <td className="py-1.5 pr-3 font-medium text-foreground">{item.label}</td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">{item.calls.toLocaleString()}</td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                  {item.total_tokens.toLocaleString()}
                </td>
                <td className="py-1.5 text-right tabular-nums font-semibold text-foreground">
                  {formatUsd(item.cost_usd)}
                  {item.cost_is_partial && <span className="ml-1 font-normal text-amber-500">partial</span>}
                </td>
                <td className="py-1.5 text-right tabular-nums text-muted-foreground">
                  {total > 0 ? `${((item.cost_usd / total) * 100).toFixed(1)}%` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
