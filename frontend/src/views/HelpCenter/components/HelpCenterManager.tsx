import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { AlertCircle, ChevronLeft, ChevronRight, LifeBuoy, Plus } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { RichTextEditor, RichTextEditorToolbar } from "@/components/RichTextEditor";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { SearchInput } from "@/components/SearchInput";
import { PageListSkeleton } from "@/components/skeletons";
import {
  createSupportTicket,
  listSupportTickets,
  searchDuplicateTickets,
} from "@/services/helpCenter";
import {
  SupportTicket,
  SupportTicketDuplicateCandidate,
  SupportTicketType,
} from "@/interfaces/helpCenter.interface";
import { TicketStatusBadge } from "./TicketStatusBadge";

type ViewMode = "list" | "form";

const TICKET_TYPE_LABELS: Record<string, string> = {
  bug: "Bug",
  feature: "Feature",
  task: "Task",
};

const RICH_TOOLBAR: RichTextEditorToolbar = {
  bold: true,
  italic: true,
  fontSize: true,
  link: true,
  image: true,
};

const stripHtml = (html: string): string =>
  html
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();

/** One-line plain-text preview of a ticket's primary content. */
const ticketPreview = (ticket: SupportTicket): string => {
  const raw =
    ticket.ticket_type === "bug"
      ? ticket.repro_steps || ticket.system_info || ""
      : ticket.description || "";
  const text = stripHtml(raw || "");
  return text.length > 140 ? `${text.slice(0, 140)}…` : text;
};

const formatDate = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

