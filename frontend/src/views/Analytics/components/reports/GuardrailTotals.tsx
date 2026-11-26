import { Card, CardContent, CardHeader, CardTitle } from "@/components/card";
import { TruncatedText } from "@/components/TruncatedText";
import { cn } from "@/helpers/utils";
import type { GuardrailTotalsItem } from "@/interfaces/analyticsReports.interface";
import { analyticsFadeUpClass } from "../../constants/animations";
import { segmentWidth, summarizeGuardrailTotals } from "../../helpers/guardrailTotals";

const OUTCOMES = [
  {
    key: "blocked",
    label: "Blocked",
    bar: "bg-rose-400 dark:bg-rose-500/80",
    text: "text-rose-700 dark:text-rose-400",
  },
  {
    key: "flagged",
    label: "Flagged",
    bar: "bg-amber-400 dark:bg-amber-500/80",
    text: "text-amber-700 dark:text-amber-400",
  },
] as const;

const ROW_GRID = "sm:grid-cols-[11rem_minmax(0,1fr)_4.5rem_4.5rem]";

export function GuardrailTotals({ items }: { items: GuardrailTotalsItem[] }) {
  const summary = summarizeGuardrailTotals(items);
  const { rows, busiest, failed } = summary;

  return (
    <Card className={cn("bg-card dark:bg-zinc-900 shadow-sm", analyticsFadeUpClass)}>
      <CardHeader className="pb-0">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground">Guardrails</CardTitle>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {OUTCOMES.map((outcome) => (
              <span key={outcome.key} className="flex items-center gap-1.5">
                <span aria-hidden className={cn("h-2.5 w-2.5 rounded-full", outcome.bar)} />
                {outcome.label}
                <span className="font-semibold tabular-nums text-foreground">
                  {summary[outcome.key].toLocaleString()}
                </span>
              </span>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing blocked or flagged in this range</p>
        ) : (
          <>
            <div aria-hidden className={cn("hidden sm:grid gap-x-4 mb-2 text-xs text-muted-foreground", ROW_GRID)}>
              <span>Check</span>
              <span />
              {OUTCOMES.map((outcome) => (
                <span key={outcome.key} className="text-right">
                  {outcome.label}
                </span>
              ))}
            </div>
            <ul aria-label="Guardrail checks" className="space-y-3">
              {rows.map((row) => (
                <li
                  key={row.check_type}
                  className={cn(
                    "grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-4 gap-y-1.5 text-sm",
                    ROW_GRID
                  )}
                >
                  <TruncatedText className="font-medium text-foreground">{row.label}</TruncatedText>
                  <div
                    aria-hidden
                    className="flex h-2 w-full overflow-hidden rounded-full bg-muted order-last col-span-3 sm:order-none sm:col-span-1"
                  >
                    {OUTCOMES.map((outcome) => (
                      <div
                        key={outcome.key}
                        className={outcome.bar}
                        style={{ width: segmentWidth(row[outcome.key], busiest) }}
                      />
                    ))}
                  </div>
                  {OUTCOMES.map((outcome) => (
                    <span
                      key={outcome.key}
                      className={cn(
                        "text-right tabular-nums",
                        row[outcome.key] > 0 ? outcome.text : "text-muted-foreground/60"
                      )}
                    >
                      <span className="sr-only">{outcome.label} </span>
                      {row[outcome.key].toLocaleString()}
                    </span>
                  ))}
                </li>
              ))}
            </ul>
          </>
        )}
        {failed > 0 && (
          <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
            Checks failed {failed.toLocaleString()} {failed === 1 ? "time" : "times"}, and those messages went through
            unchecked.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
