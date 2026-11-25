import React, { useId } from "react";
import { Loader2, Play } from "lucide-react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
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
    nliSelected,
    nliScoreText,
    setNliScoreText,
    nliScoreIssue,
    judgeSelected,
    rubricText,
    setRubricText,
    rubricIssue,
    judgeScoreText,
    setJudgeScoreText,
    judgeScoreIssue,
    judgeSeesExpected,
    setJudgeSeesExpected,
    casesToCheck,
    setCasesToCheck,
    split,
    splitActive,
    setSplitEnabled,
    evalRun,
    evalStale,
    evaluate,
  } = measurement;
  const id = useId();

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
                id={`${id}-${technique}`}
                checked={selectedTechniques.includes(technique)}
                onCheckedChange={() => toggleTechnique(technique)}
              />
              <Label
                htmlFor={`${id}-${technique}`}
                className="text-sm cursor-pointer"
              >
                {methodLabel(technique)}
              </Label>
            </div>
          ))}
        </div>

        {notContainsSelected && (
          <div className="space-y-2">
            <Label htmlFor={`${id}-phrases`} className="text-sm">
              Forbidden phrases (one per line)
            </Label>
            <RichTextarea
              id={`${id}-phrases`}
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

        {nliSelected && (
          <div className="space-y-2">
            <Label htmlFor={`${id}-nli-score`} className="text-sm">
              Minimum entailment score (0-1)
            </Label>
            <RichInput
              id={`${id}-nli-score`}
              inputMode="decimal"
              value={nliScoreText}
              onChange={(e) => setNliScoreText(e.target.value)}
              placeholder="0.5"
              className="w-28 text-sm"
            />
            <p className="text-xs text-muted-foreground">
              How much of the reply the expected output must back up. Lower
              accepts replies that say more than the expected text.
            </p>
            {nliScoreIssue && (
              <p className="text-xs text-destructive">{nliScoreIssue}</p>
            )}
          </div>
        )}

        {judgeSelected && (
          <div className="space-y-2">
            <Label htmlFor={`${id}-rubric`} className="text-sm">
              Judge rubric
            </Label>
            <RichTextarea
              id={`${id}-rubric`}
              value={rubricText}
              onChange={(e) => setRubricText(e.target.value)}
              placeholder="Score from 0.0 to 1.0 how well the reply answers the question."
              size="description"
              className="text-sm"
            />
            <Label htmlFor={`${id}-judge-score`} className="text-sm">
              Minimum judge score (0-1)
            </Label>
            <RichInput
              id={`${id}-judge-score`}
              inputMode="decimal"
              value={judgeScoreText}
              onChange={(e) => setJudgeScoreText(e.target.value)}
              placeholder="0.5"
              className="w-28 text-sm"
            />
            <div className="flex items-center gap-2">
              <Switch
                id={`${id}-judge-expected`}
                checked={judgeSeesExpected}
                onCheckedChange={setJudgeSeesExpected}
              />
              <Label
                htmlFor={`${id}-judge-expected`}
                className="text-sm cursor-pointer"
              >
                Show the judge the expected output
              </Label>
            </div>
            <p className="text-xs text-muted-foreground">
              The evaluation model grades each reply against the rubric, one call
              per case. Turn the switch on to show the judge the expected output
              as its SOURCE; cases without one are then skipped.
            </p>
            {rubricIssue && (
              <p className="text-xs text-destructive">{rubricIssue}</p>
            )}
            {judgeScoreIssue && (
              <p className="text-xs text-destructive">{judgeScoreIssue}</p>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Label htmlFor={`${id}-cases`} className="text-sm">
              Cases to check
            </Label>
            <Select
              value={String(casesToCheck)}
              onValueChange={(v) => setCasesToCheck(Number(v))}
              disabled={splitActive}
            >
              <SelectTrigger id={`${id}-cases`} className="w-20">
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
                id={`${id}-holdout`}
                checked={splitActive}
                disabled={!split.feasible}
                onCheckedChange={setSplitEnabled}
              />
              <Label
                htmlFor={`${id}-holdout`}
                className="text-sm cursor-pointer"
              >
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
        <p className="text-xs text-muted-foreground">
          Variables such as {"{{name}}"} are sent as written.
        </p>
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
