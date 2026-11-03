import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { Link, useNavigate } from "react-router-dom";
import {
  CircleCheckBig,
  CircleDashed,
  CircleDotDashed,
  Flag,
  type LucideIcon,
} from "lucide-react";
import { Card } from "@/components/card";
import { PageListSkeleton } from "@/components/skeletons";
import { cn } from "@/helpers/utils";
import {
  dashboardDefaultDateRange,
  formatDateRangeLabel,
  toInclusiveDateParams,
} from "@/helpers/dateRange";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { ISSUE_CATEGORIES, type IssueCategory } from "@/services/issueStatuses";
import { CATEGORY_LABELS } from "@/views/ReportedFeedback/constants";
import { listableStatuses } from "@/views/ReportedFeedback/helpers/issueStatuses";
import { useIssueStatuses } from "@/views/ReportedFeedback/hooks/useIssueStatuses";
import { useFeedbackSummary } from "@/views/ReportedFeedback/hooks/useReportedFeedback";

interface CountRowProps {
  icon: LucideIcon;
  title: string;
  description: string;
  count: number;
  bgColor: string;
  iconColor: string;
  to?: string;
  state?: { dateRange?: DateRange };
}

const CATEGORY_ROWS: Record<IssueCategory, Omit<CountRowProps, "title" | "count">> = {
  todo: {
    icon: CircleDashed,
    description: "Not started yet",
    bgColor: "bg-zinc-100 dark:bg-zinc-500/15",
    iconColor: "text-zinc-600 dark:text-zinc-400",
  },
  in_progress: {
    icon: CircleDotDashed,
    description: "Being worked on",
    bgColor: "bg-blue-100 dark:bg-blue-500/15",
    iconColor: "text-blue-700 dark:text-blue-400",
  },
  done: {
    icon: CircleCheckBig,
    description: "Resolved or closed",
    bgColor: "bg-green-100 dark:bg-green-500/15",
    iconColor: "text-green-700 dark:text-green-400",
  },
};

const formatPeriod = (range: DateRange | undefined): string => {
  if (!range?.from) return range?.to ? `Until ${format(range.to, "MMM d, yyyy")}` : "All time";
  if (!range.to) return `Since ${format(range.from, "MMM d, yyyy")}`;
  return formatDateRangeLabel(range.from, range.to);
};

function CountRow({ icon: Icon, title, description, count, bgColor, iconColor, to, state }: CountRowProps) {
  const rowClass = "flex gap-3 items-center p-2 rounded-lg";
  const content = (
    <>
      <div className={cn(bgColor, "flex items-center p-2 rounded-lg shrink-0")}>
        <Icon className={cn("w-5 h-5", iconColor)} />
      </div>
      <div className="flex flex-col flex-1 min-w-0">
        <p className="text-sm font-semibold text-accent-foreground truncate">{title}</p>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
      <span className="text-sm font-semibold text-foreground tabular-nums">
        {count.toLocaleString()}
      </span>
    </>
  );
  if (!to) return <div className={rowClass}>{content}</div>;
  return (
    <Link
      to={to}
      state={state}
      className={cn(
        rowClass,
        "hover:bg-muted/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {content}
    </Link>
  );
}

/** Reported feedback counts per status category, over the Dashboard date range */
export function ReportedFeedbackCard({ className }: { className?: string }) {
  const navigate = useNavigate();
  const [dateRange] = usePersistedDateRange(dashboardDefaultDateRange());
  const { data: statuses = [] } = useIssueStatuses();
  const { total, totals, byStatus, isLoading, isError } = useFeedbackSummary(
    toInclusiveDateParams(dateRange),
  );
  const listedStatuses = listableStatuses(statuses, byStatus);
  const categoryLink = (category: IssueCategory) => {
    const keys = listedStatuses
      .filter((status) => status.category === category)
      .map((status) => status.key);
    if (keys.length === 0) return undefined;
    return `/reported-feedback?${new URLSearchParams(keys.map((key) => ["status", key])).toString()}`;
  };

  return (
    <Card
      className={cn(
        "bg-card dark:bg-zinc-900 border border-border rounded-xl overflow-hidden shadow-sm animate-fade-up",
        className,
      )}
    >
      <div className="bg-card dark:bg-zinc-900 flex items-center justify-between p-6">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-foreground">Reported Feedback</h3>
        </div>
        <button
          onClick={() => navigate("/reported-feedback")}
          className="text-sm font-medium text-foreground hover:underline"
        >
          View all
        </button>
      </div>

      <div className="flex flex-col gap-2 px-4 pb-4">
        {isLoading ? (
          <PageListSkeleton variant="dashboard-integration" rows={4} bordered={false} />
        ) : isError ? (
          <div className="text-center py-8 text-muted-foreground">
            <p>Couldn't load the status counts.</p>
          </div>
        ) : (
          <>
            <CountRow
              icon={Flag}
              title="Total reported"
              description={formatPeriod(dateRange)}
              count={total}
              bgColor="bg-amber-100 dark:bg-amber-500/15"
              iconColor="text-amber-700 dark:text-amber-400"
            />
            {ISSUE_CATEGORIES.map((category) => (
              <CountRow
                key={category}
                {...CATEGORY_ROWS[category]}
                title={CATEGORY_LABELS[category]}
                count={totals[category]}
                to={categoryLink(category)}
                state={{ dateRange }}
              />
            ))}
          </>
        )}
      </div>
    </Card>
  );
}
