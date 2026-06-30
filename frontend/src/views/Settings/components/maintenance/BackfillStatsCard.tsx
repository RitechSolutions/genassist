import { useState } from "react";
import { DatabaseBackup } from "lucide-react";
import toast from "react-hot-toast";
import { useMutation } from "@tanstack/react-query";
import type { DateRange } from "react-day-picker";
import { Card } from "@/components/card";
import { Button } from "@/components/button";
import { DateRangePicker } from "@/components/date-range-picker";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/alert-dialog";
import { toExpandedUTCDateRange } from "@/helpers/analyticsParams";
import { triggerAnalyticsBackfill } from "@/services/analyticsReports";

/**
 * Maintenance job: re-aggregates agent/node daily stats over an optional date
 * window so columns added after rows were first aggregated (e.g.
 * unique_conversations, which made Containment Rate read 100%) get repopulated.
 * Heavy at scale — runs asynchronously on the worker and is confirmed first.
 */
export function BackfillStatsCard() {
  const [range, setRange] = useState<DateRange | undefined>(undefined);
  const [open, setOpen] = useState(false);

  const { from_date, to_date } = toExpandedUTCDateRange(range);

  const mutation = useMutation({
    mutationFn: async () => {
      const result = await triggerAnalyticsBackfill({ from_date, to_date });
      if (!result) throw new Error("No response from server.");
      return result;
    },
    onSuccess: () => {
      toast.success(
        "Backfill queued. Stats will refresh once the worker finishes — reload analytics in a few minutes.",
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to queue backfill.";
      toast.error(msg);
    },
    // Close the confirm dialog once the request settles (success or error);
    // feedback is delivered via toast.
    onSettled: () => setOpen(false),
  });

  const rangeLabel =
    from_date && to_date ? `${from_date} → ${to_date}` : "the entire history";

  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-md bg-zinc-100 p-2 text-zinc-600">
          <DatabaseBackup className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-medium">Recompute analytics stats</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Re-aggregates agent and node daily stats for all tenants, repopulating
            metrics that can otherwise read incorrectly (e.g. a containment rate stuck
            at 100%). Runs in the background and is safe to re-run. At large scale,
            pick a narrow window (e.g. one month) and run it in slices.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <DateRangePicker
              value={range}
              onChange={setRange}
              placeholder="All time (optional range)"
            />

            <AlertDialog open={open} onOpenChange={setOpen}>
              <AlertDialogTrigger asChild>
                <Button variant="outline" className="gap-1.5" disabled={mutation.isPending}>
                  <DatabaseBackup className="h-4 w-4" />
                  {mutation.isPending ? "Queuing…" : "Run backfill"}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Recompute analytics for {rangeLabel}?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This re-aggregates agent and node daily stats for{" "}
                    <span className="font-medium">all tenants</span> over {rangeLabel}.
                    It runs in the background and is safe to re-run. At large scale,
                    prefer a narrow date range (e.g. one month) per run.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel disabled={mutation.isPending}>Cancel</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={(e) => {
                      e.preventDefault();
                      mutation.mutate();
                    }}
                    disabled={mutation.isPending}
                  >
                    {mutation.isPending ? "Queuing…" : "Recompute"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </div>
    </Card>
  );
}
