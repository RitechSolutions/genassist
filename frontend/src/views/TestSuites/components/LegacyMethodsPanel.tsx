import React from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/label";
import { Checkbox } from "@/components/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Settings } from "lucide-react";
import { cn } from "@/helpers/utils";
import type { LLMProviderMinimal } from "@/interfaces/llmProvider.interface";
import type { RuleConversation } from "@/interfaces/testEvaluation.interface";
import { ToolUsageRuleBuilder } from "./ToolUsageRuleBuilder";
import { RouteRulesBuilder } from "./RouteRulesBuilder";
import { ActionRulesBuilder } from "./ActionRulesBuilder";
import { JudgeRulesBuilder } from "./JudgeRulesBuilder";
import {
  CONFIG_METRICS,
  GRADING_SOURCE_OPTIONS,
  METRIC_GROUPS,
  NLI_MODEL_OPTIONS,
  RUBRIC_PRESETS,
  isValidScore,
  type GradingSourceSelection,
  type MethodDef,
  type MethodSettingsValue,
} from "../helpers/methodSettings";
import type { EvaluationCatalog } from "../hooks/useEvaluationData";

export type { GradingSourceSelection } from "../helpers/methodSettings";

const GradingSourceSelect: React.FC<{
  value: GradingSourceSelection;
  onChange: (value: GradingSourceSelection) => void;
  allowRubricOnly?: boolean;
  legacyField?: string;
}> = ({ value, onChange, allowRubricOnly = false, legacyField }) => (
  <Select value={value} onValueChange={(next) => onChange(next as GradingSourceSelection)}>
    <SelectTrigger className="mt-1">
      <SelectValue placeholder="Select source" />
    </SelectTrigger>
    <SelectContent>
      {allowRubricOnly && <SelectItem value="none">No source: rubric only</SelectItem>}
      {GRADING_SOURCE_OPTIONS.map((source) => (
        <SelectItem key={source.value} value={source.value}>
          {source.label}
        </SelectItem>
      ))}
      {legacyField && (
        <SelectItem value="legacy">Legacy configured source ({legacyField})</SelectItem>
      )}
    </SelectContent>
  </Select>
);

const MetricOption: React.FC<{
  metric: MethodDef;
  selected: boolean;
  onToggle: (checked: boolean) => void;
}> = ({ metric, selected, onToggle }) => (
  <div
    className={cn(
      "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
      selected ? "border-primary bg-primary/5" : "hover:border-gray-300"
    )}
    onClick={() => onToggle(!selected)}
  >
    <Checkbox
      id={`metric-${metric.value}`}
      checked={selected}
      onClick={(e) => e.stopPropagation()}
      onCheckedChange={(checked) => onToggle(Boolean(checked))}
      className="mt-0.5"
    />
    <div className="flex-1">
      <Label htmlFor={`metric-${metric.value}`} className="text-sm font-medium cursor-pointer">
        {metric.label}
      </Label>
      <p className="text-xs text-muted-foreground mt-0.5">{metric.description}</p>
    </div>
  </div>
);

/** The 12 methods, grouped, to tick. */
export const MethodPicker: React.FC<{
  metrics: string[];
  onChange: (metrics: string[]) => void;
}> = ({ metrics, onChange }) => (
  <>
    {METRIC_GROUPS.map((group) => (
      <div key={group.label} className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {group.label}
        </div>
        {group.metrics.map((metric) => (
          <MetricOption
            key={metric.value}
            metric={metric}
            selected={metrics.includes(metric.value)}
            onToggle={(checked) =>
              onChange(
                checked
                  ? [...metrics, metric.value]
                  : metrics.filter((m) => m !== metric.value),
              )
            }
          />
        ))}
      </div>
    ))}
  </>
);

interface MethodSettingsProps {
  metrics: string[];
  settings: MethodSettingsValue;
  onChange: (patch: Partial<MethodSettingsValue>) => void;
  providers: LLMProviderMinimal[];
  catalog: EvaluationCatalog;
  conversations: RuleConversation[];
  hasWorkflow: boolean;
  /** Says so when the picked methods have nothing to set. */
  showEmptyState?: boolean;
}

