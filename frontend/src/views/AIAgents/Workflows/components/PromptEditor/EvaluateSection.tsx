import React from "react";
import { Loader2, Play } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichTextarea } from "@/components/richTextarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Switch } from "@/components/switch";
import { methodLabel } from "@/views/TestSuites/helpers/methodLabels";
import {
  CASES_TO_CHECK_OPTIONS,
  PROMPT_CHECK_TECHNIQUES,
} from "../../utils/promptEditorTechniques";
import { GateTooltip } from "./GateTooltip";
import { PromptEvalResults } from "./PromptEvalResults";
import { ProviderSelect } from "./ProviderSelect";
import type { PromptMeasurementState } from "./usePromptMeasurement";

interface EvaluateSectionProps {
  measurement: PromptMeasurementState;
}

/** Scores the draft against the gold dataset. The run button sits above its results */
export const EvaluateSection: React.FC<EvaluateSectionProps> = ({
  measurement,
}) => {
  const {
    providers,
    activeEvalProviderId,
    setEvalProviderId,
    providerStatus,
    selectedTechniques,
    toggleTechnique,
    notContainsSelected,
    phrasesText,
    setPhrasesText,
    phrasesIssue,
    casesToCheck,
    setCasesToCheck,
    split,
    splitActive,
    setSplitEnabled,
    evalRun,
    evalStale,
    evaluate,
  } = measurement;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3">
        <ProviderSelect
          label="Evaluation model"
          providers={providers}
          value={activeEvalProviderId}
          onChange={setEvalProviderId}
          isEmpty={providerStatus === "empty"}
        />

        <div className="flex flex-wrap gap-4">
          {PROMPT_CHECK_TECHNIQUES.map((technique) => (
            <div key={technique} className="flex items-center gap-2">
              <Switch
                checked={selectedTechniques.includes(technique)}
                onCheckedChange={() => toggleTechnique(technique)}
              />
              <Label className="text-sm cursor-pointer">
                {methodLabel(technique)}
              </Label>
            </div>
          ))}
        </div>

        {notContainsSelected && (
          <div className="space-y-2">
            <Label className="text-sm">Forbidden phrases (one per line)</Label>
            <RichTextarea
              value={phrasesText}
              onChange={(e) => setPhrasesText(e.target.value)}
              placeholder={"discount\nguarantee"}
              size="description"
              className="text-sm"
            />
            {phrasesIssue && (
              <p className="text-xs text-destructive">{phrasesIssue}</p>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="text-sm">Cases to check</Label>
            <Select
              value={String(casesToCheck)}
              onValueChange={(v) => setCasesToCheck(Number(v))}
              disabled={splitActive}
            >
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CASES_TO_CHECK_OPTIONS.map((option) => (
                  <SelectItem key={option} value={String(option)}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <GateTooltip reason={split.feasible ? null : split.reason}>
            <span className="flex items-center gap-2">
              <Switch
                checked={splitActive}
                disabled={!split.feasible}
                onCheckedChange={setSplitEnabled}
              />
              <Label className="text-sm cursor-pointer">
                Hold out cases
                {split.feasible && (
                  <span className="text-muted-foreground">
                    {" "}
                    ({split.dev.length} development · {split.holdout.length}{" "}
                    hold-out)
                  </span>
                )}
              </Label>
            </span>
          </GateTooltip>
        </div>

        <div className="flex justify-end">
          <GateTooltip reason={evaluate.reason}>
            <Button
              size="sm"
              variant="default"
              onClick={evaluate.run}
              disabled={!evaluate.enabled || evaluate.pending}
            >
              {evaluate.pending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              {evaluate.pending ? "Evaluating..." : "Run Evaluation"}
            </Button>
          </GateTooltip>
        </div>
      </div>

      {evalRun && (
        <PromptEvalResults
          results={evalRun.results}
          stale={evalStale}
          providerFallback={evalRun.providerFallback}
          leaky={evalRun.leaky}
        />
      )}
    </div>
  );
};
