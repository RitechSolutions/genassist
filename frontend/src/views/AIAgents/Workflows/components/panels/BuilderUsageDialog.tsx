import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/dialog";
import { getBuilderUsage, type BuilderUsageTotals } from "@/services/workflowBuilder";

const tokens = (n: number) => n.toLocaleString();

/** 950 → "950", 12,585 → "12.6k", 999,999 → "1M", 10,405,169 → "10.4M". One decimal, none when it is zero. */
const compact = (n: number): string => {
  const units: [number, string][] = [
    [1e3, "k"],
    [1e6, "M"],
    [1e9, "B"],
  ];
  if (n < units[0][0]) return n.toLocaleString();
  for (let i = 0; i < units.length; i += 1) {
    const [size, suffix] = units[i];
    const scaled = n / size;
    const rounded = scaled >= 100 ? Math.round(scaled) : Math.round(scaled * 10) / 10;
    // "1000k" reads as the next unit: carry over when rounding reaches it.
    if (rounded >= 1000 && i + 1 < units.length) continue;
    return `${rounded}${suffix}`;
  }
  return n.toLocaleString();
};

/** Dollars with enough precision for small numbers: $0.0139, $26.76, <$0.0001. */
const formatUsd = (value: number): string => {
  if (value === 0) return "$0.00";
  if (value < 0.0001) return "<$0.0001";
  return `$${value < 1 ? value.toFixed(4) : value.toFixed(2)}`;
};

/** A count tile: the compact figure, the exact one on hover. */
const Stat: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div className="min-w-0 rounded-lg bg-muted/40 px-4 py-3" title={tokens(value)}>
    <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
    <div className="mt-1 whitespace-nowrap text-xl font-semibold tabular-nums leading-7 text-foreground">
      {compact(value)}
    </div>
  </div>
);

/** One scope: the cost up front, then the token and call counts, then anything worth knowing about them. */
const Section: React.FC<{ title: string; hint: string; totals: BuilderUsageTotals | null }> = ({
  title,
  hint,
  totals,
}) => (
  <section className="rounded-xl p-5">
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">{hint}</p>
      </div>
      {totals && (
        <div className="text-right">
          <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Total cost</div>
          <div className="text-3xl font-semibold tabular-nums leading-tight text-foreground">
            {formatUsd(totals.cost_usd)}
          </div>
        </div>
      )}
    </div>

    {!totals ? (
      <p className="mt-4 text-sm text-muted-foreground">Nothing spent yet.</p>
    ) : (
      <>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Tokens" value={totals.total_tokens} />
          <Stat label="Input" value={totals.input_tokens} />
          <Stat label="Output" value={totals.output_tokens} />
          <Stat label="Model calls" value={totals.calls} />
        </div>
        {(totals.test_run_calls > 0 || totals.unpriced_calls > 0) && (
          <ul className="mt-4 space-y-1.5 text-sm text-muted-foreground">
            {totals.test_run_calls > 0 && (
              <li>
                <span className="font-medium text-foreground">{tokens(totals.test_run_calls)}</span> of these calls,{" "}
                <span className="font-medium text-foreground">{formatUsd(totals.test_run_cost_usd)}</span>, were test runs
                of your workflow.
              </li>
            )}
            {totals.unpriced_calls > 0 && (
              <li>
                <span className="font-medium text-foreground">{tokens(totals.unpriced_calls)}</span> call
                {totals.unpriced_calls === 1 ? "" : "s"} had no price for their model. Their tokens are counted, their
                cost is not.
              </li>
            )}
          </ul>
        )}
      </>
    )}
  </section>
);

/** Tokens and cost the Workflow Builder spent: this chat, and all of its chats on the tenant. */
export const BuilderUsageDialog: React.FC<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conversationId: string | null;
}> = ({ open, onOpenChange, conversationId }) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["workflowBuilderUsage", conversationId],
    queryFn: () => getBuilderUsage(conversationId),
    enabled: open,
    staleTime: 0,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">Usage</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            What the assistant spent on the models it calls, test runs of your workflow included.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Adding it up…
          </div>
        ) : isError || !data ? (
          <p className="py-10 text-sm text-muted-foreground">Usage is not available right now.</p>
        ) : (
          <div className="space-y-4 pt-1">
            <Section
              title="This chat"
              hint={conversationId ? "Since this conversation started." : "No messages sent yet."}
              totals={data.conversation}
            />
            <Section title="All time" hint="Every chat with the assistant on this workspace." totals={data.all_time} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default BuilderUsageDialog;
