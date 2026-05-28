import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  LifeBuoy,
  ListChecks,
  Plus,
} from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  listTriageTickets,
  linkTicketDuplicate,
  searchDuplicateTickets,
} from "@/services/helpCenter";
import {
  SupportTicket,
  SupportTicketDuplicateCandidate,
  SupportTicketType,
} from "@/interfaces/helpCenter.interface";
import { TicketStatusBadge } from "./TicketStatusBadge";
import { hasAnyPermission } from "@/services/auth";

type ViewMode = "list" | "form" | "triage";

const TICKET_TYPE_LABELS: Record<string, string> = {
  bug: "Bug",
  feature: "Feature",
  question: "Question",
};

export default function HelpCenterManager() {
  const navigate = useNavigate();
  const location = useLocation();
  const canTriage = hasAnyPermission(["manage:support_ticket", "*"]);
  const canCreate = hasAnyPermission(["create:support_ticket", "*"]);

  const [view, setView] = useState<ViewMode>("list");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  // Triage state
  const [triageTickets, setTriageTickets] = useState<SupportTicket[]>([]);
  const [triageLoading, setTriageLoading] = useState(false);
  const [linkTarget, setLinkTarget] = useState<Record<string, string>>({});

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ticketType, setTicketType] = useState<SupportTicketType>("bug");
  const [steps, setSteps] = useState("");
  const [expected, setExpected] = useState("");
  const [actual, setActual] = useState("");
  const [browser, setBrowser] = useState("");
  const [appVersion, setAppVersion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [duplicates, setDuplicates] = useState<SupportTicketDuplicateCandidate[]>([]);
  const [duplicateCheckLoading, setDuplicateCheckLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  const fetchTriage = useCallback(async () => {
    try {
      setTriageLoading(true);
      const res = await listTriageTickets();
      setTriageTickets(res.items);
    } catch {
      toast.error("Failed to load triage queue");
    } finally {
      setTriageLoading(false);
    }
  }, []);

  useEffect(() => {
    const state = location.state as { openForm?: boolean; openTriage?: boolean } | null;
    if (state?.openForm) {
      setView("form");
      navigate("/help-center", { replace: true, state: {} });
    } else if (state?.openTriage) {
      setView("triage");
      navigate("/help-center", { replace: true, state: {} });
    }
  }, [location.key, navigate]);

  useEffect(() => {
    if (view === "list") {
      fetchTickets();
    } else if (view === "triage") {
      fetchTriage();
    }
  }, [view, fetchTickets, fetchTriage]);

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
    setDescription("");
    setTicketType("bug");
    setSteps("");
    setExpected("");
    setActual("");
    setBrowser("");
    setAppVersion("");
    setDuplicates([]);
    setShowAdvanced(false);
  };

  const hasEnvironmentValues = Boolean(browser.trim() || appVersion.trim());

  useEffect(() => {
    if (view === "form" && hasEnvironmentValues) {
      setShowAdvanced(true);
    }
  }, [view, hasEnvironmentValues]);

  const handleCancelForm = () => {
    resetForm();
    setView("list");
  };

  const buildDescription = () => {
    const parts = [description.trim()];
    if (steps) parts.push(`\n\n**Steps to reproduce**\n${steps}`);
    if (expected) parts.push(`\n\n**Expected**\n${expected}`);
    if (actual) parts.push(`\n\n**Actual**\n${actual}`);
    return parts.filter(Boolean).join("");
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
        description: buildDescription(),
        ticket_type: ticketType,
        environment: {
          browser: browser || undefined,
          app_version: appVersion || undefined,
          steps_to_reproduce: steps || undefined,
          expected_behavior: expected || undefined,
          actual_behavior: actual || undefined,
        },
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

  const handleLinkDuplicate = async (ticketId: string) => {
    const canonicalId = linkTarget[ticketId]?.trim();
    if (!canonicalId) {
      toast.error("Enter canonical ticket ID");
      return;
    }
    try {
      await linkTicketDuplicate(ticketId, canonicalId);
      toast.success("Linked as duplicate");
      await fetchTriage();
    } catch {
      toast.error("Failed to link duplicate");
    }
  };

  const filteredTickets = tickets.filter((item) => {
    const matchesQuery = item.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || item.status === statusFilter;
    const matchesType = typeFilter === "all" || item.ticket_type === typeFilter;
    return matchesQuery && matchesStatus && matchesType;
  });

  const filteredTriage = triageTickets.filter((t) =>
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
                      Summary and type. A matching Azure DevOps work item is created after submit.
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
                            <SelectItem value="feature">Feature request</SelectItem>
                            <SelectItem value="question">Question</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div>
                      <div className="mb-1">Description</div>
                      <Textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="What happened?"
                        rows={4}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="-mx-px border-t border-gray-200" />

              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <h3 className="text-lg font-semibold">Reproduction</h3>
                    <p className="text-sm text-gray-500 mt-1">
                      Steps and expected vs actual behavior help engineering reproduce faster.
                    </p>
                  </div>
                  <div className="md:col-span-2 space-y-4">
                    <div>
                      <div className="mb-1">Steps to reproduce</div>
                      <Textarea
                        value={steps}
                        onChange={(e) => setSteps(e.target.value)}
                        rows={3}
                        placeholder="1. Go to... 2. Click..."
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <div className="mb-1">Expected behavior</div>
                        <Textarea
                          value={expected}
                          onChange={(e) => setExpected(e.target.value)}
                          rows={2}
                        />
                      </div>
                      <div>
                        <div className="mb-1">Actual behavior</div>
                        <Textarea
                          value={actual}
                          onChange={(e) => setActual(e.target.value)}
                          rows={2}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-200 px-6 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAdvanced((prev) => !prev)}
                  className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left transition-colors hover:bg-muted/40"
                  aria-expanded={showAdvanced}
                  aria-controls="help-center-advanced-section"
                >
                  <span className="text-sm font-medium">Advanced</span>
                  {showAdvanced ? (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
              </div>

              {showAdvanced && (
                <div id="help-center-advanced-section" className="px-6 pb-6 space-y-3">
                  <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
                    <div>
                      <h3 className="text-sm font-semibold">Environment</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Optional context about where the issue occurred.
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <div className="mb-1 text-sm">Browser</div>
                        <Input
                          value={browser}
                          onChange={(e) => setBrowser(e.target.value)}
                          placeholder="e.g. Chrome 120"
                        />
                      </div>
                      <div>
                        <div className="mb-1 text-sm">App version</div>
                        <Input
                          value={appVersion}
                          onChange={(e) => setAppVersion(e.target.value)}
                          placeholder="e.g. v1.2.0"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
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

  if (view === "triage") {
    return (
      <div className="space-y-8">
        <div className="flex items-center">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setSearchQuery("");
              setView("list");
            }}
            className="mr-2"
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Triage queue</h2>
            <p className="text-sm text-gray-500">
              Review open issues and link duplicates to a canonical ticket
            </p>
          </div>
        </div>

        <div className="flex w-full sm:max-w-md">
          <SearchInput
            placeholder="Search triage queue..."
            className="w-full"
            value={searchQuery}
            onChange={setSearchQuery}
          />
        </div>

        <div className="rounded-lg border bg-white overflow-hidden">
          {triageLoading ? (
            <PageListSkeleton variant="rich" bordered={false} />
          ) : filteredTriage.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
              <div className="rounded-full bg-gray-100 p-4">
                <ListChecks className="h-12 w-12 text-gray-400" />
              </div>
              <h3 className="font-medium text-lg">
                {searchQuery ? "No tickets found" : "Triage queue is empty"}
              </h3>
              <p className="text-sm text-gray-500 max-w-md px-4">
                {searchQuery
                  ? "Try adjusting your search query."
                  : "No open tickets need triage right now."}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredTriage.map((ticket) => (
                <div key={ticket.id} className="px-4 py-4 sm:px-6 space-y-3">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/help-center/${ticket.id}`}
                        className="text-base font-semibold hover:underline break-words"
                      >
                        {ticket.title}
                      </Link>
                      <div className="flex flex-wrap gap-2 mt-2 items-center text-sm text-gray-500">
                        <TicketStatusBadge status={ticket.status} />
                        <span>{ticket.vote_count} reports</span>
                        {ticket.azure_work_item_id && (
                          <span>ADO #{ticket.azure_work_item_id}</span>
                        )}
                      </div>
                    </div>
                    <Button variant="secondary" size="sm" asChild className="shrink-0">
                      <Link to={`/help-center/${ticket.id}`}>View</Link>
                    </Button>
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <Input
                      placeholder="Canonical ticket ID"
                      value={linkTarget[ticket.id] ?? ""}
                      onChange={(e) =>
                        setLinkTarget((prev) => ({ ...prev, [ticket.id]: e.target.value }))
                      }
                      className="bg-white"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleLinkDuplicate(ticket.id)}
                      className="shrink-0"
                    >
                      Link as duplicate
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
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
              Report bugs and track issues synced to Azure DevOps
            </p>
          </div>
          <div className="flex flex-nowrap items-center gap-2 min-w-0 overflow-x-auto pb-0.5 lg:overflow-visible">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[8.5rem] shrink-0 bg-white">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="sync_pending">Syncing</SelectItem>
                <SelectItem value="new">New</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="in_progress">In progress</SelectItem>
                <SelectItem value="resolved">Resolved</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
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
                <SelectItem value="question">Question</SelectItem>
              </SelectContent>
            </Select>
            <SearchInput
              placeholder="Search tickets..."
              className="!w-[11rem] shrink-0"
              value={searchQuery}
              onChange={setSearchQuery}
            />
            {canTriage && (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchQuery("");
                  setView("triage");
                }}
                className="shrink-0 rounded-full whitespace-nowrap"
              >
                <ListChecks className="h-4 w-4 mr-2" />
                Triage
              </Button>
            )}
            {canCreate && (
              <Button
                onClick={() => setView("form")}
                className="shrink-0 rounded-full whitespace-nowrap"
              >
                <Plus className="h-4 w-4 mr-2" />
                Report issue
              </Button>
            )}
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
                  : "Report bugs and feature requests here. Each submission creates a work item in Azure DevOps for the engineering team."}
              </p>
              {!searchQuery && statusFilter === "all" && typeFilter === "all" && canCreate && (
                <Button onClick={() => setView("form")} className="rounded-full">
                  Report your first issue
                </Button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredTickets.map((ticket) => (
                <div
                  key={ticket.id}
                  className="px-4 py-4 sm:px-6 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={(e) => {
                    if ((e.target as HTMLElement).closest("a, button")) return;
                    navigate(`/help-center/${ticket.id}`);
                  }}
                >
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div className="flex-1 flex flex-col space-y-2 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-base sm:text-lg font-semibold break-words">
                          {ticket.title}
                        </h4>
                        <span className="inline-flex items-center rounded-md bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-800">
                          {TICKET_TYPE_LABELS[ticket.ticket_type] ?? ticket.ticket_type}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
                        <TicketStatusBadge status={ticket.status} />
                        {ticket.vote_count > 1 && <span>{ticket.vote_count} reports</span>}
                        {ticket.azure_work_item_id && (
                          <span>ADO #{ticket.azure_work_item_id}</span>
                        )}
                      </div>
                      {ticket.sync_error && (
                        <p className="text-xs text-destructive truncate">
                          Sync: {ticket.sync_error}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2 justify-end w-full md:w-auto shrink-0">
                      {ticket.azure_url && (
                        <Button
                          variant="outline"
                          size="sm"
                          asChild
                          onClick={(e) => e.stopPropagation()}
                        >
                          <a href={ticket.azure_url} target="_blank" rel="noreferrer">
                            <ExternalLink className="h-4 w-4 mr-1" />
                            Azure DevOps
                          </a>
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/help-center/${ticket.id}`);
                        }}
                      >
                        View
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
