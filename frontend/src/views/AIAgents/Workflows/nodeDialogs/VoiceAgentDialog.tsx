import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { VoiceAgentNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { Label } from "@/components/label";
import { RichInput } from "@/components/richInput";
import { Switch } from "@/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { useNodeDialogState } from "./useNodeDialogState";
import { getAllAudioProviders } from "@/services/audioProviders";
import { useAudioProvidersEnabled } from "../hooks/useAudioProviderConfig";

type VoiceAgentDialogProps = BaseNodeDialogProps<
  VoiceAgentNodeData,
  VoiceAgentNodeData
>;

/** Parse a numeric input value, mapping blank/invalid (e.g. "-", ".") to undefined. */
const toNumberOrUndef = (
  value: string,
  parse: (v: string) => number,
): number | undefined => {
  if (value === "") return undefined;
  const n = parse(value);
  return Number.isNaN(n) ? undefined : n;
};

const LIVE_MODELS = [
  {
    value: "gemini-3.1-flash-live-preview",
    label: "Gemini 3.1 Flash Live (Preview)",
  },
  {
    value: "gemini-2.5-flash-native-audio-preview-12-2025",
    label: "Gemini 2.5 Flash Native Audio (Preview)",
  },
];

const LIVE_VOICES = [
  { value: "Kore", label: "Kore (Firm)" },
  { value: "Puck", label: "Puck (Upbeat)" },
  { value: "Zephyr", label: "Zephyr (Bright)" },
  { value: "Charon", label: "Charon (Informative)" },
  { value: "Fenrir", label: "Fenrir (Excitable)" },
  { value: "Leda", label: "Leda (Youthful)" },
  { value: "Aoede", label: "Aoede (Breezy)" },
  { value: "Orus", label: "Orus (Firm)" },
];

export const VoiceAgentDialog: React.FC<VoiceAgentDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  const { values, setField, merged, handleSave } = useNodeDialogState(
    props,
    () => data
  );

  const hasAdvanced = (d: VoiceAgentNodeData) =>
    d.temperature != null ||
    d.maxOutputTokens != null ||
    d.vadSilenceMs != null ||
    !!d.vadStartSensitivity ||
    !!d.vadEndSensitivity ||
    !!d.proactiveAudio ||
    !!d.contextCompression;
  const [showAdvanced, setShowAdvanced] = useState(() => hasAdvanced(data));

  // Reset advanced-panel visibility when the dialog is opened to reflect the
  // current node data (config re-seeding is handled by useNodeDialogState).
  useEffect(() => {
    if (isOpen) {
      setShowAdvanced(hasAdvanced(data));
    }
  }, [isOpen, data]);

  // The Live API needs a Gemini audio provider, so this node depends on the
  // Audio Providers feature — don't fetch (or promise a picker) when it is off.
  const audioProvidersEnabled = useAudioProvidersEnabled();

  const { data: audioProviders } = useQuery({
    queryKey: ["audioProviders", "all"],
    queryFn: getAllAudioProviders,
    enabled: isOpen && audioProvidersEnabled,
  });
  // The Live API requires a Gemini API key
  const geminiProviders = audioProviders?.filter(
    (p) => p.provider_type === "gemini"
  );
  // Flag a configured-but-keyless provider so the operator fixes it before it
  // silently fails at runtime (the widget only ever shows a neutral "unavailable").
  const selectedProvider = geminiProviders?.find(
    (p) => p.id === values.voiceProviderId
  );
  const selectedProviderMissingKey =
    !!selectedProvider && !selectedProvider.connection_data?.api_key;

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save Changes</Button>
        </>
      }
      {...props}
      data={merged}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={values.name || "Voice Agent"}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="e.g., Voice Agent"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="voiceProviderId">Voice Provider (Gemini)</Label>
          <p className="text-xs text-muted-foreground">
            Native speech-to-speech runs on the Gemini Live API — configure a
            Gemini audio provider under Settings → Audio Providers.
          </p>
          <Select
            value={values.voiceProviderId || ""}
            onValueChange={(value) => setField("voiceProviderId", value)}
            disabled={!audioProvidersEnabled}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a Gemini audio provider" />
            </SelectTrigger>
            <SelectContent>
              {geminiProviders?.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name} ({p.provider_type})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!audioProvidersEnabled && (
            <p className="text-xs text-destructive">
              Audio Providers are not enabled in this environment, so this node
              cannot be configured here.
            </p>
          )}
          {audioProvidersEnabled && geminiProviders && geminiProviders.length === 0 && (
            <p className="text-xs text-destructive">
              No Gemini audio provider configured yet.
            </p>
          )}
          {selectedProviderMissingKey && (
            <p className="text-xs text-destructive">
              The selected Gemini provider has no API key. Live voice won&apos;t
              work until you add one under Settings → Audio Providers.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="model">Live Model</Label>
          <Select
            value={values.model || LIVE_MODELS[0].value}
            onValueChange={(value) => setField("model", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              {LIVE_MODELS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="voice">Voice</Label>
          <Select
            value={values.voice || "Kore"}
            onValueChange={(value) => setField("voice", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select voice" />
            </SelectTrigger>
            <SelectContent>
              {LIVE_VOICES.map((v) => (
                <SelectItem key={v.value} value={v.value}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="language">Language Code (Optional)</Label>
          <p className="text-xs text-muted-foreground mb-1">
            BCP-47 code (e.g., en-US, de-DE). Leave empty for auto-detect.
          </p>
          <RichInput
            id="language"
            value={values.language || ""}
            onChange={(e) => setField("language", e.target.value)}
            placeholder="e.g., en-US"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="systemPrompt">System Prompt</Label>
          <DraggableTextArea
            id="systemPrompt"
            value={values.systemPrompt || ""}
            onChange={(e) => setField("systemPrompt", e.target.value)}
            placeholder="Instructions for how the voice agent should behave"
            className="h-24 text-sm"
            rows={4}
          />
        </div>

        <div>
          <Label htmlFor="userPrompt">Text Fallback Prompt</Label>
          <p className="text-xs text-muted-foreground mb-1">
            Used when the user types a text message instead of sending voice.
          </p>
          <DraggableTextArea
            id="userPrompt"
            value={values.userPrompt || ""}
            onChange={(e) => setField("userPrompt", e.target.value)}
            placeholder="{{session.message}}"
            className="h-16 font-mono text-sm"
            rows={2}
          />
        </div>

        <div>
          <Label htmlFor="maxToolCalls">Max Tool Calls</Label>
          <p className="text-xs text-muted-foreground mb-1">
            Safety cap on tool invocations within a single voice turn.
          </p>
          <RichInput
            id="maxToolCalls"
            type="number"
            value={String(values.maxToolCalls ?? 10)}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val) && val >= 1) {
                setField("maxToolCalls", val);
              }
            }}
            min={1}
            step={1}
            className="w-full"
          />
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="voice-agent-memory">Enable Memory</Label>
          <Switch
            id="voice-agent-memory"
            checked={values.memory}
            onCheckedChange={(checked) => setField("memory", checked)}
          />
        </div>

        {values.memory && (
          <>
            <div className="space-y-2">
              <Label htmlFor="memoryTrimmingMode">Memory Trimming Mode</Label>
              <Select
                value={values.memoryTrimmingMode || "message_count"}
                onValueChange={(value) =>
                  setField(
                    "memoryTrimmingMode",
                    value as "message_count" | "rag_retrieval"
                  )
                }
              >
                <SelectTrigger id="memoryTrimmingMode" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="message_count">Last N Messages</SelectItem>
                  <SelectItem value="rag_retrieval">RAG Retrieval</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {(values.memoryTrimmingMode === "message_count" ||
              !values.memoryTrimmingMode) && (
              <div>
                <Label htmlFor="maxMessages">Max Messages</Label>
                <RichInput
                  id="maxMessages"
                  type="number"
                  value={String(values.maxMessages ?? 10)}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val >= 1) {
                      setField("maxMessages", val);
                    }
                  }}
                  min={1}
                  step={1}
                  className="w-full"
                />
              </div>
            )}
          </>
        )}

        <div className="flex items-center justify-between">
          <div>
            <Label htmlFor="voice-agent-pii">Enable PII Masking</Label>
            <p className="text-xs text-muted-foreground">
              Masks PII in replayed history and text messages. Audio sent to
              the model cannot be masked.
            </p>
          </div>
          <Switch
            id="voice-agent-pii"
            checked={values.piiMasking || false}
            onCheckedChange={(checked) => setField("piiMasking", checked)}
          />
        </div>

        {/* --- Advanced live tuning (collapsed; unset = Gemini Live defaults) --- */}
        <div className="pt-2 border-t border-border">
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            Advanced: live tuning
          </button>

          {showAdvanced && (
            <div className="space-y-3 mt-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="temperature">Temperature</Label>
                  <RichInput
                    id="temperature"
                    type="number"
                    value={values.temperature != null ? String(values.temperature) : ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      setField("temperature", toNumberOrUndef(v, parseFloat));
                    }}
                    min={0}
                    max={2}
                    step={0.1}
                    placeholder="model default"
                    className="w-full"
                  />
                </div>
                <div>
                  <Label htmlFor="maxOutputTokens">Max Output Tokens</Label>
                  <RichInput
                    id="maxOutputTokens"
                    type="number"
                    value={values.maxOutputTokens != null ? String(values.maxOutputTokens) : ""}
                    onChange={(e) => {
                      const v = e.target.value;
                      setField(
                        "maxOutputTokens",
                        toNumberOrUndef(v, (s) => parseInt(s, 10))
                      );
                    }}
                    min={1}
                    step={1}
                    placeholder="no cap"
                    className="w-full"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="vadSilenceMs">End-of-turn Silence (ms)</Label>
                <p className="text-xs text-muted-foreground mb-1">
                  How long a pause counts as "you finished". Lower = snappier turn-taking.
                </p>
                <RichInput
                  id="vadSilenceMs"
                  type="number"
                  value={values.vadSilenceMs != null ? String(values.vadSilenceMs) : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    setField(
                      "vadSilenceMs",
                      toNumberOrUndef(v, (s) => parseInt(s, 10))
                    );
                  }}
                  min={0}
                  step={50}
                  placeholder="model default"
                  className="w-full"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>Start Sensitivity</Label>
                  <Select
                    value={values.vadStartSensitivity || "default"}
                    onValueChange={(value) =>
                      setField(
                        "vadStartSensitivity",
                        value === "default"
                          ? undefined
                          : (value as VoiceAgentNodeData["vadStartSensitivity"])
                      )
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="default">Default</SelectItem>
                      <SelectItem value="START_SENSITIVITY_HIGH">High (eager)</SelectItem>
                      <SelectItem value="START_SENSITIVITY_LOW">Low (cautious)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>End Sensitivity</Label>
                  <Select
                    value={values.vadEndSensitivity || "default"}
                    onValueChange={(value) =>
                      setField(
                        "vadEndSensitivity",
                        value === "default"
                          ? undefined
                          : (value as VoiceAgentNodeData["vadEndSensitivity"])
                      )
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="default">Default</SelectItem>
                      <SelectItem value="END_SENSITIVITY_HIGH">High (sooner)</SelectItem>
                      <SelectItem value="END_SENSITIVITY_LOW">Low (waits)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label htmlFor="voice-agent-proactive">Proactive Audio</Label>
                <Switch
                  id="voice-agent-proactive"
                  checked={values.proactiveAudio || false}
                  onCheckedChange={(checked) =>
                    setField("proactiveAudio", checked)
                  }
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor="voice-agent-compression">Context Compression</Label>
                  <p className="text-xs text-muted-foreground">
                    Sliding-window so long calls stay within the context limit.
                  </p>
                </div>
                <Switch
                  id="voice-agent-compression"
                  checked={values.contextCompression || false}
                  onCheckedChange={(checked) =>
                    setField("contextCompression", checked)
                  }
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </NodeConfigPanel>
  );
};
