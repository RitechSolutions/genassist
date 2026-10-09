import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { useNavigate } from "react-router-dom";
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
  toInclusiveDateParams,
} from "@/helpers/dateRange";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import type { IssueCategory } from "@/services/issueStatuses";
import { CATEGORY_META } from "@/views/ReportedFeedback/constants";
import { useFeedbackSummary } from "@/views/ReportedFeedback/hooks/useReportedFeedback";

interface CountRowProps {
  icon: LucideIcon;
  title: string;
  description: string;
  count: number;
  bgColor: string;
  iconColor: string;
}

const CATEGORY_ROWS: Array<Omit<CountRowProps, "title" | "count"> & { category: IssueCategory }> = [
  {
    category: "todo",
    icon: CircleDashed,
    description: "Not started yet",
    bgColor: "bg-zinc-100 dark:bg-zinc-500/15",
    iconColor: "text-zinc-600 dark:text-zinc-400",
  },
  {
    category: "in_progress",
    icon: CircleDotDashed,
    description: "Being worked on",
    bgColor: "bg-blue-100 dark:bg-blue-500/15",
    iconColor: "text-blue-700 dark:text-blue-400",
  },
  {
    category: "done",
    icon: CircleCheckBig,
    description: "Resolved or closed",
    bgColor: "bg-green-100 dark:bg-green-500/15",
    iconColor: "text-green-700 dark:text-green-400",
  },
];

const formatPeriod = (range: DateRange | undefined): string => {
  if (!range?.from) return range?.to ? `Until ${format(range.to, "MMM d, yyyy")}` : "All time";
  if (!range.to) return `Since ${format(range.from, "MMM d, yyyy")}`;
  return `${format(range.from, "MMM d")} – ${format(range.to, "MMM d, yyyy")}`;
};

function CountRow({ icon: Icon, title, description, count, bgColor, iconColor }: CountRowProps) {
  return (
    <div className="flex gap-3 items-center p-2 rounded-lg">
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
    </div>
  );
}

/** Reported feedback counts per status category, over the Dashboard date range */
export function ReportedFeedbackCard({ className }: { className?: string }) {
  const navigate = useNavigate();
  const [dateRange] = usePersistedDateRange(dashboardDefaultDateRange());
  const { total, totals, isLoading, isError } = useFeedbackSummary(
    toInclusiveDateParams(dateRange),
  );

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
            {CATEGORY_ROWS.map(({ category, ...row }) => (
              <CountRow
                key={category}
                {...row}
                title={CATEGORY_META[category].label}
                count={totals[category]}
              />
            ))}
          </>
        )}
      </div>
    </Card>
  );
}