/** The settings of each picked method. */
export const MethodSettings: React.FC<MethodSettingsProps> = ({
  metrics,
  settings,
  onChange,
  providers,
  catalog,
  conversations,
  hasWorkflow,
  showEmptyState = false,
}) => {
  const set =
    <K extends keyof MethodSettingsValue>(key: K) =>
    (next: MethodSettingsValue[K]) =>
      onChange({ [key]: next } as Partial<MethodSettingsValue>);
  const needsConfig = metrics.some((m) => CONFIG_METRICS.includes(m));

  return (
    <div className="space-y-4">
      {showEmptyState && !needsConfig && (
        <div className="text-center py-8 text-muted-foreground">
          <Settings className="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No additional configuration needed.</p>
          <p className="text-xs mt-1">
            The selected validation methods don't require extra settings.
          </p>
        </div>
      )}

      {metrics.includes("nli_eval") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span>
            NLI Evaluation Config
          </div>
          <p className="text-xs text-muted-foreground">
            Uses workflow output as answer and expected output as evidence.
          </p>
          <div>
            <Label className="text-xs">NLI Model</Label>
            <Select value={settings.nliModelName} onValueChange={set("nliModelName")}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select NLI model" />
              </SelectTrigger>
              <SelectContent>
                {NLI_MODEL_OPTIONS.map((model) => (
                  <SelectItem key={model.value} value={model.value}>
                    {model.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Compare answer with</Label>
            <GradingSourceSelect
              value={settings.nliEvidenceSource}
              onChange={set("nliEvidenceSource")}
              legacyField={settings.nliEvidenceField}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Expected answer checks consistency with the reference answer; Retrieved
              context checks support from what the agent retrieved this run.
            </p>
          </div>
          <div>
            <Label className="text-xs">Min Entailment Score (0-1)</Label>
            <Input
              value={settings.nliMinEntailScore}
              onChange={(e) => set("nliMinEntailScore")(e.target.value)}
              className="mt-1"
              placeholder="0.5"
            />
            {!isValidScore(settings.nliMinEntailScore) && (
              <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
            )}
          </div>
        </div>
      )}

      {metrics.includes("provenance_eval") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            Provenance Evaluation Config
          </div>
          <p className="text-xs text-muted-foreground">
            Uses workflow output as answer and expected output as context.
          </p>
          <div>
            <Label className="text-xs">Grounding source</Label>
            <GradingSourceSelect
              value={settings.provContextSource}
              onChange={set("provContextSource")}
              legacyField={settings.provContextField}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Retrieved context means only what the agent actually retrieved this run
              (KB passages and retrieval-tool results), not the whole knowledge base.
            </p>
          </div>
          <div>
            <Label className="text-xs">Provenance Mode</Label>
            <Select
              value={settings.provMode}
              onValueChange={(value: "embeddings" | "llm") => set("provMode")(value)}
            >
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="embeddings">Embeddings</SelectItem>
                <SelectItem value="llm">LLM Verification</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Min Score (0-1)</Label>
            <Input
              value={settings.provMinScore}
              onChange={(e) => set("provMinScore")(e.target.value)}
              className="mt-1"
              placeholder="0.5"
            />
            {!isValidScore(settings.provMinScore) && (
              <p className="text-xs text-red-500 mt-1">Enter a number between 0 and 1.</p>
            )}
          </div>
          {settings.provMode === "embeddings" && (
            <>
              <div>
                <Label className="text-xs">Embedding Provider</Label>
                <Select
                  value={settings.provEmbeddingType}
                  onValueChange={(value: "openai" | "huggingface" | "bedrock") =>
                    set("provEmbeddingType")(value)
                  }
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select embedding provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="huggingface">HuggingFace</SelectItem>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="bedrock">AWS Bedrock</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Embedding Model Name</Label>
                <Input
                  value={settings.provEmbeddingModelName}
                  onChange={(e) => set("provEmbeddingModelName")(e.target.value)}
                  placeholder="all-MiniLM-L6-v2"
                  className="mt-1"
                />
              </div>
            </>
          )}

          {settings.provMode === "llm" && (
            <>
              <div>
                <Label className="text-xs">LLM Provider</Label>
                <Select value={settings.provLlmProviderId} onValueChange={set("provLlmProviderId")}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>
                        {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Additional Verification Instructions</Label>
                <Textarea
                  value={settings.provLlmJudgeSystemPromptSuffix}
                  onChange={(e) => set("provLlmJudgeSystemPromptSuffix")(e.target.value)}
                  placeholder="Optional extra instructions for the judge..."
                  size="body"
                  className="mt-1"
                />
              </div>
            </>
          )}
        </div>
      )}

      {metrics.includes("tool_used") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500"></span>
            Tool Usage
          </div>
          <p className="text-xs text-muted-foreground">
            Add rules about which tools an agent should or should not use. Agents and
            tools come from the selected workflow.
          </p>
          {!hasWorkflow ? (
            <p className="text-sm text-muted-foreground">
              Pick a workflow first to load its agents and tools.
            </p>
          ) : (
            <ToolUsageRuleBuilder
              rules={settings.toolRules}
              onChange={set("toolRules")}
              catalog={catalog.agents}
              conversations={conversations}
              loading={catalog.loading}
              error={catalog.error}
            />
          )}
        </div>
      )}

      {metrics.includes("not_contains") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-500"></span>
            Does Not Contain Config
          </div>
          <p className="text-xs text-muted-foreground">
            Fails the run if any of these phrases appears in the output. One phrase
            per line. Matching is case-insensitive.
          </p>
          <div>
            <Label className="text-xs">Forbidden Phrases *</Label>
            <Textarea
              value={settings.notContainsText}
              onChange={(e) => set("notContainsText")(e.target.value)}
              placeholder={"e.g.\ncompetitor name\nsocial security number"}
              size="body"
              className="mt-1"
            />
          </div>
        </div>
      )}

      {metrics.includes("field_equals") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-sky-500"></span>
            Field Equals Config
          </div>
          <p className="text-xs text-muted-foreground">
            Checks that a value from the run equals an expected value. Values are
            compared as text.
          </p>
          <div>
            <Label className="text-xs">Field</Label>
            <Input
              value={settings.fieldEqualsField}
              onChange={(e) => set("fieldEqualsField")(e.target.value)}
              placeholder="Leave empty for the final output, or e.g. outputs.status"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Expected Value</Label>
            <Input
              value={settings.fieldEqualsExpected}
              onChange={(e) => set("fieldEqualsExpected")(e.target.value)}
              placeholder="Leave empty to use the test case's expected output"
              className="mt-1"
            />
          </div>
        </div>
      )}

      {metrics.includes("route_taken") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-orange-500"></span>
            Route Taken Config
          </div>
          <p className="text-xs text-muted-foreground">
            Checks that router nodes selected the expected branches, on every turn or
            at least once in a conversation. All rules must pass.
          </p>
          <RouteRulesBuilder
            rules={settings.routeRules}
            routers={catalog.routers}
            conversations={conversations}
            onChange={set("routeRules")}
          />
        </div>
      )}

      {metrics.includes("action_taken") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-500"></span>
            Action Taken Config
          </div>
          <p className="text-xs text-muted-foreground">
            Checks whether specific workflow nodes ran successfully, on every turn or
            at least once in a conversation. All rules must pass.
          </p>
          <ActionRulesBuilder
            rules={settings.actionRules}
            nodes={catalog.actionNodes}
            conversations={conversations}
            onChange={set("actionRules")}
          />
        </div>
      )}

      {metrics.includes("llm_judge") && (
        <div className="border rounded-lg p-4 space-y-3">
          <div className="text-sm font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-pink-500"></span>
            LLM Judge Config
          </div>
          <p className="text-xs text-muted-foreground">
            Grades the answer against rubrics you write. One criterion per rule works
            best; all rules must pass.
          </p>
          <div>
            <Label className="text-xs">LLM Provider</Label>
            <Select value={settings.judgeProviderId} onValueChange={set("judgeProviderId")}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.id} value={provider.id}>
                    {provider.name} ({provider.llm_model_provider} - {provider.llm_model})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <JudgeRulesBuilder
            rules={settings.judgeRules}
            presets={RUBRIC_PRESETS}
            onChange={set("judgeRules")}
          />
        </div>
      )}
    </div>
  );
};
