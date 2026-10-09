import { useEffect, useState } from "react";
import { MessageSquareDot, Settings } from "lucide-react";
import type { DateRange } from "react-day-picker";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";

import { PageLayout } from "@/components/PageLayout";
import { buttonVariants } from "@/components/button";
import { DataTable, Column } from "@/components/ui/data-table";
import { ListEmptyState } from "@/components/ListEmptyState";
import { PaginationBar } from "@/components/PaginationBar";
import { FilterMenu, type FilterMenuGroup } from "@/components/FilterMenu";
import { TruncatedText } from "@/components/TruncatedText";
import { DateRangePicker } from "@/components/date-range-picker";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { useTopicOptions } from "@/hooks/useTopicOptions";
import { usePermissions } from "@/context/PermissionContext";
import { getWorkflowsMinimal } from "@/services/workflows";
import type { IssueCategory } from "@/services/issueStatuses";
import { extractErrorMessage } from "@/helpers/apiError";
import { subtopicsFor, withCurrentOption } from "@/helpers/topicOptions";
import { toInclusiveDateParams } from "@/helpers/dateRange";

import {
  EMPTY_SUMMARY,
  FeedbackStatus,
  fetchReportedFeedbackSummary,
  IssuePatch,
  ReportedFeedbackItem,
  updateFeedbackIssue,
} from "@/services/reportedFeedback";
import { StatsOverviewCard } from "@/views/Analytics/components/StatsOverviewCard";
import { useReportedFeedback } from "../hooks/useReportedFeedback";
import { useIssueStatuses } from "../hooks/useIssueStatuses";
import { ReportedFeedbackDialog } from "../components/ReportedFeedbackDialog";
import { StatusBadge, StatusSelect } from "../components/StatusSelect";
import { CATEGORY_META } from "../constants";
import {
  categoryTotals,
  statusMeta,
  withCurrentStatus,
} from "../helpers/issueStatuses";
import {
  applyIssuePatch,
  IssueFields,
  pickPatchedFields,
} from "../helpers/issuePatch";
import { topicLabel } from "../helpers/triageDraft";
import { formatDateTime } from "@/helpers/utils";

const PAGE_SIZE = 20;

