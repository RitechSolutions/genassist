import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/dialog";
import { Button } from "@/components/button";
import { Loader2, Send } from "lucide-react";
import { toast } from "react-hot-toast";
import { testDeploymentInference } from "@/services/localFineTune";
import type { LocalFineTuneDeployment } from "@/interfaces/localFineTune.interface";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface LocalFineTuneTestDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  deployment: LocalFineTuneDeployment;
}

export function LocalFineTuneTestDialog({
  isOpen,
  onOpenChange,
  deployment,
}: LocalFineTuneTestDialogProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const modelName = deployment.model_path?.split("/").filter(Boolean).pop() ?? deployment.model_path;

  const handleSend = async () => {
    const text = input.trim();
    if (!text || inFlight.current) return;

    inFlight.current = true;
    setLoading(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);

    try {
      const reply = await testDeploymentInference(deployment.id, text);
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 401) {
        toast.error("Unauthorized — the vLLM server may require auth or the session expired");
      } else if (status === 422 || status === 400) {
        toast.error("Bad request — check the model path is correct");
      } else {
        toast.error("Inference call failed");
      }
      setMessages((prev) => prev.slice(0, -1));
      setInput(text);
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[580px] p-0 flex flex-col" style={{ maxHeight: "80vh" }}>
        <DialogHeader className="p-5 pb-3 border-b shrink-0">
          <DialogTitle className="text-base">Test deployment</DialogTitle>
          <p className="text-xs text-muted-foreground mt-0.5 font-mono truncate">
            {modelName} · port {deployment.port}
          </p>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground text-center pt-8">
              Send a message to test the deployed model
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`rounded-xl px-4 py-2.5 text-sm max-w-[85%] whitespace-pre-wrap leading-relaxed ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground border border-border"
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-xl px-4 py-2.5 bg-muted border border-border">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-4 border-t shrink-0 flex gap-2 items-end">
          <textarea
            className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[40px] max-h-[120px]"
            rows={1}
            placeholder='Type a message and press Enter… (e.g. "Hello")'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <Button
            size="icon"
            className="h-10 w-10 shrink-0"
            onClick={handleSend}
            disabled={loading || !input.trim()}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}