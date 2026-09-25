import React from "react";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/switch";
import { Plus, Trash2 } from "lucide-react";
import type { JudgeRuleDraft, JudgeRuleSource } from "@/interfaces/testEvaluation.interface";

export interface JudgeRubricPreset {
  key: string;
  label: string;
  rubric: string;
  sourceType: JudgeRuleSource;
}

export const newJudgeRule = (): JudgeRuleDraft => ({
  label: "",
  rubric: "",
  minScore: "0.5",
  sourceType: "none",
  sourceField: "",
});

// A score field is valid when empty (a default applies) or a number in [0, 1].
const isValidScore = (text: string): boolean => {
  if (text.trim() === "") return true;
  const value = Number(text);
  return Number.isFinite(value) && value >= 0 && value <= 1;
};

interface JudgeRuleRowProps {
  rule: JudgeRuleDraft;
  index: number;
  presets: JudgeRubricPreset[];
  onChange: (patch: Partial<JudgeRuleDraft>) => void;
  onRemove: () => void;
  canRemove: boolean;
}

const JudgeRuleRow: React.FC<JudgeRuleRowProps> = ({
  rule,
  index,
  presets,
  onChange,
  onRemove,
  canRemove,
}) => (
  <div className="rounded-lg border p-3 space-y-3">
    <div className="flex items-center justify-between">
      <span className="text-xs font-medium text-muted-foreground">
        {rule.label.trim() ? rule.label : `Rule ${index + 1}`}
      </span>
      {canRemove && (
        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={onRemove}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
    <div>
      <Label className="text-xs">Rubric *</Label>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {presets.map((preset) => (
          <Button
            key={preset.key}
            variant="outline"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() =>
              onChange({
                label: preset.label,
                rubric: preset.rubric,
                sourceType: preset.sourceType,
              })
            }
          >
            {preset.label}
          </Button>
        ))}
      </div>
      <Textarea
        value={rule.rubric}
        onChange={(e) => onChange({ rubric: e.target.value })}
        placeholder="e.g. Score 1.0 if the answer is polite and offers a next step, 0.0 otherwise."
        rows={4}
        className="mt-1"
      />
    </div>
    <div>
      <Label className="text-xs">Min Score (0-1)</Label>
      <Input
        value={rule.minScore}
        onChange={(e) => onChange({ minScore: e.target.value })}
        className="mt-1"
        placeholder="0.5"
      />
      {!isValidScore(rule.minScore) && (
        <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
      )}
    </div>
    <div className="flex items-center justify-between rounded-md border p-3">
      <div>
        <Label className="text-xs">Give the judge the retrieved context</Label>
        <p className="text-xs text-muted-foreground mt-1">
          Off = rubric only (style or behavior checks). On = the judge also sees the
          KB passages the agent retrieved during the run.
        </p>
      </div>
      <Switch
        checked={rule.sourceType === "kb_retrievals"}
        onCheckedChange={(checked) =>
          onChange({ sourceType: checked ? "kb_retrievals" : "none" })
        }
      />
    </div>
  </div>
);

interface JudgeRulesBuilderProps {
  rules: JudgeRuleDraft[];
  presets: JudgeRubricPreset[];
  onChange: (rules: JudgeRuleDraft[]) => void;
}

export const JudgeRulesBuilder: React.FC<JudgeRulesBuilderProps> = ({
  rules,
  presets,
  onChange,
}) => {
  const updateRule = (index: number, patch: Partial<JudgeRuleDraft>) => {
    onChange(rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)));
  };

  const removeRule = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      {rules.map((rule, index) => (
        <JudgeRuleRow
          key={index}
          rule={rule}
          index={index}
          presets={presets}
          onChange={(patch) => updateRule(index, patch)}
          onRemove={() => removeRule(index)}
          canRemove={rules.length > 1}
        />
      ))}
      <Button variant="outline" size="sm" onClick={() => onChange([...rules, newJudgeRule()])}>
        <Plus className="mr-1 h-3.5 w-3.5" />
        Add rule
      </Button>
    </div>
  );
};
