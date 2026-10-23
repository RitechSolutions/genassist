import { useState } from "react";
import toast from "react-hot-toast";
import { NotebookPen } from "lucide-react";

import { Button } from "@/components/button";
import { Textarea } from "@/components/ui/textarea";

import { extractErrorMessage } from "@/helpers/apiError";
import { formatDateTime } from "@/helpers/utils";
import { useAddIssueNote, useIssueNotes } from "../hooks/useReportedFeedback";
import { SectionLabel } from "./SectionLabel";

export function NotesSection({
  feedbackId,
  canTriage,
}: {
  feedbackId: string;
  canTriage: boolean;
}) {
  const [noteDraft, setNoteDraft] = useState("");

  const {
    data: notes = [],
    isLoading: notesLoading,
    isError: notesError,
  } = useIssueNotes(feedbackId);

  const addNote = useAddIssueNote(feedbackId);

  const submitNote = () => {
    const body = noteDraft.trim();
    if (!body || addNote.isPending) return;
    void addNote.mutateAsync(body).then(
      () => {
        setNoteDraft((current) => (current.trim() === body ? "" : current));
        toast.success("Note added");
      },
      (err) => toast.error(extractErrorMessage(err, "Failed to add note")),
    );
  };

  return (
    <section>
      <SectionLabel icon={NotebookPen}>Notes</SectionLabel>
      {notesLoading ? (
        <p className="text-sm text-muted-foreground">Loading notes...</p>
      ) : notesError ? (
        <p className="text-sm text-red-600 dark:text-red-400">
          Couldn't load the notes.
        </p>
      ) : notes.length === 0 ? (
        <p className="text-sm text-muted-foreground">No notes yet</p>
      ) : (
        <ol className="space-y-2">
          {notes.map((note) => (
            <li key={note.id} className="rounded-lg border bg-muted/40 p-3">
              <div className="mb-1 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  {note.author_username ?? "Unknown user"}
                </span>
                {" · "}
                {formatDateTime(note.created_at)}
              </div>
              <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                {note.body}
              </div>
            </li>
          ))}
        </ol>
      )}
      {canTriage && (
        <div className="mt-3 space-y-2">
          <Textarea
            rows={2}
            maxLength={5000}
            placeholder="Add a note about what was changed and how"
            aria-label="New note"
            value={noteDraft}
            onChange={(e) => setNoteDraft(e.target.value)}
          />
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="rounded-full"
              disabled={!noteDraft.trim() || addNote.isPending}
              onClick={submitNote}
            >
              {addNote.isPending ? "Adding..." : "Add note"}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
