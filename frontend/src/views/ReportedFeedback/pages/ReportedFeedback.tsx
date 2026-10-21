import { useState } from "react";
import { MessageSquareDot, NotebookPen, Settings } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
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
import { SearchInput } from "@/components/SearchInput";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { useTopicFilter } from "@/hooks/useTopicFilter";
import { usePermissions } from "@/context/PermissionContext";
import { ISSUE_CATEGORIES } from "@/services/issueStatuses";
import { extractErrorMessage } from "@/helpers/apiError";
import { toInclusiveDateParams } from "@/helpers/dateRange";

import { ReportedFeedbackItem } from "@/services/reportedFeedback";
import { StatsOverviewCard } from "@/views/Analytics/components/StatsOverviewCard";
import { useAgentsList } from "@/views/Analytics/hooks/useAgentsList";
import {
  cacheIssue,
  useFeedbackSummary,
  useIssue,
  useIssuePatch,
  useReportedFeedback,
} from "../hooks/useReportedFeedback";
import { useReportLink } from "../hooks/useReportLink";
import { useIssueStatuses } from "../hooks/useIssueStatuses";
import { ReportedFeedbackDialog } from "../components/ReportedFeedbackDialog";
import { StatusBadge, StatusSelect } from "../components/StatusSelect";
import { CATEGORY_LABELS } from "../constants";
import { statusMeta, withCurrentStatus } from "../helpers/issueStatuses";
import { topicLabel } from "../helpers/triageDraft";
import { HighlightedExcerpt } from "../components/HighlightedExcerpt";
import { formatDateTime } from "@/helpers/utils";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;
const LAST_OPENED_ROW_ID = "reported-feedback-last-opened";

