import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import { Search, ShieldAlert, MessageCircle } from "lucide-react";
import toast from "react-hot-toast";

import { PageLayout } from "@/components/PageLayout";
import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Badge } from "@/components/badge";
import { DataTable } from "@/components/DataTable";
import { TableCell, TableRow } from "@/components/table";
import { PaginationBar } from "@/components/PaginationBar";

import {
  deleteConversationForGdpr,
  GdprConversationItem,
  GdprDeleteMode,
  searchConversationsByEmail,
} from "@/services/gdprConversations";
import { GdprDeleteDialog } from "../components/GdprDeleteDialog";
import { conversationService } from "@/services/liveConversations";
import { transformTranscript } from "@/views/Transcripts/helpers/transformers";
import type { Transcript } from "@/interfaces/transcript.interface";
import { TranscriptDialog } from "@/views/Transcripts/components/TranscriptDialog";
import { ActiveConversationDialog } from "@/views/ActiveConversations/components/ActiveConversationDialog";

const PAGE_SIZE = 10;

const formatDate = (value: string | null | undefined): string => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
};

const getRequesterEmail = (item: GdprConversationItem): string | null => {
  const attrs = item.custom_attributes;
  if (!attrs || typeof attrs !== "object") return null;
  const pii = (attrs as Record<string, unknown>).pii;
  if (!pii || typeof pii !== "object") return null;
  const email = (pii as Record<string, unknown>).requester_email;
  return typeof email === "string" ? email : null;
};

