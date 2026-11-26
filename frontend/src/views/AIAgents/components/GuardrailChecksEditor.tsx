import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
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
import { TagsFieldInput } from "@/components/TagsFieldInput";
import {
  HARM_CATEGORIES,
  guardrailLimitError,
  usesJudge,
} from "@/helpers/guardrailChecks";
import {
  DeniedTopic,
  GuardrailCheckSettings,
  Sensitivity,
  UntrustedContentMode,
} from "@/interfaces/guardrails.interface";
import { LLMProvider } from "@/interfaces/llmProvider.interface";
import { getAllLLMProviders } from "@/services/llmProviders";

const MAX_TOPICS = 20;
const MAX_EXAMPLES = 3;

const SENSITIVITY_OPTIONS: { value: Sensitivity; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

interface GuardrailChecksEditorProps {
  value: GuardrailCheckSettings;
  onChange: (next: GuardrailCheckSettings) => void;
  judgeProviderId: string | null;
  onJudgeProviderChange: (providerId: string) => void;
  untrustedContent?: UntrustedContentMode;
}

function SensitivitySelect({
  id,
  value,
  onChange,
}: {
  id: string;
  value: Sensitivity;
  onChange: (next: Sensitivity) => void;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as Sensitivity)}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {SENSITIVITY_OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function GuardrailChecksEditor({
  value,
  onChange,
  judgeProviderId,
  onJudgeProviderChange,
  untrustedContent = "off",
}: GuardrailChecksEditorProps) {
  const { data: providers = [] } = useQuery({
    queryKey: ["llmProviders"],
    queryFn: getAllLLMProviders,
    select: (rows: LLMProvider[]) => rows.filter((p) => p.is_active === 1),
  });

  const update = (patch: Partial<GuardrailCheckSettings>) =>
    onChange({ ...value, ...patch });

  const updateTopic = (index: number, patch: Partial<DeniedTopic>) =>
    update({
      denied_topics: value.denied_topics.map((topic, i) =>
        i === index ? { ...topic, ...patch } : topic
      ),
    });

  const limitError = guardrailLimitError(value);

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="guardrails-judge">Judge model</Label>
        <Select
          value={judgeProviderId ?? ""}
          onValueChange={onJudgeProviderChange}
        >
          <SelectTrigger id="guardrails-judge" className="w-full">
            <SelectValue placeholder="Pick a model" />
          </SelectTrigger>
          <SelectContent>
            {providers.map((provider) => (
              <SelectItem key={provider.id} value={provider.id}>
                {provider.name} ({provider.llm_model_provider} -{" "}
                {provider.llm_model})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Reads each message and scores it for the checks below.
        </p>
        {usesJudge(value, untrustedContent) && !judgeProviderId && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Pick a judge model to run these checks.
          </p>
        )}
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="space-y-0.5">
          <Label htmlFor="guardrails-previous-reply">
            Previous reply as context
          </Label>
          <p className="text-xs text-muted-foreground">
            The judge also reads the end of the agent's last reply. Only the
            checked text is scored.
          </p>
        </div>
        <Switch
          id="guardrails-previous-reply"
          checked={!!value.previous_reply_context}
          onCheckedChange={(previous_reply_context) =>
            update({ previous_reply_context })
          }
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="guardrails-prompt-attack">Prompt attacks</Label>
        <SensitivitySelect
          id="guardrails-prompt-attack"
          value={value.prompt_attack}
          onChange={(prompt_attack) => update({ prompt_attack })}
        />
        <p className="text-xs text-muted-foreground">
          Attempts to override the agent's instructions.
        </p>
      </div>

      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-foreground">
          Harmful content
        </h4>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          {HARM_CATEGORIES.map(({ key, label }) => (
            <div key={key} className="space-y-2">
              <Label htmlFor={`guardrails-harm-${key}`}>{label}</Label>
              <SensitivitySelect
                id={`guardrails-harm-${key}`}
                value={value.harmful_content[key]}
                onChange={(level) =>
                  update({
                    harmful_content: { ...value.harmful_content, [key]: level },
                  })
                }
              />
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-foreground">
            Denied topics
          </h4>
          <p className="text-xs text-muted-foreground">
            Topics the agent must not discuss.
          </p>
        </div>
        {value.denied_topics.map((topic, index) => (
          <div key={index} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <RichInput
                aria-label="Topic name"
                value={topic.name}
                maxLength={100}
                onChange={(e) => updateTopic(index, { name: e.target.value })}
                placeholder="Topic name"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="shrink-0"
                aria-label="Remove topic"
                onClick={() =>
                  update({
                    denied_topics: value.denied_topics.filter(
                      (_, i) => i !== index
                    ),
                  })
                }
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            <RichTextarea
              aria-label="Topic definition"
              value={topic.definition}
              maxLength={300}
              size="compact"
              onChange={(e) =>
                updateTopic(index, { definition: e.target.value })
              }
              placeholder="What the topic covers"
            />
            <TagsFieldInput
              id={`guardrails-topic-${index}-examples`}
              value={topic.examples}
              onChange={(examples) =>
                updateTopic(index, {
                  examples: examples.slice(0, MAX_EXAMPLES),
                })
              }
              placeholder="Up to 3 examples"
            />
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={value.denied_topics.length >= MAX_TOPICS}
          onClick={() =>
            update({
              denied_topics: [
                ...value.denied_topics,
                { name: "", definition: "", examples: [] },
              ],
            })
          }
        >
          <Plus className="mr-1 h-4 w-4" />
          Add topic
        </Button>
      </div>

      <div className="space-y-2">
        <Label htmlFor="guardrails-blocked-words">Blocked words</Label>
        <TagsFieldInput
          id="guardrails-blocked-words"
          value={value.blocked_words}
          onChange={(blocked_words) => update({ blocked_words })}
          placeholder="Type a word and press Enter"
        />
        <p className="text-xs text-muted-foreground">
          Matched as whole words. No judge needed.
        </p>
      </div>

      {limitError && <p className="text-xs text-destructive">{limitError}</p>}
    </div>
  );
}
