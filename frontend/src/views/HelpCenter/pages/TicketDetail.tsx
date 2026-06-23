import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { Button } from "@/components/button";
import { Textarea } from "@/components/ui/textarea";
import {
  addTicketComment,
  getSupportTicket,
  listTicketComments,
} from "@/services/helpCenter";
import { SupportTicket, SupportTicketComment } from "@/interfaces/helpCenter.interface";
import { TicketStatusBadge } from "../components/TicketStatusBadge";
import { PageListSkeleton } from "@/components/skeletons";
import toast from "react-hot-toast";
import { AlertCircle, ChevronLeft, LifeBuoy } from "lucide-react";

function HtmlBlock({ label, html }: { label: string; html?: string | null }) {
  const isEmpty =
    !html || (html.replace(/<[^>]*>/g, "").trim() === "" && !/<img/i.test(html));
  if (isEmpty) return null;
  return (
    <div>
      <div className="text-sm font-medium text-gray-700 mb-1">{label}</div>
      <div
        className="text-sm text-gray-800 leading-relaxed [&_a]:text-primary [&_a]:underline [&_img]:max-w-full [&_img]:h-auto [&_img]:rounded-md [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}

export default function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [comments, setComments] = useState<SupportTicketComment[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!ticketId) return;
    setLoading(true);
    try {
      const [t, c] = await Promise.all([
        getSupportTicket(ticketId),
        listTicketComments(ticketId),
      ]);
      setTicket(t);
      setComments(c);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleComment = async () => {
    if (!ticketId || !commentBody.trim()) return;
    setSubmitting(true);
    try {
      await addTicketComment(ticketId, commentBody.trim());
      setCommentBody("");
      toast.success("Comment added");
      await load();
    } catch {
      toast.error("Failed to add comment");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <PageLayout>
        <div className="rounded-lg border bg-white overflow-hidden">
          <PageListSkeleton variant="rich" bordered={false} />
        </div>
      </PageLayout>
    );
  }

  if (!ticket) {
    return (
      <PageLayout>
        <div className="rounded-lg border bg-white flex flex-col items-center justify-center py-16 gap-4 text-center">
          <div className="rounded-full bg-gray-100 p-4">
            <LifeBuoy className="h-12 w-12 text-gray-400" />
          </div>
          <h3 className="font-medium text-lg">Ticket not found</h3>
          <p className="text-sm text-gray-500 max-w-md px-4">
            This ticket may have been removed or you do not have access to view it.
          </p>
          <Button asChild className="rounded-full">
            <Link to="/help-center">Back to Help Center</Link>
          </Button>
        </div>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="space-y-6">
        <div className="flex items-center">
          <Button variant="ghost" size="icon" asChild className="mr-2">
            <Link to="/help-center">
              <ChevronLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div className="min-w-0 flex-1">
            <h2 className="text-2xl font-bold tracking-tight break-words">{ticket.title}</h2>
            <div className="flex flex-wrap gap-2 mt-2 items-center text-sm text-gray-500">
              <TicketStatusBadge status={ticket.status} />
              <span className="capitalize">{ticket.ticket_type}</span>
              {ticket.vote_count > 1 && <span>{ticket.vote_count} reports</span>}
            </div>
          </div>
        </div>

        {ticket.sync_error && (
          <div className="flex items-center gap-2 p-3 text-destructive bg-destructive/10 rounded-md">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p className="text-sm font-medium">Sync error: {ticket.sync_error}</p>
          </div>
        )}

        {ticket.duplicate_of_id && (
          <p className="text-sm text-gray-500">
            Linked duplicate of{" "}
            <Link className="underline font-medium" to={`/help-center/${ticket.duplicate_of_id}`}>
              another ticket
            </Link>
          </p>
        )}

        <div className="rounded-lg border bg-white">
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="text-lg font-semibold">Details</h3>
                <p className="text-sm text-gray-500 mt-1">Issue details submitted to Help Center.</p>
              </div>
              <div className="md:col-span-2 space-y-5">
                {ticket.ticket_type === "bug" ? (
                  <>
                    <HtmlBlock label="Repro steps" html={ticket.repro_steps} />
                    <HtmlBlock label="System info" html={ticket.system_info} />
                    <HtmlBlock label="Acceptance criteria" html={ticket.acceptance_criteria} />
                  </>
                ) : ticket.ticket_type === "feature" ? (
                  <>
                    <HtmlBlock label="Description" html={ticket.description} />
                    <HtmlBlock label="Acceptance criteria" html={ticket.acceptance_criteria} />
                  </>
                ) : (
                  <HtmlBlock label="Description" html={ticket.description} />
                )}
              </div>
            </div>
          </div>

          <div className="border-t border-gray-200" />

          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h3 className="text-lg font-semibold">Comments</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Discussion is synced to Azure DevOps when linked.
                </p>
              </div>
              <div className="md:col-span-2 space-y-4">
                {comments.length === 0 ? (
                  <p className="text-sm text-gray-500">No comments yet. Be the first to reply.</p>
                ) : (
                  <div className="space-y-3">
                    {comments.map((c) => (
                      <div key={c.id} className="rounded-md border bg-gray-50 p-3 text-sm">
                        <p className="whitespace-pre-wrap">{c.body}</p>
                        {c.created_at && (
                          <p className="text-xs text-gray-500 mt-2">
                            {new Date(c.created_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <Textarea
                  value={commentBody}
                  onChange={(e) => setCommentBody(e.target.value)}
                  placeholder="Add a comment..."
                  rows={3}
                />
                <Button
                  onClick={handleComment}
                  disabled={submitting || !commentBody.trim()}
                  className="rounded-full"
                >
                  {submitting ? "Posting..." : "Post comment"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