export default function GdprConversations() {
  const [emailQuery, setEmailQuery] = useState("");
  const [activeEmail, setActiveEmail] = useState<string | null>(null);
  const [items, setItems] = useState<GdprConversationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedConversationIds, setSelectedConversationIds] = useState<Set<string>>(
    () => new Set(),
  );

  const [selectedTranscript, setSelectedTranscript] = useState<Transcript | null>(null);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(false);
  const [isLiveTranscriptSelected, setIsLiveTranscriptSelected] = useState(false);
  const [isOpeningTranscript, setIsOpeningTranscript] = useState(false);

  const [conversationIdsToDelete, setConversationIdsToDelete] = useState<string[]>([]);
  const [finalizedConversationIdsSelected, setFinalizedConversationIdsSelected] = useState<
    Set<string>
  >(() => new Set());
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isFinalizedConversation = (item: Pick<GdprConversationItem, "status">): boolean =>
    (item.status ?? "").toLowerCase() === "finalized";

  const performSearch = useCallback(
    async (email: string, page: number) => {
      const trimmed = email.trim();
      if (!trimmed) {
        setItems([]);
        setTotal(0);
        setActiveEmail(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await searchConversationsByEmail(trimmed, {
          skip: (page - 1) * PAGE_SIZE,
          limit: PAGE_SIZE,
        });
        setItems(response.items);
        setTotal(response.total);
        setActiveEmail(trimmed);
        setSelectedConversationIds(new Set());
        setFinalizedConversationIdsSelected(new Set());
      } catch (err) {
        const axiosError = err as AxiosError<{ error?: string }>;
        const apiMessage =
          axiosError.response?.data?.error ??
          (err instanceof Error ? err.message : "Failed to search conversations.");
        setError(apiMessage);
        setItems([]);
        setTotal(0);
        setSelectedConversationIds(new Set());
        setFinalizedConversationIdsSelected(new Set());
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // Reset to first page when the email input is changed via the form.
  useEffect(() => {
    if (activeEmail && emailQuery.trim() !== activeEmail) {
      // Don't auto-trigger; the user must press Enter / click Search to avoid
      // hammering the FTS-backed endpoint with every keystroke.
    }
  }, [emailQuery, activeEmail]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCurrentPage(1);
    performSearch(emailQuery, 1);
  };

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    setSelectedConversationIds(new Set());
    setFinalizedConversationIdsSelected(new Set());
    if (activeEmail) {
      performSearch(activeEmail, page);
    }
  };

  const selectedCount = selectedConversationIds.size;
  const allOnPageSelected = items.length > 0 && selectedCount === items.length;

  const toggleSelectedConversation = (conversationId: string, checked: boolean) => {
    const item = items.find((candidate) => candidate.id === conversationId);
    const isFinalized = item ? isFinalizedConversation(item) : false;

    setSelectedConversationIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(conversationId);
      else next.delete(conversationId);
      return next;
    });

    setFinalizedConversationIdsSelected((prev) => {
      const next = new Set(prev);
      if (checked && isFinalized) next.add(conversationId);
      else next.delete(conversationId);
      return next;
    });

    if (checked && isFinalized) {
      toast(
        "This conversation is finalized and cannot be hard-deleted. It can still be soft-deleted or anonymized.",
      );
    }
  };

  const toggleSelectAllOnPage = (checked: boolean) => {
    setSelectedConversationIds(() => {
      if (!checked) return new Set();
      return new Set(items.map((item) => item.id));
    });
    setFinalizedConversationIdsSelected(() => {
      if (!checked) return new Set();
      return new Set(items.filter((item) => isFinalizedConversation(item)).map((item) => item.id));
    });

    if (checked) {
      const finalizedCount = items.filter((item) => isFinalizedConversation(item)).length;
      if (finalizedCount > 0) {
        toast(
          `${finalizedCount} finalized conversation${finalizedCount === 1 ? "" : "s"} selected. Finalized conversations cannot be hard-deleted.`,
        );
      }
    }
  };

  const handleBulkDeleteClick = () => {
    const ids = Array.from(selectedConversationIds);
    if (ids.length === 0) return;
    setConversationIdsToDelete(ids);
    setIsDialogOpen(true);
  };

  const handleOpenConversation = async (conversationId: string) => {
    if (!conversationId || isOpeningTranscript) return;
    try {
      setIsOpeningTranscript(true);
      const backend = await conversationService.fetchConversationsTranscriptsAndData(conversationId);
      const transformed = transformTranscript(backend);
      setSelectedTranscript(transformed);
      setIsLiveTranscriptSelected(
        transformed?.status === "in_progress" || transformed?.status === "takeover"
      );
      setIsTranscriptOpen(true);
    } catch {
      toast.error("Could not open conversation. It may not exist or you may not have access.");
    } finally {
      setIsOpeningTranscript(false);
    }
  };

  const handleDeleteConfirm = async (mode: GdprDeleteMode) => {
    if (conversationIdsToDelete.length === 0) return;
    setIsDeleting(true);
    try {
      const blockedIds =
        mode === "hard" ? finalizedConversationIdsSelected : new Set<string>();
      const idsToProcess =
        mode === "hard"
          ? conversationIdsToDelete.filter((id) => !blockedIds.has(id))
          : conversationIdsToDelete;

      if (mode === "hard" && idsToProcess.length === 0) {
        toast.error(
          `Hard delete is not allowed for finalized conversations. ${conversationIdsToDelete.length} selected item${
            conversationIdsToDelete.length === 1 ? "" : "s"
          } would be skipped.`,
        );
        return;
      }

      const failures: { id: string; message: string }[] = [];
      for (const id of idsToProcess) {
        try {
          await deleteConversationForGdpr(id, mode);
        } catch (err) {
          const axiosError = err as AxiosError<{ error?: string }>;
          const apiMessage =
            axiosError.response?.data?.error ??
            (err instanceof Error ? err.message : "Failed to delete conversation.");
          failures.push({ id, message: apiMessage });
        }
      }

      const succeededCount = idsToProcess.length - failures.length;
      if (succeededCount > 0) {
        toast.success(
          mode === "hard"
            ? `${succeededCount} conversation${succeededCount === 1 ? "" : "s"} permanently deleted.`
            : mode === "anonymize"
              ? `${succeededCount} conversation${succeededCount === 1 ? "" : "s"} anonymized.`
              : `${succeededCount} conversation${succeededCount === 1 ? "" : "s"} soft-deleted (PII scrubbed).`,
        );
      }
      if (mode === "hard" && blockedIds.size > 0) {
        toast(
          `${blockedIds.size} finalized conversation${blockedIds.size === 1 ? "" : "s"} skipped (hard delete not allowed).`,
        );
      }
      if (failures.length > 0) {
        toast.error(
          `Failed to delete ${failures.length} conversation${failures.length === 1 ? "" : "s"}.`,
        );
      }

      setIsDialogOpen(false);
      setConversationIdsToDelete([]);
      setSelectedConversationIds(new Set());
      setFinalizedConversationIdsSelected(new Set());
      // Refetch to reflect the new state. ``soft`` rows disappear from the
      // default list; ``anonymize`` rows stay but lose PII; ``hard`` rows are
      // gone from the list entirely.
      if (activeEmail) {
        await performSearch(activeEmail, currentPage);
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDialogOpenChange = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      setConversationIdsToDelete([]);
      setFinalizedConversationIdsSelected(new Set());
    }
  };

  const headers = [
    { label: "", className: "w-12 px-2" },          // checkbox column
    { label: "Conversation", className: "w-[260px]" },
    { label: "Email (PII)", className: "w-[220px]" },
    { label: "Status", className: "w-[120px]" },
    { label: "Created", className: "w-[160px]" },
    { label: "Updated", className: "w-[160px]" },
    { label: "Open", className: "w-[110px]" },
  ];

  const renderRow = (item: GdprConversationItem) => {
    const requesterEmail = getRequesterEmail(item);
    const isAnonymized = Boolean(item.pii_redacted_at);
    const isChecked = selectedConversationIds.has(item.id);
    return (
      <TableRow key={item.id}>
        <TableCell>
          <div className="flex items-center justify-center">
          <input
            type="checkbox"
            aria-label={`Select conversation ${item.id}`}
            checked={isChecked}
            onChange={(event) => toggleSelectedConversation(item.id, event.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          </div>
        </TableCell>
        <TableCell className="font-mono text-xs break-all">
          <div className="flex flex-wrap items-center gap-2">
            <span className="break-all">{item.id}</span>
          </div>
          {item.zendesk_ticket_id ? (
            <Badge variant="outline" className="ml-2">
              Zendesk #{item.zendesk_ticket_id}
            </Badge>
          ) : null}
        </TableCell>
        <TableCell className="truncate text-sm">
          {requesterEmail || (
            <span className="text-muted-foreground italic">
              Not on this row (matched via transcript text)
            </span>
          )}
        </TableCell>
        <TableCell className="truncate">
          <div className="flex flex-wrap gap-1">
            <Badge variant="default">{item.status ?? "—"}</Badge>
            {isAnonymized && (
              <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700">
                Redacted
              </Badge>
            )}
          </div>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
          {formatDate(item.created_at)}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
          {formatDate(item.updated_at)}
        </TableCell>
        <TableCell>
          <Button
            type="button"
            variant="default"
            size="sm"
            className="rounded-full"
            title="Open conversation"
            onClick={() => handleOpenConversation(item.id)}
            disabled={isOpeningTranscript}
          >
            <MessageCircle className="h-2 w-2" /> Open
          </Button>
        </TableCell>
      </TableRow>
    );
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);

  return (
    <PageLayout>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-amber-600" />
          <h1 className="text-2xl md:text-3xl font-bold animate-fade-down">
            GDPR Right-to-Erasure
          </h1>
        </div>
        <p className="text-sm md:text-base text-muted-foreground animate-fade-up">
          Search conversations by an end-user's email address and delete or
          anonymize them on request. The search matches the email captured by
          the Zendesk ticket node and falls back to full-text search over the
          transcript content.
        </p>
      </div>

      <Card className="p-4">
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-2 sm:flex-row sm:items-center"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="email"
              required
              autoComplete="off"
              placeholder="user@example.com"
              value={emailQuery}
              onChange={(event) => setEmailQuery(event.target.value)}
              className="w-full rounded-full border bg-white px-9 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <Button type="submit" className="rounded-full" disabled={loading}>
            <Search className="h-4 w-4" />
            Search
          </Button>
        </form>
        {activeEmail ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Showing results for <span className="font-medium">{activeEmail}</span>{" "}
            ({total} match{total === 1 ? "" : "es"}).
          </p>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            Enter an email address to begin. Results include conversations whose
            Zendesk PII matches and conversations whose transcript text
            mentions the email.
          </p>
        )}
      </Card>

      {activeEmail && (
        <>
          <Card className="p-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between px-2">
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={allOnPageSelected}
                    onChange={(event) => toggleSelectAllOnPage(event.target.checked)}
                    disabled={items.length === 0 || loading}
                    className="h-4 w-4 accent-primary"
                  />
                  Select <b>{selectedCount}</b> conversations
                </label>
              </div>
              <Button
                type="button"
                variant="destructive"
                className="rounded-full"
                disabled={selectedCount === 0 || loading}
                onClick={handleBulkDeleteClick}
                title="Delete selected conversations for GDPR"
              >
                Delete selected
              </Button>
            </div>
          </Card>

          <DataTable
            data={items}
            loading={loading}
            error={error}
            searchQuery={activeEmail}
            headers={headers}
            renderRow={renderRow}
            emptyMessage="No conversations found for this email."
            searchEmptyMessage="No conversations found for this email."
          />

          {total > PAGE_SIZE && (
            <PaginationBar
              total={total}
              pageSize={PAGE_SIZE}
              currentPage={safePage}
              pageItemCount={items.length}
              onPageChange={handlePageChange}
            />
          )}
        </>
      )}

      <GdprDeleteDialog
        isOpen={isDialogOpen}
        onOpenChange={handleDialogOpenChange}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        conversationId={conversationIdsToDelete.length === 1 ? conversationIdsToDelete[0] : null}
        conversationCount={conversationIdsToDelete.length}
        hardDeleteBlockedCount={finalizedConversationIdsSelected.size}
      />

      {isLiveTranscriptSelected ? (
        <ActiveConversationDialog
          transcript={selectedTranscript}
          isOpen={isTranscriptOpen}
          onOpenChange={(open) => {
            setIsTranscriptOpen(open);
            if (!open) setSelectedTranscript(null);
          }}
        />
      ) : (
        <TranscriptDialog
          transcript={selectedTranscript}
          isOpen={isTranscriptOpen}
          onOpenChange={(open) => {
            setIsTranscriptOpen(open);
            if (!open) setSelectedTranscript(null);
          }}
        />
      )}
    </PageLayout>
  );
}
