import React, { useState, useEffect } from "react";
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
import { getAllAudioProviders } from "@/services/audioProviders";

type VoiceAgentDialogProps = BaseNodeDialogProps<
  VoiceAgentNodeData,
  VoiceAgentNodeData
>;

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
  const { isOpen, onClose, data, onUpdate } = props;

  const [config, setConfig] = useState<VoiceAgentNodeData>(data);

  // Reset state when the dialog is opened to reflect the current node data
  useEffect(() => {
    if (isOpen) {
      setConfig(data);
    }
  }, [isOpen, data]);

  const { data: audioProviders } = useQuery({
    queryKey: ["audioProviders", "all"],
    queryFn: getAllAudioProviders,
    enabled: isOpen,
  });
  // The Live API requires a Gemini API key
  const geminiProviders = audioProviders?.filter(
    (p) => p.provider_type === "gemini"
  );

  const handleSave = () => {
    onUpdate({
      ...data,
      ...config,
    });
    onClose();
  };

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
      data={{
        ...data,
        ...config,
      }}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={config.name || "Voice Agent"}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, name: e.target.value }))
            }
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
            value={config.voiceProviderId || ""}
            onValueChange={(value) =>
              setConfig((prev) => ({ ...prev, voiceProviderId: value }))
            }
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
          {geminiProviders && geminiProviders.length === 0 && (
            <p className="text-xs text-destructive">
              No Gemini audio provider configured yet.
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="model">Live Model</Label>
          <Select
            value={config.model || LIVE_MODELS[0].value}
            onValueChange={(value) =>
              setConfig((prev) => ({ ...prev, model: value }))
            }
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
            value={config.voice || "Kore"}
            onValueChange={(value) =>
              setConfig((prev) => ({ ...prev, voice: value }))
            }
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
            value={config.language || ""}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, language: e.target.value }))
            }
            placeholder="e.g., en-US"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="systemPrompt">System Prompt</Label>
          <DraggableTextArea
            id="systemPrompt"
            value={config.systemPrompt || ""}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, systemPrompt: e.target.value }))
            }
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
            value={config.userPrompt || ""}
            onChange={(e) =>
              setConfig((prev) => ({ ...prev, userPrompt: e.target.value }))
            }
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
            value={String(config.maxToolCalls ?? 10)}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val) && val >= 1) {
                setConfig((prev) => ({ ...prev, maxToolCalls: val }));
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
            checked={config.memory}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({ ...prev, memory: checked }))
            }
          />
        </div>

        {config.memory && (
          <>
            <div className="space-y-2">
              <Label htmlFor="memoryTrimmingMode">Memory Trimming Mode</Label>
              <Select
                value={config.memoryTrimmingMode || "message_count"}
                onValueChange={(value) =>
                  setConfig((prev) => ({
                    ...prev,
                    memoryTrimmingMode: value as
                      | "message_count"
                      | "rag_retrieval",
                  }))
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

            {(config.memoryTrimmingMode === "message_count" ||
              !config.memoryTrimmingMode) && (
              <div>
                <Label htmlFor="maxMessages">Max Messages</Label>
                <RichInput
                  id="maxMessages"
                  type="number"
                  value={String(config.maxMessages ?? 10)}
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val) && val >= 1) {
                      setConfig((prev) => ({ ...prev, maxMessages: val }));
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
            checked={config.piiMasking || false}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({ ...prev, piiMasking: checked }))
            }
          />
        </div>
      </div>
    </NodeConfigPanel>
  );
};