export default function HelpCenterManager() {
  const navigate = useNavigate();
  const location = useLocation();

  const [view, setView] = useState<ViewMode>("list");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // Form state
  const [title, setTitle] = useState("");
  const [ticketType, setTicketType] = useState<SupportTicketType>("bug");
  const [description, setDescription] = useState("");
  const [reproSteps, setReproSteps] = useState("");
  const [systemInfo, setSystemInfo] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [duplicates, setDuplicates] = useState<SupportTicketDuplicateCandidate[]>([]);
  const [duplicateCheckLoading, setDuplicateCheckLoading] = useState(false);

  const fetchTickets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await listSupportTickets({ limit: 100 });
      setTickets(res.items);
    } catch {
      setError("Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const state = location.state as { openForm?: boolean } | null;
    if (state?.openForm) {
      setView("form");
      navigate("/help-center", { replace: true, state: {} });
    }
  }, [location.key, navigate]);

  useEffect(() => {
    if (view === "list") {
      fetchTickets();
    }
  }, [view, fetchTickets]);

  useEffect(() => {
    if (view !== "form" || title.trim().length < 8) {
      setDuplicates([]);
      return;
    }
    const timer = setTimeout(async () => {
      setDuplicateCheckLoading(true);
      try {
        const found = await searchDuplicateTickets(title.trim(), ticketType);
        setDuplicates(found);
      } catch {
        setDuplicates([]);
      } finally {
        setDuplicateCheckLoading(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [title, ticketType, view]);

  const resetForm = () => {
    setTitle("");
    setTicketType("bug");
    setDescription("");
    setReproSteps("");
    setSystemInfo("");
    setAcceptanceCriteria("");
    setDuplicates([]);
  };

  const handleCancelForm = () => {
    resetForm();
    setView("list");
  };

  const submitTicket = async (opts?: { duplicateOfId?: string; forceCreate?: boolean }) => {
    if (title.trim().length < 3) {
      toast.error("Title must be at least 3 characters");
      return;
    }
    setSubmitting(true);
    try {
      const ticket = await createSupportTicket({
        title: title.trim(),
        ticket_type: ticketType,
        description: ticketType === "bug" ? "" : description,
        repro_steps: ticketType === "bug" ? reproSteps : undefined,
        system_info: ticketType === "bug" ? systemInfo : undefined,
        acceptance_criteria:
          ticketType === "bug" || ticketType === "feature"
            ? acceptanceCriteria
            : undefined,
        duplicate_of_id: opts?.duplicateOfId,
        force_create: opts?.forceCreate,
      });
      toast.success(opts?.duplicateOfId ? "Linked to existing issue" : "Issue submitted");
      resetForm();
      setView("list");
      navigate(`/help-center/${ticket.id}`);
    } catch {
      toast.error("Failed to submit issue");
    } finally {
      setSubmitting(false);
    }
  };

  const filteredTickets = tickets.filter((item) => {
    const matchesQuery = item.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || item.status === statusFilter;
    const matchesType = typeFilter === "all" || item.ticket_type === typeFilter;
    return matchesQuery && matchesStatus && matchesType;
  });

  // Status options are derived from the live Azure DevOps states present in the
  // loaded tickets (they vary by work item type/process), not a fixed list.
  const statusOptions = Array.from(new Set(tickets.map((t) => t.status))).sort();

  if (view === "form") {
    return (
      <div className="space-y-8">
        <div className="flex items-center">
          <Button variant="ghost" size="icon" onClick={handleCancelForm} className="mr-2">
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <h2 className="text-2xl font-bold tracking-tight">Report issue</h2>
        </div>

        {duplicates.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p className="font-medium text-sm mb-2">Possible duplicates</p>
            {duplicateCheckLoading && (
              <p className="text-xs text-gray-500 mb-2">Checking for similar issues...</p>
            )}
            <ul className="space-y-2">
              {duplicates.map((d) => (
                <li
                  key={d.id}
                  className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm bg-white/60 rounded-md p-2"
                >
                  <span className="flex-1 truncate font-medium">{d.title}</span>
                  <TicketStatusBadge status={d.status} />
                  <span className="text-gray-500">{d.vote_count} reports</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={() => submitTicket({ duplicateOfId: d.id })}
                    disabled={submitting}
                  >
                    +1 same issue
                  </Button>
                </li>
              ))}
            </ul>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mt-3"
              onClick={() => submitTicket({ forceCreate: true })}
              disabled={submitting}
            >
              Submit as new issue anyway
            </Button>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitTicket();
          }}
        >
          <div className="space-y-6">
            <div className="rounded-lg border bg-white">
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <h3 className="text-lg font-semibold">Issue details</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Summary and type. The engineering team picks it up after you submit.
                    </p>
                  </div>
                  <div className="md:col-span-2 space-y-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <div className="mb-1">Title</div>
                        <Input
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          placeholder="Brief summary of the problem"
                          required
                        />
                      </div>
                      <div>
                        <div className="mb-1">Type</div>
                        <Select
                          value={ticketType}
                          onValueChange={(v) => setTicketType(v as SupportTicketType)}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="bug">Bug</SelectItem>
                            <SelectItem value="feature">Feature</SelectItem>
                            <SelectItem value="task">Task</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-200" />

              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <h3 className="text-lg font-semibold">
                      {ticketType === "bug"
                        ? "Bug details"
                        : ticketType === "feature"
                          ? "Feature details"
                          : "Task details"}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">
                      {ticketType === "bug"
                        ? "Repro steps, system info and acceptance criteria help the team reproduce and fix it."
                        : ticketType === "feature"
                          ? "Describe the feature and what done looks like."
                          : "Describe what needs to be done."}
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      Use the toolbar to format text, add links, and attach images.
                    </p>
                  </div>
                  <div className="md:col-span-2 space-y-5">
                    {ticketType === "bug" ? (
                      <>
                        <div>
                          <div className="mb-1 text-sm font-medium">Repro steps</div>
                          <RichTextEditor
                            value={reproSteps}
                            onChange={setReproSteps}
                            toolbar={RICH_TOOLBAR}
                            placeholder="1. Go to… 2. Click… 3. See the error"
                            minHeight="120px"
                            maxHeight="360px"
                          />
                        </div>
                        <div>
                          <div className="mb-1 text-sm font-medium">System info</div>
                          <RichTextEditor
                            value={systemInfo}
                            onChange={setSystemInfo}
                            toolbar={RICH_TOOLBAR}
                            placeholder="Browser, OS, app version, environment…"
                            minHeight="100px"
                            maxHeight="300px"
                          />
                        </div>
                        <div>
                          <div className="mb-1 text-sm font-medium">Acceptance criteria</div>
                          <RichTextEditor
                            value={acceptanceCriteria}
                            onChange={setAcceptanceCriteria}
                            toolbar={RICH_TOOLBAR}
                            placeholder="What does “fixed” look like?"
                            minHeight="100px"
                            maxHeight="300px"
                          />
                        </div>
                      </>
                    ) : ticketType === "feature" ? (
                      <>
                        <div>
                          <div className="mb-1 text-sm font-medium">Description</div>
                          <RichTextEditor
                            value={description}
                            onChange={setDescription}
                            toolbar={RICH_TOOLBAR}
                            placeholder="Describe the feature and the problem it solves"
                            minHeight="140px"
                            maxHeight="400px"
                          />
                        </div>
                        <div>
                          <div className="mb-1 text-sm font-medium">Acceptance criteria</div>
                          <RichTextEditor
                            value={acceptanceCriteria}
                            onChange={setAcceptanceCriteria}
                            toolbar={RICH_TOOLBAR}
                            placeholder="What does “done” look like?"
                            minHeight="100px"
                            maxHeight="300px"
                          />
                        </div>
                      </>
                    ) : (
                      <div>
                        <div className="mb-1 text-sm font-medium">Description</div>
                        <RichTextEditor
                          value={description}
                          onChange={setDescription}
                          toolbar={RICH_TOOLBAR}
                          placeholder="Describe the task"
                          minHeight="140px"
                          maxHeight="400px"
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={handleCancelForm}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Submitting..." : "Submit issue"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 shrink-0">
            <h2 className="text-2xl sm:text-3xl font-bold whitespace-nowrap">Help Center</h2>
            <p className="text-zinc-400 font-normal text-sm mt-0.5 hidden sm:block">
              Report bugs and feature requests and track their status
            </p>
          </div>
          <div className="flex flex-nowrap items-center gap-2 min-w-0 overflow-x-auto pb-0.5 lg:overflow-visible">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[8.5rem] shrink-0 bg-white">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {statusOptions.map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">
                    {s === "sync_pending" ? "Syncing" : s.replace(/_/g, " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[7rem] shrink-0 bg-white">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                <SelectItem value="bug">Bug</SelectItem>
                <SelectItem value="feature">Feature</SelectItem>
                <SelectItem value="task">Task</SelectItem>
              </SelectContent>
            </Select>
            <SearchInput
              placeholder="Search tickets..."
              className="!w-[11rem] shrink-0"
              value={searchQuery}
              onChange={setSearchQuery}
            />
            <Button
              onClick={() => setView("form")}
              className="shrink-0 rounded-full whitespace-nowrap"
            >
              <Plus className="h-4 w-4 mr-2" />
              Report issue
            </Button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
            <AlertCircle className="h-4 w-4" />
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        <div className="rounded-lg border bg-white overflow-hidden">
          {loading ? (
            <PageListSkeleton variant="rich" bordered={false} />
          ) : filteredTickets.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
              <div className="rounded-full bg-gray-100 p-4">
                <LifeBuoy className="h-12 w-12 text-gray-400" />
              </div>
              <h3 className="font-medium text-lg">
                {searchQuery || statusFilter !== "all" || typeFilter !== "all"
                  ? "No tickets found"
                  : "No tickets yet"}
              </h3>
              <p className="text-sm text-gray-500 max-w-md px-4">
                {searchQuery || statusFilter !== "all" || typeFilter !== "all"
                  ? "Try adjusting your search or filters."
                  : "Report bugs and feature requests here. Each submission is routed to the engineering team."}
              </p>
              <Button onClick={() => setView("form")} className="rounded-full">
                Report your first issue
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredTickets.map((ticket) => {
                const preview = ticketPreview(ticket);
                return (
                  <div
                    key={ticket.id}
                    className="group px-4 py-4 sm:px-6 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/help-center/${ticket.id}`)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 flex flex-col space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-base sm:text-lg font-semibold break-words">
                            {ticket.title}
                          </h4>
                          <TicketStatusBadge status={ticket.status} />
                        </div>
                        {preview && (
                          <p className="text-sm text-gray-500 line-clamp-1">{preview}</p>
                        )}
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-400">
                          <span className="font-medium text-gray-500">
                            {TICKET_TYPE_LABELS[ticket.ticket_type] ?? ticket.ticket_type}
                          </span>
                          {ticket.vote_count > 1 && (
                            <>
                              <span aria-hidden>·</span>
                              <span>{ticket.vote_count} reports</span>
                            </>
                          )}
                          {ticket.created_at && (
                            <>
                              <span aria-hidden>·</span>
                              <span>{formatDate(ticket.created_at)}</span>
                            </>
                          )}
                        </div>
                        {ticket.sync_error && (
                          <p className="text-xs text-destructive truncate">
                            Sync: {ticket.sync_error}
                          </p>
                        )}
                      </div>
                      <ChevronRight className="h-5 w-5 shrink-0 mt-1 text-gray-300 transition-colors group-hover:text-gray-500" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
