import React, { useState } from "react";
import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import FieldChangeRow from "../diff/FieldChangeRow";
import { PROMPT_DIFF_TIMEOUT_MS, PROMPT_MIN_SIMILARITY } from "./promptDiff";

type SuggestionView = "diff" | "edit";

interface SuggestionDiffEditorProps {
  /** The prompt the optimizer rewrote, so the diff reads optimized-from → saved */
  before: string;
  suggestion: string;
  edited: boolean;
  onChange: (text: string) => void;
}

/** The suggestion as a diff against the prompt it came from, or as an editor */
export const SuggestionDiffEditor: React.FC<SuggestionDiffEditorProps> = ({
  before,
  suggestion,
  edited,
  onChange,
}) => {
  const [view, setView] = useState<SuggestionView>("diff");

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label className="text-sm font-medium">
          Suggested Prompt
          {edited && (
            <span className="text-muted-foreground font-normal"> · edited</span>
          )}
        </Label>
        <Tabs value={view} onValueChange={(v) => setView(v as SuggestionView)}>
          <TabsList className="h-9">
            <TabsTrigger value="diff" className="gap-1.5 px-3 text-xs">
              Diff
            </TabsTrigger>
            <TabsTrigger value="edit" className="gap-1.5 px-3 text-xs">
              Edit
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {view === "diff" ? (
        <div className="border rounded max-h-48 overflow-y-auto">
          {before === suggestion ? (
            <div className="px-3 py-2 text-xs italic text-muted-foreground">
              No differences
            </div>
          ) : (
            <FieldChangeRow
              variant="embedded"
              change={{
                key: "Suggested prompt",
                before,
                after: suggestion,
              }}
              minSimilarity={PROMPT_MIN_SIMILARITY}
              diffTimeoutMs={PROMPT_DIFF_TIMEOUT_MS}
            />
          )}
        </div>
      ) : (
        <RichTextarea
          value={suggestion}
          onChange={(e) => onChange(e.target.value)}
          rows={12}
          className="w-full font-mono text-sm"
        />
      )}
    </div>
  );
};
