import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Save } from "lucide-react";
import { Button } from "@/components/button";
import { Input } from "@/components/input";
import { Label } from "@/components/label";
import { Textarea } from "@/components/textarea";
import { createPromptVersion } from "@/services/promptEditor";

interface EditorTabProps {
  workflowId: string;
  nodeId: string;
  promptField: string;
  value: string;
  onChange: (newValue: string) => void;
}

export const EditorTab: React.FC<EditorTabProps> = ({
  workflowId,
  nodeId,
  promptField,
  value,
  onChange,
}) => {
  const [versionLabel, setVersionLabel] = useState("");
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const queryClient = useQueryClient();

  const saveVersionMutation = useMutation({
    mutationFn: async () => {
      setStatus(null);
      const result = await createPromptVersion(workflowId, nodeId, promptField, {
        content: value,
        label: versionLabel || undefined,
      });
      if (!result) throw new Error("Server returned empty response — check permissions.");
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["promptVersions", workflowId, nodeId, promptField],
      });
      setVersionLabel("");
      setStatus({ type: "success", message: "Version saved" });
    },
    onError: (err) => {
      setStatus({
        type: "error",
        message: `Failed to save: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    },
  });

  return (
    <div className="space-y-4 pt-4">
      <div className="space-y-2">
        <Label>Prompt Content</Label>
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter your prompt..."
          rows={14}
          className="w-full font-mono text-sm"
        />
        <div className="text-xs text-muted-foreground text-right">
          {value.length} characters
        </div>
      </div>

      {status && (
        <div
          className={`flex items-center gap-2 text-sm rounded-md px-3 py-2 ${
            status.type === "error"
              ? "text-destructive bg-destructive/10 border border-destructive/20"
              : "text-green-700 bg-green-50 border border-green-200"
          }`}
        >
          {status.type === "error" ? (
            <AlertCircle className="h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          )}
          <span>{status.message}</span>
        </div>
      )}

      <div className="flex items-end gap-3 border-t pt-4">
        <div className="flex-1 space-y-2">
          <Label htmlFor="version-label">Version Label (optional)</Label>
          <Input
            id="version-label"
            value={versionLabel}
            onChange={(e) => setVersionLabel(e.target.value)}
            placeholder="e.g., Added tone instructions"
          />
        </div>
        <Button
          onClick={() => saveVersionMutation.mutate()}
          disabled={!value.trim() || saveVersionMutation.isPending}
        >
          <Save className="h-4 w-4 mr-2" />
          {saveVersionMutation.isPending ? "Saving..." : "Save Version"}
        </Button>
      </div>
    </div>
  );
};