export default function ReportedFeedback() {
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canTriage =
    permissions.includes("*") || permissions.includes("update:conversation");
  const canManageStatuses =
    permissions.includes("*") || permissions.includes("write:app_settings");
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "all">("all");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [subtopicFilter, setSubtopicFilter] = useState<string>("all");
  const [workflowFilter, setWorkflowFilter] = useState<string>("all");
  // Shared global range (same component/store as the dashboard).
  const [dateRange, setDateRange] = usePersistedDateRange(undefined);

  const { data: workflowsData } = useQuery({
    queryKey: ["workflows-minimal"],
    queryFn: getWorkflowsMinimal,
  });
  const workflows = workflowsData ?? [];

  const {
    data: statuses = [],
    isLoading: statusesLoading,
    isError: statusesError,
  } = useIssueStatuses();
  const { data: topicOptions = [] } = useTopicOptions();
  const topicChoices = withCurrentOption(topicOptions, topicFilter);
  const subtopicChoices = subtopicsFor(
    topicChoices,
    topicFilter === "all" ? null : topicFilter,
    subtopicFilter,
  );

  // Server-side time filter on the reported time (when the comment was added).
  const filters = {
    workflow_id: workflowFilter !== "all" ? workflowFilter : undefined,
    ...toInclusiveDateParams(dateRange),
    topic: topicFilter !== "all" ? topicFilter : undefined,
    subtopic: subtopicFilter !== "all" ? subtopicFilter : undefined,
  };

  const { data, total, loading, error } = useReportedFeedback({
    skip: (currentPage - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter,
    ...filters,
  });

  const {
    data: summary = EMPTY_SUMMARY,
    isLoading: summaryLoading,
    isError: summaryError,
  } = useQuery({
    queryKey: ["reported-feedback", "summary", filters],
    queryFn: () => fetchReportedFeedbackSummary(filters),
    placeholderData: keepPreviousData,
  });

  const categoryCounts = categoryTotals(summary, statuses);
  const statusMetrics = [
    {
      label: "Total reported",
      value: summary.total.toLocaleString(),
      change: 0,
      changeType: "neutral" as const,
    },
    ...(Object.keys(CATEGORY_META) as IssueCategory[]).map((category) => ({
      label: CATEGORY_META[category].label,
      value: categoryCounts[category].toLocaleString(),
      change: 0,
      changeType: "neutral" as const,
    })),
  ];

  // Local mirror so status changes update the row instantly (optimistic).
  const [rows, setRows] = useState<ReportedFeedbackItem[]>([]);
  useEffect(() => setRows(data), [data]);

  const [selectedIssue, setSelectedIssue] = useState<ReportedFeedbackItem | null>(
    null,
  );
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const openDialog = (issue: ReportedFeedbackItem) => {
    setSelectedIssue(issue);
    setIsDialogOpen(true);
  };

  // The dialog embeds the conversation itself; these are the "see everything" escape
  // hatches. They open in a new tab so the reviewer keeps their filters, page and
  // scroll position — and the open dialog — on this one.
  const openInNewTab = (path: string) => {
    window.open(`${window.location.origin}${path}`, "_blank", "noopener,noreferrer");
  };

  const openConversation = (conversationId: string) => {
    if (!conversationId) return;
    openInNewTab(`/transcripts?conversation=${encodeURIComponent(conversationId)}`);
  };

  const openWorkflow = (agentId: string | null) => {
    if (!agentId) return;
    openInNewTab(`/ai-agents/workflow/${agentId}`);
  };

  const applyFields = (feedbackId: string, fields: IssueFields) => {
    setRows((rs) => applyIssuePatch(rs, feedbackId, fields));
    setSelectedIssue((current) =>
      current && current.feedback_id === feedbackId
        ? { ...current, ...fields }
        : current,
    );
  };

  const handleIssuePatch = async (
    issue: ReportedFeedbackItem,
    patch: IssuePatch,
    errorFallback = "Failed to update feedback",
  ): Promise<ReportedFeedbackItem | null> => {
    const rollback = pickPatchedFields(issue, patch);
    applyFields(issue.feedback_id, patch);
    try {
      const saved = await updateFeedbackIssue(issue.feedback_id, patch);
      const reconciled = pickPatchedFields(saved, patch);
      applyFields(issue.feedback_id, reconciled);
      void queryClient.invalidateQueries({
        queryKey: ["reported-feedback", "summary"],
      });
      return { ...issue, ...reconciled };
    } catch (err) {
      applyFields(issue.feedback_id, rollback);
      toast.error(extractErrorMessage(err, errorFallback));
      return null;
    }
  };

  const handleStatusChange = (
    issue: ReportedFeedbackItem,
    next: FeedbackStatus,
  ) => {
    if (next === issue.status) return;
    void handleIssuePatch(issue, { status: next }, "Failed to update status").then(
      (saved) => {
        if (saved) toast.success(`Marked as ${statusMeta(statuses, next).label}`);
      },
    );
  };

  const handleFilterChange = (value: string) => {
    setStatusFilter(value as FeedbackStatus | "all");
    setCurrentPage(1);
  };

  const handleTopicChange = (value: string) => {
    setTopicFilter(value);
    setSubtopicFilter("all");
    setCurrentPage(1);
  };

  const handleSubtopicChange = (value: string) => {
    setSubtopicFilter(value);
    setCurrentPage(1);
  };

  const handleWorkflowChange = (value: string) => {
    setWorkflowFilter(value);
    setCurrentPage(1);
  };

  const handleDateRangeChange = (range: DateRange | undefined) => {
    setDateRange(range);
    setCurrentPage(1);
  };

  const columns: Column<ReportedFeedbackItem>[] = [
    {
      header: "Comment",
      key: "comment",
      headerClassName: "w-[300px]",
      cell: (item) => (
        <span className="block max-w-[280px] truncate text-sm">
          {item.comment}
        </span>
      ),
    },
    {
      header: "Message",
      key: "message",
      headerClassName: "w-[260px]",
      cell: (item) => (
        <span className="block max-w-[240px] truncate text-sm text-muted-foreground">
          <span className="mr-1 text-xs font-medium uppercase">
            {item.speaker}:
          </span>
          {item.text}
        </span>
      ),
    },
    {
      header: "Workflow",
      key: "workflow",
      headerClassName: "w-[150px]",
      cell: (item) => (
        <span className="block max-w-[140px] truncate text-sm">
          {item.workflow_name || (
            <span className="italic text-muted-foreground">—</span>
          )}
        </span>
      ),
    },
    {
      header: "Topic",
      key: "topic",
      headerClassName: "w-[170px]",
      cell: (item) =>
        item.conversation_topic ? (
          <TruncatedText className="max-w-[160px] text-sm">
            {topicLabel(item.conversation_topic, item.conversation_subtopic)}
          </TruncatedText>
        ) : (
          <span className="text-sm italic text-muted-foreground">—</span>
        ),
    },
    {
      header: "Reported",
      key: "reported_at",
      headerClassName: "w-[160px]",
      className: "whitespace-nowrap text-xs text-muted-foreground",
      cell: (item) => formatDateTime(item.reported_at),
    },
    {
      header: "Status",
      key: "status",
      headerClassName: "w-[160px]",
      // Editable inline; stop row-click so the dropdown doesn't open the dialog.
      cell: (item) =>
        canTriage ? (
          <div onClick={(e) => e.stopPropagation()}>
            <StatusSelect
              value={item.status}
              statuses={statuses}
              onChange={(next) => handleStatusChange(item, next)}
            />
          </div>
        ) : (
          <StatusBadge value={item.status} statuses={statuses} />
        ),
    },
  ];

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  const filterGroups: FilterMenuGroup[] = [
    {
      key: "workflow",
      label: "Workflow",
      allLabel: "All workflows",
      value: workflowFilter,
      options: workflows.map((wf) => ({ value: wf.id, label: wf.name })),
      onChange: handleWorkflowChange,
    },
    {
      key: "topic",
      label: "Topic",
      allLabel: "All topics",
      value: topicFilter,
      options: topicChoices.map((topic) => ({
        value: topic.name,
        label: topic.name,
      })),
      onChange: handleTopicChange,
    },
    ...(subtopicChoices.length > 0
      ? [
          {
            key: "subtopic",
            label: "Sub-topic",
            allLabel: "All sub-topics",
            value: subtopicFilter,
            options: subtopicChoices.map((subtopic) => ({
              value: subtopic,
              label: subtopic,
            })),
            onChange: handleSubtopicChange,
          },
        ]
      : []),
    {
      key: "status",
      label: "Status",
      allLabel: "All statuses",
      value: statusFilter,
      options: withCurrentStatus(statuses, statusFilter, {
        includeRetired: true,
      }).map((status) => ({
        value: status,
        label: statusMeta(statuses, status).label,
      })),
      onChange: handleFilterChange,
    },
  ];

  const hasActiveFilters =
    statusFilter !== "all" ||
    topicFilter !== "all" ||
    subtopicFilter !== "all" ||
    workflowFilter !== "all" ||
    Boolean(dateRange?.from || dateRange?.to);

  return (
    <PageLayout>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl md:text-3xl font-bold animate-fade-down">
            Reported Feedback
          </h1>
          <p className="text-sm md:text-base text-muted-foreground animate-fade-up">
            Messages flagged with a comment by admins or supervisors
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <DateRangePicker
            value={dateRange}
            onChange={handleDateRangeChange}
            disableFutureDates
          />
          <FilterMenu groups={filterGroups} className="h-10 text-sm" />
          {canManageStatuses && (
            <Link
              to="/settings?tab=feedback-statuses"
              className={buttonVariants({ variant: "outline" })}
            >
              <Settings />
              Manage statuses
            </Link>
          )}
        </div>
      </div>

      <StatsOverviewCard
        metrics={statusMetrics}
        loading={statusesLoading || summaryLoading}
        error={
          statusesError || summaryError
            ? "Couldn't load the status counts."
            : null
        }
      />

      <DataTable
        data={rows}
        columns={columns}
        keyExtractor={(item) => item.feedback_id}
        onRowClick={openDialog}
        loading={loading}
        error={error ? error.message : null}
        searchQuery={statusFilter === "all" ? "" : statusFilter}
        emptyState={
          <ListEmptyState
            icon={<MessageSquareDot className="h-12 w-12 text-muted-foreground" />}
            title={
              hasActiveFilters ? "No matching feedback yet" : "No reported feedback yet"
            }
            description={
              hasActiveFilters
                ? "No reported feedback matches the current filters. Try widening the date range or clearing a filter."
                : "When an admin or supervisor leaves a comment on a message, it shows up here as feedback you can track and resolve."
            }
          />
        }
      />

      {total > PAGE_SIZE && (
        <PaginationBar
          total={total}
          pageSize={PAGE_SIZE}
          currentPage={safePage}
          pageItemCount={rows.length}
          onPageChange={setCurrentPage}
        />
      )}

      <ReportedFeedbackDialog
        issue={selectedIssue}
        isOpen={isDialogOpen}
        onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) setSelectedIssue(null);
        }}
        statuses={statuses}
        canTriage={canTriage}
        onStatusChange={handleStatusChange}
        onIssuePatch={handleIssuePatch}
        onOpenConversation={openConversation}
        onOpenWorkflow={openWorkflow}
      />
    </PageLayout>
  );
}
