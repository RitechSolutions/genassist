import { useEffect, useState, useMemo } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { fetchAgentResponseLog, AgentResponseLog } from "@/services/transcripts";
import JsonViewer from "@/components/JsonViewer";
import { extractReferencedArticles } from "@/helpers/referencedArticles";
import { TruncatedText } from "@/components/TruncatedText";

type AgentResponseLogDialogProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  messageId?: string | null;
};

/** Parsed shape from API: id, conversation_id, transcript_message_id, raw_response (string), logged_at */
type AgentResponseLogEntry = AgentResponseLog & {
  raw_response?: string;
  logged_at?: string;
};

function parseRawResponse(raw: string | undefined): unknown | null {
  if (raw == null || typeof raw !== "string" || !raw.trim()) return null;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

export function AgentResponseLogDialog({
  isOpen,
  onOpenChange,
  messageId,
}: AgentResponseLogDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AgentResponseLogEntry | null>(null);

  const parsedResponse = useMemo(() => parseRawResponse(data?.raw_response), [data?.raw_response]);
  const references = useMemo(() => extractReferencedArticles(parsedResponse), [parsedResponse]);

  useEffect(() => {
    if (!isOpen || !messageId) {
      setLoading(false);
      setError(null);
      setData(null);
      return;
    }

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);
      setData(null);

      const result = await fetchAgentResponseLog(messageId);

      if (cancelled) return;

      if (!result) {
        setError("No agent response log found for this message.");
        setLoading(false);
        return;
      }

      setData(result as AgentResponseLogEntry);
      setLoading(false);
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [isOpen, messageId]);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        onOpenChange(open);
        if (!open) {
          setLoading(false);
          setError(null);
          setData(null);
        }
      }}
    >
      <DialogContent className="w-[95vw] max-w-[min(1100px,95vw)] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Agent response log</DialogTitle>
        </DialogHeader>
        <div className="mt-2 flex flex-col gap-4 overflow-y-auto min-h-0">
          {loading && (
            <p className="text-sm text-muted-foreground">Loading...</p>
          )}
          {!loading && error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          {!loading && !error && data && (
            <>
              <div className="text-xs text-muted-foreground space-y-1">
                {data.id != null && (
                  <div><span className="font-medium">ID:</span> {String(data.id)}</div>
                )}
                {data.conversation_id != null && (
                  <div><span className="font-medium">Conversation ID:</span> {String(data.conversation_id)}</div>
                )}
                {data.transcript_message_id != null && (
                  <div><span className="font-medium">Message ID:</span> {String(data.transcript_message_id)}</div>
                )}
                {data.logged_at != null && (
                  <div><span className="font-medium">Logged at:</span> {new Date(data.logged_at).toLocaleString()}</div>
                )}
              </div>
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-1">Referenced articles</div>
                {references.kbCalls === 0 ? (
                  <p className="text-xs text-muted-foreground">No knowledge-base lookup recorded in this response's log.</p>
                ) : references.articles.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {references.failedCalls === references.kbCalls
                      ? "The knowledge-base lookup failed, so no articles were returned."
                      : "The knowledge base was queried but returned no results."}
                  </p>
                ) : (
                  <ul className="space-y-1.5 text-sm">
                    {references.articles.map((article) => (
                      <li key={article.id} className="flex items-baseline gap-x-2">
                        <TruncatedText className="min-w-0">
                          {article.title && <span className="mr-2 font-medium">{article.title}</span>}
                          <code className="text-xs text-muted-foreground">{article.id}</code>
                        </TruncatedText>
                        {article.score != null && (
                          <span className="shrink-0 text-xs text-muted-foreground">score {article.score.toFixed(3)}</span>
                        )}
                        {article.kbId && (
                          <span className="flex shrink-0 items-baseline gap-1 text-xs text-muted-foreground">
                            KB <TruncatedText className="max-w-[6rem]">{article.kbId}</TruncatedText>
                          </span>
                        )}
                        {article.legacy && (
                          <span className="shrink-0 text-xs italic text-muted-foreground">parsed from log text</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <div className="text-xs font-semibold text-muted-foreground mb-1">Response (JSON)</div>
                {parsedResponse != null && typeof parsedResponse === "object" ? (
                  <div className="border border-border rounded-md overflow-hidden">
                    <JsonViewer
                      data={parsedResponse as unknown as never}
                      onCopy={(d) => navigator.clipboard.writeText(JSON.stringify(d, null, 2))}
                    />
                  </div>
                ) : (
                  <pre className="text-xs whitespace-pre-wrap bg-muted border border-border p-3 rounded-md max-h-[300px] overflow-auto">
                    {data.raw_response ?? "—"}
                  </pre>
                )}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

