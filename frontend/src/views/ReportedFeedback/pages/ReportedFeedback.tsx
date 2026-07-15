import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare } from "lucide-react";
import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { PageLayout } from "@/components/PageLayout";
import { DataTable, Column } from "@/components/ui/data-table";
import { ListEmptyState } from "@/components/ListEmptyState";
import { PaginationBar } from "@/components/PaginationBar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DateRangePicker } from "@/components/date-range-picker";
import { usePersistedDateRange } from "@/hooks/usePersistedDateRange";
import { getWorkflowsMinimal } from "@/services/workflows";

import {
  FeedbackStatus,
  ReportedFeedbackItem,
  updateFeedbackStatus,
} from "@/services/reportedFeedback";
import { useReportedFeedback } from "../hooks/useReportedFeedback";
import { ReportedFeedbackDialog } from "../components/ReportedFeedbackDialog";
import { StatusSelect } from "../components/StatusSelect";
import { STATUS_META, STATUS_ORDER, formatDate } from "../constants";

const PAGE_SIZE = 20;

export default function ReportedFeedback() {
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "all">(
    "all",
  );
  const [workflowFilter, setWorkflowFilter] = useState<string>("all");
  // Shared global range (same component/store as the dashboard).
  const [dateRange, setDateRange] = usePersistedDateRange(undefined);

  const { data: workflowsData } = useQuery({
    queryKey: ["workflows-minimal"],
    queryFn: getWorkflowsMinimal,
  });
  const workflows = workflowsData ?? [];

  // Server-side time filter on the reported time (when the comment was added).
  const fromDate = dateRange?.from
    ? format(dateRange.from, "yyyy-MM-dd")
    : undefined;
  const toDate = dateRange?.to
    ? format(dateRange.to, "yyyy-MM-dd 23:59:59")
    : undefined;

  const { data, total, loading, error } = useReportedFeedback({
    skip: (currentPage - 1) * PAGE_SIZE,
    limit: PAGE_SIZE,
    status: statusFilter,
    from_date: fromDate,
    to_date: toDate,
    workflow_id: workflowFilter !== "all" ? workflowFilter : undefined,
  });

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

  const openConversation = (conversationId: string) => {
    if (!conversationId) return;
    navigate(`/transcripts?conversation=${encodeURIComponent(conversationId)}`);
  };

  const openWorkflow = (agentId: string | null) => {
    if (!agentId) return;
    navigate(`/ai-agents/workflow/${agentId}`);
  };

  const handleStatusChange = async (
    issue: ReportedFeedbackItem,
    next: FeedbackStatus,
  ) => {
    if (next === issue.status) return;
    const previous = issue.status;

    const apply = (status: FeedbackStatus) => {
      setRows((rs) =>
        rs.map((r) =>
          r.feedback_id === issue.feedback_id ? { ...r, status } : r,
        ),
      );
      setSelectedIssue((current) =>
        current && current.feedback_id === issue.feedback_id
          ? { ...current, status }
          : current,
      );
    };

    apply(next);
    try {
      await updateFeedbackStatus(issue.feedback_id, next);
      toast.success(`Marked as ${STATUS_META[next].label}`);
    } catch {
      apply(previous);
      toast.error("Failed to update status");
    }
  };

  const handleFilterChange = (value: string) => {
    setStatusFilter(value as FeedbackStatus | "all");
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
      header: "Reported",
      key: "reported_at",
      headerClassName: "w-[160px]",
      className: "whitespace-nowrap text-xs text-muted-foreground",
      cell: (item) => formatDate(item.reported_at),
    },
    {
      header: "Status",
      key: "status",
      headerClassName: "w-[160px]",
      // Editable inline; stop row-click so the dropdown doesn't open the dialog.
      cell: (item) => (
        <div onClick={(e) => e.stopPropagation()}>
          <StatusSelect
            value={item.status}
            onChange={(next) => handleStatusChange(item, next)}
          />
        </div>
      ),
    },
  ];

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  const hasActiveFilters =
    statusFilter !== "all" ||
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
          <Select value={workflowFilter} onValueChange={handleWorkflowChange}>
            <SelectTrigger className="h-9 w-[200px] rounded-full">
              <SelectValue placeholder="Filter by workflow" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All workflows</SelectItem>
              {workflows.map((wf) => (
                <SelectItem key={wf.id} value={wf.id}>
                  {wf.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="h-9 w-[180px] rounded-full">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {STATUS_ORDER.map((status) => (
                <SelectItem key={status} value={status}>
                  {STATUS_META[status].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

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
            icon={<MessageSquare className="h-12 w-12 text-gray-400" />}
            title={
              hasActiveFilters ? "No matching feedback" : "No reported feedback yet"
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
        onStatusChange={handleStatusChange}
        onOpenConversation={openConversation}
        onOpenWorkflow={openWorkflow}
      />
    </PageLayout>
  );
}
