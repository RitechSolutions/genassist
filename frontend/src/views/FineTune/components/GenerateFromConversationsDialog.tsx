import { useCallback, useEffect, useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/dialog";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { ChevronDown, ChevronRight, Download, Loader2, Upload } from "lucide-react";
import { toast } from "react-hot-toast";
import { fetchConversationById, fetchTranscripts } from "@/services/transcripts";
import {
  downloadGeneratedTrainingFile,
  generateTrainingFileFromConversations,
} from "@/services/openaiFineTune";
import type { BackendTranscript, TranscriptEntry } from "@/interfaces/transcript.interface";
import type { OpenAIFileItem } from "@/interfaces/fineTune.interface";

const PAGE_SIZE = 20;

interface Props {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  fileType: "training" | "validation";
  onFileGenerated: (file: { id: string; name: string }) => void;
}

export function GenerateFromConversationsDialog({
  isOpen,
  onOpenChange,
  fileType,
  onFileGenerated,
}: Props) {
  const [conversations, setConversations] = useState<BackendTranscript[]>([]);
  const [convPage, setConvPage] = useState(0);
  const [convTotal, setConvTotal] = useState(0);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [convIdSuffix, setConvIdSuffix] = useState("");
  const idSuffixDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [expandedConvId, setExpandedConvId] = useState<string | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<TranscriptEntry[]>([]);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  const [selectedConvIds, setSelectedConvIds] = useState<Set<string>>(new Set());
  const [isDownloading, setIsDownloading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const loadConversations = useCallback(async (page: number, idSuffix: string) => {
    setIsLoadingConversations(true);
    try {
      const result = await fetchTranscripts({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        id_suffix: idSuffix || undefined,
      });
      setConversations(result.items ?? []);
      setConvTotal(result.total ?? 0);
    } catch {
      toast.error("Failed to load conversations");
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      setConvPage(0);
      void loadConversations(0, "");
    }
  }, [isOpen, loadConversations]);

  const handleConvIdSuffixChange = (value: string) => {
    setConvIdSuffix(value);
    if (idSuffixDebounceRef.current) clearTimeout(idSuffixDebounceRef.current);
    idSuffixDebounceRef.current = setTimeout(() => {
      setConvPage(0);
      void loadConversations(0, value);
    }, 700);
  };

  const handlePageChange = (newPage: number) => {
    setConvPage(newPage);
    void loadConversations(newPage, convIdSuffix);
  };

  const toggleExpandConversation = async (convId: string) => {
    if (expandedConvId === convId) {
      setExpandedConvId(null);
      setExpandedMessages([]);
      return;
    }
    setExpandedConvId(convId);
    setExpandedMessages([]);
    setIsLoadingMessages(true);
    try {
      const conv = await fetchConversationById(convId);
      setExpandedMessages((conv as { messages?: TranscriptEntry[] }).messages ?? []);
    } catch {
      toast.error("Failed to load messages");
    } finally {
      setIsLoadingMessages(false);
    }
  };

  const toggleSelectConv = (convId: string) => {
    setSelectedConvIds((prev) => {
      const next = new Set(prev);
      if (next.has(convId)) next.delete(convId);
      else next.add(convId);
      return next;
    });
  };

  const handleDownload = async () => {
    if (selectedConvIds.size === 0) {
      toast.error("Please select at least one conversation");
      return;
    }
    setIsDownloading(true);
    try {
      const blob = await downloadGeneratedTrainingFile({
        conversation_ids: Array.from(selectedConvIds),
      });
      // Trigger browser download
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `training_${fileType}.jsonl`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("File downloaded — review it, then upload when ready");
    } catch {
      toast.error("Failed to generate file");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleUploadToOpenAI = async () => {
    if (selectedConvIds.size === 0) return;
    setIsUploading(true);
    try {
      const result: OpenAIFileItem = await generateTrainingFileFromConversations({
        conversation_ids: Array.from(selectedConvIds),
        upload_to_openai: true,
      });
      const fileLabel = fileType === "training" ? "Training" : "Validation";
      toast.success(`${fileLabel} file uploaded to OpenAI`);
      onFileGenerated({ id: result.id, name: result.filename ?? `generated_${fileType}.jsonl` });
      onOpenChange(false);
      resetState();
    } catch {
      toast.error("Failed to upload file");
    } finally {
      setIsUploading(false);
    }
  };

  const resetState = () => {
    setConvIdSuffix("");
    setConvPage(0);
    setConversations([]);
    setConvTotal(0);
    setSelectedConvIds(new Set());
    setExpandedConvId(null);
    setExpandedMessages([]);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) resetState();
    onOpenChange(open);
  };

  const fileTypeLabel = fileType === "training" ? "Training" : "Validation";
  const isBusy = isDownloading || isUploading;

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[95vw] max-w-2xl h-[85vh] max-h-[85vh] overflow-hidden p-0 flex flex-col">
        <DialogHeader className="px-6 pt-6 pb-2 shrink-0">
          <DialogTitle>Generate {fileTypeLabel} File from Conversations</DialogTitle>
        </DialogHeader>

        <div className="px-6 pb-3 shrink-0 flex gap-3 items-end">
          <div className="flex-1">
            <Label className="text-xs mb-1 block">Search by ID</Label>
            <Input
              placeholder="e.g. a3f2"
              value={convIdSuffix}
              onChange={(e) => handleConvIdSuffixChange(e.target.value)}
              maxLength={36}
            />
          </div>
          {selectedConvIds.size > 0 && (
            <span className="text-xs text-muted-foreground pb-2">
              {selectedConvIds.size} selected
            </span>
          )}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto px-6">
          {isLoadingConversations ? (
            <div className="text-sm text-muted-foreground py-4">Loading conversations…</div>
          ) : conversations.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4">No conversations found.</div>
          ) : (
            <div className="space-y-2 py-2">
              {conversations.map((conv) => {
                const isExpanded = expandedConvId === conv.id;
                const isSelected = selectedConvIds.has(conv.id);
                return (
                  <div
                    key={conv.id}
                    className={`border rounded overflow-hidden transition-colors ${
                      isSelected ? "border-primary bg-primary/5" : ""
                    }`}
                  >
                    <div className="p-3 flex items-center justify-between gap-3">
                      <button
                        className="flex items-center gap-2 min-w-0 text-left flex-1"
                        onClick={() => void toggleExpandConversation(conv.id)}
                      >
                        <ChevronDown
                          className={`h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform ${
                            isExpanded ? "" : "-rotate-90"
                          }`}
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-medium">#{conv.id.slice(-4)}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {conv.conversation_date
                              ? new Date(conv.conversation_date).toLocaleDateString()
                              : "—"}{" "}
                            · {conv.word_count ?? 0} words · {conv.status}
                          </p>
                        </div>
                      </button>
                      <Button
                        size="sm"
                        variant={isSelected ? "default" : "outline"}
                        onClick={() => toggleSelectConv(conv.id)}
                        disabled={isBusy}
                      >
                        {isSelected ? "Selected" : "Select"}
                      </Button>
                    </div>

                    {isExpanded && (
                      <div className="border-t bg-muted/30 px-3 py-2 max-h-48 overflow-y-auto space-y-1.5">
                        {isLoadingMessages ? (
                          <p className="text-xs text-muted-foreground">Loading messages…</p>
                        ) : expandedMessages.length === 0 ? (
                          <p className="text-xs text-muted-foreground">No messages found.</p>
                        ) : (
                          expandedMessages.map((msg, idx) => {
                            const isAgent = msg.speaker?.toLowerCase() === "agent";
                            return (
                              <div
                                key={(msg as { id?: string }).id ?? idx}
                                className={`flex flex-col ${isAgent ? "items-end" : "items-start"}`}
                              >
                                <span className="text-[10px] font-medium mb-0.5 capitalize">
                                  {msg.speaker}
                                </span>
                                <div
                                  className={`max-w-[80%] rounded-lg px-2.5 py-1.5 text-xs leading-tight break-words ${
                                    isAgent
                                      ? "bg-blue-500 text-white rounded-tr-none"
                                      : "bg-muted text-foreground rounded-tl-none"
                                  }`}
                                >
                                  {msg.text}
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <DialogFooter className="border-t px-6 py-3 shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{convTotal} total</span>
            <Button
              variant="outline"
              size="sm"
              disabled={convPage === 0 || isBusy}
              onClick={() => handlePageChange(convPage - 1)}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">Page {convPage + 1}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={(convPage + 1) * PAGE_SIZE >= convTotal || isBusy}
              onClick={() => handlePageChange(convPage + 1)}
            >
              Next
              <ChevronRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenChange(false)}
              disabled={isBusy}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={isBusy || selectedConvIds.size === 0}
            >
              {isDownloading
                ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                : <Download className="w-4 h-4 mr-2" />}
              Download
            </Button>
            <Button
              size="sm"
              onClick={handleUploadToOpenAI}
              disabled={isBusy || selectedConvIds.size === 0}
            >
              {isUploading
                ? <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                : <Upload className="w-4 h-4 mr-2" />}
              Upload to OpenAI
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}