import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";
import { Loader2, Save } from "lucide-react";
import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { GuardrailChecksList } from "@/components/GuardrailChecksList";
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
import { ToggleGroup, ToggleGroupItem } from "@/components/toggle-group";
import { extractErrorMessage } from "@/helpers/apiError";
import {
  defaultGuardrailPolicy,
  guardrailLimitError,
  usesJudge,
} from "@/helpers/guardrailChecks";
import {
  GuardrailCheckResponse,
  GuardrailMode,
  GuardrailPolicy,
  UntrustedContentMode,
} from "@/interfaces/guardrails.interface";
import {
  checkAgentGuardrails,
  getAgentConfig,
  updateAgentConfig,
} from "@/services/api";
import { GuardrailChecksEditor } from "@/views/AIAgents/components/GuardrailChecksEditor";
import { TranslationTrigger } from "@/views/AIAgents/components/TranslationTrigger";

const WAIT_HELP = "Each check adds a short wait before the reply.";

const MODES: { value: GuardrailMode; label: string; help: string }[] = [
  { value: "off", label: "Off", help: "Nothing is checked." },
  {
    value: "detect",
    label: "Detect only",
    help: `Records what the checks find and blocks nothing. ${WAIT_HELP}`,
  },
  {
    value: "block",
    label: "Block",
    help: `Answers with the blocked message when a check fires. ${WAIT_HELP} Messages over 60,000 characters are blocked.`,
  },
];

const TOOL_RESULT_OPTIONS: { value: UntrustedContentMode; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "flag", label: "Flag" },
  { value: "block", label: "Block" },
];

interface GuardrailsPanelProps {
  agentId?: string;
}

export const GuardrailsPanel = ({ agentId }: GuardrailsPanelProps) => {
  const [policy, setPolicy] = useState<GuardrailPolicy>(defaultGuardrailPolicy);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testText, setTestText] = useState("");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<GuardrailCheckResponse | null>(null);

  useEffect(() => {
    if (!agentId) return;
    setLoading(true);
    getAgentConfig(agentId)
      .then((config) =>
        setPolicy(
          config?.security_settings?.guardrails ?? defaultGuardrailPolicy()
        )
      )
      .catch(() => toast.error("Failed to load Guardrails"))
      .finally(() => setLoading(false));
  }, [agentId]);

  const update = (patch: Partial<GuardrailPolicy>) =>
    setPolicy((prev) => ({ ...prev, ...patch }));

  const topicsComplete = policy.denied_topics.every(
    (topic) => topic.name.trim() && topic.definition.trim()
  );
  const judgeMissing =
    policy.mode !== "off" &&
    usesJudge(policy, policy.untrusted_content) &&
    !policy.judge_provider_id;
  const canSave =
    !saving &&
    topicsComplete &&
    !guardrailLimitError(policy) &&
    !judgeMissing &&
    policy.blocked_message.trim() !== "";

  const handleSave = async () => {
    if (!agentId) return;
    setSaving(true);
    try {
      const updated = await updateAgentConfig(agentId, {
        security_settings: { guardrails: policy },
      });
      if (!updated) {
        toast.error("Failed to save Guardrails");
        return;
      }
      setPolicy(
        updated.security_settings?.guardrails ?? defaultGuardrailPolicy()
      );
      toast.success("Guardrails saved");
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to save Guardrails"));
    } finally {
      setSaving(false);
    }
  };

  const handleCheck = async () => {
    if (!agentId) return;
    setChecking(true);
    try {
      setResult(await checkAgentGuardrails(agentId, policy, testText));
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to check the message"));
    } finally {
      setChecking(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex justify-center items-center py-12">
          <div className="text-sm text-muted-foreground">
            Loading Guardrails...
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="p-6 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              Guardrails
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              Check messages and replies for attacks, harmful content and
              denied topics
            </p>
          </div>
          <Button onClick={handleSave} disabled={!canSave}>
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </div>

        <div className="space-y-2 border-b border-border pb-6">
          <Label>Mode</Label>
          <ToggleGroup
            type="single"
            value={policy.mode}
            onValueChange={(mode) =>
              mode && update({ mode: mode as GuardrailMode })
            }
            variant="outline"
            size="sm"
            className="w-fit justify-start rounded-full border border-input bg-background p-0.5"
            aria-label="Mode"
          >
            {MODES.map((mode) => (
              <ToggleGroupItem
                key={mode.value}
                value={mode.value}
                className="rounded-full px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
              >
                {mode.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p className="text-xs text-muted-foreground">
            {MODES.find((mode) => mode.value === policy.mode)?.help}
          </p>
        </div>

        <div className="border-b border-border pb-6">
          <GuardrailChecksEditor
            value={policy}
            onChange={({
              prompt_attack,
              harmful_content,
              denied_topics,
              blocked_words,
            }) =>
              update({
                prompt_attack,
                harmful_content,
                denied_topics,
                blocked_words,
              })
            }
            judgeProviderId={policy.judge_provider_id}
            onJudgeProviderChange={(judge_provider_id) =>
              update({ judge_provider_id })
            }
            untrustedContent={policy.untrusted_content}
          />
        </div>

        <div className="space-y-6 border-b border-border pb-6">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <Label htmlFor="guardrails-check-replies">Check replies</Label>
              <p className="text-xs text-muted-foreground">
                Checks the agent's reply before it is sent.
                {policy.mode === "block" &&
                  " Replies are held until checked, so they don't stream."}
              </p>
            </div>
            <Switch
              id="guardrails-check-replies"
              checked={policy.check_replies}
              onCheckedChange={(check_replies) => update({ check_replies })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="guardrails-tool-results">Tool results</Label>
            <Select
              value={policy.untrusted_content}
              onValueChange={(value) =>
                update({ untrusted_content: value as UntrustedContentMode })
              }
            >
              <SelectTrigger id="guardrails-tool-results" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TOOL_RESULT_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Checks each tool result for hidden instructions. Adds one check
              per tool call.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="guardrails-blocked-message">
                Blocked message
              </Label>
              {agentId && policy.blocked_message.trim() && (
                <TranslationTrigger
                  translationKey={`agent.${agentId}.guardrails.blocked_message`}
                  currentValue={policy.blocked_message}
                />
              )}
            </div>
            <RichInput
              id="guardrails-blocked-message"
              value={policy.blocked_message}
              maxLength={500}
              onChange={(e) => update({ blocked_message: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Sent instead of a blocked message or reply.
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <h4 className="text-base font-semibold text-foreground mb-1">
              Try a message
            </h4>
            <p className="text-sm text-muted-foreground">
              Runs the checks above, saved or not.
            </p>
          </div>
          <RichTextarea
            aria-label="Message to check"
            value={testText}
            maxLength={20000}
            size="hint"
            onChange={(e) => setTestText(e.target.value)}
            placeholder="Type a customer message"
          />
          <Button
            variant="outline"
            onClick={handleCheck}
            disabled={!testText.trim() || checking || !topicsComplete}
          >
            {checking && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Check
          </Button>
          {result && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                {result.blocked ? "Would be blocked" : "Would pass"}
              </p>
              <GuardrailChecksList verdicts={result.verdicts} />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
