import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import { Search, Trash2, ShieldAlert } from "lucide-react";
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

  const [conversationToDelete, setConversationToDelete] =
    useState<GdprConversationItem | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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
      } catch (err) {
        const axiosError = err as AxiosError<{ error?: string }>;
        const apiMessage =
          axiosError.response?.data?.error ??
          (err instanceof Error ? err.message : "Failed to search conversations.");
        setError(apiMessage);
        setItems([]);
        setTotal(0);
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
    if (activeEmail) {
      performSearch(activeEmail, page);
    }
  };

  const handleDeleteClick = (item: GdprConversationItem) => {
    setConversationToDelete(item);
    setIsDialogOpen(true);
  };

  const handleDeleteConfirm = async (mode: GdprDeleteMode) => {
    if (!conversationToDelete) return;
    setIsDeleting(true);
    try {
      await deleteConversationForGdpr(conversationToDelete.id, mode);
      toast.success(
        mode === "hard"
          ? "Conversation permanently deleted."
          : mode === "anonymize"
            ? "Conversation anonymized."
            : "Conversation soft-deleted (PII scrubbed).",
      );
      setIsDialogOpen(false);
      setConversationToDelete(null);
      // Refetch to reflect the new state. ``soft`` rows disappear from the
      // default list; ``anonymize`` rows stay but lose PII; ``hard`` rows are
      // gone from the list entirely.
      if (activeEmail) {
        await performSearch(activeEmail, currentPage);
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ error?: string }>;
      const apiMessage =
        axiosError.response?.data?.error ??
        (err instanceof Error ? err.message : "Failed to delete conversation.");
      toast.error(apiMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const headers = [
    "Conversation",
    "Email (PII)",
    "Status",
    "Created",
    "Updated",
    "Action",
  ];

  const renderRow = (item: GdprConversationItem) => {
    const requesterEmail = getRequesterEmail(item);
    const isAnonymized = Boolean(item.pii_redacted_at);
    return (
      <TableRow key={item.id}>
        <TableCell className="font-mono text-xs break-all">
          {item.id}
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
            variant="outline"
            size="sm"
            onClick={() => handleDeleteClick(item)}
            className="rounded-full"
            title="Delete conversation for GDPR"
          >
            <Trash2 className="h-4 w-4" />
            Delete
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
        onOpenChange={setIsDialogOpen}
        onConfirm={handleDeleteConfirm}
        isInProgress={isDeleting}
        conversationId={conversationToDelete?.id ?? null}
      />
    </PageLayout>
  );
}
