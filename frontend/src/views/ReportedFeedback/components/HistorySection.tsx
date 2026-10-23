import { ChevronRight, History } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/collapsible";

import { IssueStatus } from "@/services/issueStatuses";
import { IssueHistoryEvent } from "@/services/reportedFeedback";
import { formatDateTime } from "@/helpers/utils";
import { formatDateOnly } from "../helpers/triageDraft";
import { useIssueHistory } from "../hooks/useReportedFeedback";
import { SECTION_LABEL_CLASS } from "./SectionLabel";
import { StatusBadge } from "./StatusSelect";

const EMPTY = "—";

function ChangeRow({
  event,
  statuses,
}: {
  event: IssueHistoryEvent;
  statuses: IssueStatus[];
}) {
  const date = (value: string | null) =>
    value ? formatDateOnly(value) : EMPTY;
  const badge = (key: string | null) =>
    key ? <StatusBadge value={key} statuses={statuses} /> : EMPTY;

  switch (event.field) {
    case "status":
      return (
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="sr-only">Status:</span>
          {badge(event.old)}
          <span className="text-muted-foreground">→</span>
          {badge(event.new)}
        </span>
      );
    case "fix_version":
      return `Fix version: ${event.old ?? EMPTY} → ${event.new ?? EMPTY}`;
    case "target_rollout_date":
      return `Target rollout: ${date(event.old)} → ${date(event.new)}`;
    case "comment":
      return "Comment edited";
  }
}

export function HistorySection({
  feedbackId,
  statuses,
}: {
  feedbackId: string;
  statuses: IssueStatus[];
}) {
  const {
    data: events = [],
    isLoading,
    isError,
    isSuccess,
  } = useIssueHistory(feedbackId);

  return (
    <Collapsible asChild>
      <section className="border-t pt-5">
        <CollapsibleTrigger
          className={`group w-full hover:text-foreground data-[state=open]:mb-3 ${SECTION_LABEL_CLASS}`}
        >
          <ChevronRight className="h-3.5 w-3.5 transition-transform group-data-[state=open]:rotate-90" />
          <History className="h-3.5 w-3.5" />
          History
          {isSuccess && (
            <span className="font-normal normal-case tracking-normal">
              · {events.length} {events.length === 1 ? "change" : "changes"}
            </span>
          )}
        </CollapsibleTrigger>
        <CollapsibleContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading history...</p>
          ) : isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">
              Couldn't load the history.
            </p>
          ) : events.length === 0 ? (
            <p className="text-sm text-muted-foreground">No changes yet</p>
          ) : (
            <ol>
              {events.map((event) => (
                <li key={`${event.at}-${event.field}`} className="group flex gap-3">
                  <div aria-hidden="true" className="flex flex-col items-center">
                    <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full border-2 border-muted-foreground/50 bg-background" />
                    <span className="w-px flex-1 bg-border group-last:hidden" />
                  </div>
                  <div className="min-w-0 pb-3 group-last:pb-0">
                    <div className="text-sm break-words">
                      <ChangeRow event={event} statuses={statuses} />
                    </div>
                    <div className="mt-1.5 text-xs text-muted-foreground">
                      {event.by ?? "Unknown user"} · {formatDateTime(event.at)}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CollapsibleContent>
      </section>
    </Collapsible>
  );
}