export default function ReportedFeedback() {
  const permissions = usePermissions();
  const canTriage =
    permissions.includes("*") || permissions.includes("update:conversation");
  const canManageStatuses =
    permissions.includes("*") || permissions.includes("write:app_settings");
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");
  // Shared global range (same component/store as the dashboard).
  const [dateRange, setDateRange] = usePersistedDateRange(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const search = useDebouncedValue(searchQuery, SEARCH_DEBOUNCE_MS).trim();
  const appliedRange = search ? undefined : dateRange;

  const { agents } = useAgentsList();

  const { data: statuses = [] } = useIssueStatuses();
  const {
    topic: topicFilter,
    subtopic: subtopicFilter,
    topicChoices,
    subtopicChoices,
    changeTopic,
    changeSubtopic,
  } = useTopicFilter();

  // Server-side time filter on the reported time (when the comment was added).
  const filters = {
    agent_id: agentFilter !== "all" ? agentFilter : undefined,
    ...toInclusiveDateParams(appliedRange),
    topic: topicFilter !== "all" ? topicFilter : undefined,
    subtopic: subtopicFilter !== "all" ? subtopicFilter : undefined,
    search: search || undefined,
  };

  const filterKey = JSON.stringify({ status: statusFilter, ...filters });
  const [pagedFilterKey, setPagedFilterKey] = useState(filterKey);
  if (filterKey !== pagedFilterKey) {
    setPagedFilterKey(filterKey);
    setCurrentPage(1);
  }

  const {
    data: list,
    isFetching,
    error,
  } = useReportedFeedback({
    skip: (currentPage - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter,
    ...filters,
  });
  const rows = list?.items ?? [];
  const total = list?.total ?? 0;
  // A new search term keeps the last rows up while it loads, so typing doesn't flash
  const [listedSearch, setListedSearch] = useState(search);
  if (!isFetching && listedSearch !== search) setListedSearch(search);
  const keepRows = Boolean(search) && search !== listedSearch && rows.length > 0;
  const loading = isFetching && !keepRows;

  const summary = useFeedbackSummary(filters);
  const statusMetrics = [
    { label: "Total reported", value: summary.total.toLocaleString() },
    ...ISSUE_CATEGORIES.map((category) => ({
      label: CATEGORY_LABELS[category],
      value: summary.totals[category].toLocaleString(),
    })),
  ];

  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useIssue(selectedId);
  const dialogIssue =
    selected.data ?? rows.find((row) => row.feedback_id === selectedId) ?? null;
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [lastOpenedId, setLastOpenedId] = useState<string | null>(null);

  const openDialog = (feedbackId: string) => {
    setSelectedId(feedbackId);
    setLastOpenedId(feedbackId);
    setIsDialogOpen(true);
  };

  const openRow = (issue: ReportedFeedbackItem) => {
    cacheIssue(queryClient, issue);
    openDialog(issue.feedback_id);
  };

  const link = useReportLink(openDialog, !isDialogOpen);

  const focusLastOpenedRow = (event: Event) => {
    event.preventDefault();
    document.getElementById(LAST_OPENED_ROW_ID)?.focus();
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

  const patchIssue = useIssuePatch();

  const handleStatusChange = (
    issue: ReportedFeedbackItem,
    next: string,
  ) => {
    if (next === issue.status) return;
    void patchIssue.mutateAsync({ issue, patch: { status: next } }).then(
      () => toast.success(`Marked as ${statusMeta(statuses, next).label}`),
      (err) => toast.error(extractErrorMessage(err, "Failed to update status")),
    );
  };

  const columns: Column<ReportedFeedbackItem>[] = [
    {
      header: "Comment",
      key: "comment",
      headerClassName: "w-[300px]",
      cell: (item) => (
        <>
          <span className="block max-w-[280px] truncate text-sm">
            <HighlightedExcerpt text={item.comment} search={search} />
          </span>
          {item.matched_note && (
            <p className="mt-1 flex max-w-[280px] gap-1.5 text-xs text-muted-foreground">
              <NotebookPen className="mt-0.5 h-3 w-3 shrink-0" />
              <span className="sr-only">Matching note: </span>
              <span className="line-clamp-2 break-words">
                <HighlightedExcerpt text={item.matched_note} search={search} />
              </span>
            </p>
          )}
        </>
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
      header: "Agent",
      key: "agent",
      headerClassName: "w-[150px]",
      cell: (item) => (
        <span className="block max-w-[140px] truncate text-sm">
          {item.agent_name || (
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
      // Editable inline; stop row events so the dropdown doesn't open the dialog.
      cell: (item) =>
        canTriage ? (
          <div
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
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
      key: "agent",
      label: "Agent",
      allLabel: "All agents",
      value: agentFilter,
      options: agents.map((a) => ({ value: a.id, label: a.name })),
      onChange: setAgentFilter,
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
      onChange: changeTopic,
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
            onChange: changeSubtopic,
          },
        ]
      : []),
    {
      key: "status",
      label: "Status",
      allLabel: "All statuses",
      value: statusFilter,
      options: withCurrentStatus(
        statuses.filter(
          (status) =>
            status.is_active === 1 || (summary.byStatus[status.key] ?? 0) > 0,
        ),
        statusFilter,
        { includeRetired: true },
      ).map((status) => ({
        value: status,
        label: statusMeta(statuses, status).label,
      })),
      onChange: setStatusFilter,
    },
  ];

  const hasActiveFilters =
    statusFilter !== "all" ||
    topicFilter !== "all" ||
    subtopicFilter !== "all" ||
    agentFilter !== "all" ||
    Boolean(appliedRange?.from || appliedRange?.to) ||
    Boolean(search);

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
            value={appliedRange}
            onChange={setDateRange}
            placeholder={search ? "All dates" : undefined}
            disabled={Boolean(search)}
            disableFutureDates
          />
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search reports..."
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
        loading={summary.isLoading}
        error={summary.isError ? "Couldn't load the status counts." : null}
      />

      <DataTable
        data={rows}
        columns={columns}
        keyExtractor={(item) => item.feedback_id}
        onRowClick={openRow}
        getRowProps={(item) =>
          item.feedback_id === lastOpenedId ? { id: LAST_OPENED_ROW_ID } : undefined
        }
        loading={loading}
        error={error ? error.message : null}
        emptyState={
          <ListEmptyState
            icon={<MessageSquareDot className="h-12 w-12 text-muted-foreground" />}
            title={
              hasActiveFilters ? "No matching feedback yet" : "No reported feedback yet"
            }
            description={
              search
                ? "No comment or note matches this search. Try other words or clear a filter."
                : hasActiveFilters
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
        key={selectedId}
        issue={dialogIssue}
        isOpen={isDialogOpen}
        onOpenChange={(open) => {
          setIsDialogOpen(open);
          if (!open) {
            setSelectedId(null);
            link.clear();
          }
        }}
        onCloseAutoFocus={focusLastOpenedRow}
        statuses={statuses}
        canTriage={canTriage}
        onStatusChange={handleStatusChange}
        onOpenConversation={openConversation}
        onOpenWorkflow={openWorkflow}
      />
    </PageLayout>
  );
}
