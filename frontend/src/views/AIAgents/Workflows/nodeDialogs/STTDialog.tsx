import React, { useState, useEffect } from "react";
import { STTNodeData } from "../types/nodes";
import { Button } from "@/components/button";
import { RichInput } from "@/components/richInput";
import { Label } from "@/components/label";
import { DraggableTextArea } from "../components/custom/DraggableTextArea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/select";
import { Save } from "lucide-react";
import { NodeConfigPanel } from "../components/NodeConfigPanel";
import { BaseNodeDialogProps } from "./base";
import { useAudioProviderConfig, useAudioProvidersEnabled } from "../hooks/useAudioProviderConfig";
import { useNodeDialogState } from "./useNodeDialogState";

type STTDialogProps = BaseNodeDialogProps<STTNodeData, STTNodeData>;

export const STTDialog: React.FC<STTDialogProps> = (props) => {
  const { isOpen, onClose, data } = props;

  // `audioProviderId` drives `useAudioProviderConfig` (below), so it must be resolved
  // before that hook runs. `useNodeDialogState` computes its `merged`/`toPayload` eagerly
  // and `toPayload` reads `providerType` from the audio-config hook, so the config hook
  // must run first — which means this field stays as local state (re-seeded by its own
  // effect) rather than living inside the dialog-state hook.
  const [audioProviderId, setAudioProviderId] = useState(
    data.audioProviderId || "",
  );

  const {
    providers: audioProviders,
    providerType,
    models,
    responseFormats,
    supportsTemperature,
    getDefaultsForProvider,
  } = useAudioProviderConfig({ capability: "stt", audioProviderId, enabled: isOpen });

  // Without the feature the provider list is never fetched, so hide the picker and
  // let the node run on the built-in defaults instead of showing an empty select.
  const audioProvidersEnabled = useAudioProvidersEnabled();

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(
      props,
      () => ({
        name: data.name || "Speech to Text",
        audio_source: data.audio_source || "",
        model: data.model || "whisper-1",
        language: data.language ?? "",
        response_format: data.response_format || "text",
        temperature: data.temperature ?? 0.0,
      }),
      (v) => ({
        name: v.name,
        audio_source: v.audio_source,
        provider: providerType || "openai",
        audioProviderId: audioProviderId || undefined,
        model: v.model,
        language: v.language || undefined,
        response_format: v.response_format,
        temperature: v.temperature,
      }),
    );

  // Re-seed the externally-held `audioProviderId` when the panel (re)opens or the node
  // data changes — mirrors the hook's re-seed for the remaining fields.
  useEffect(() => {
    if (isOpen) {
      setAudioProviderId(data.audioProviderId || "");
    }
  }, [isOpen, data]);

  const handleProviderChange = (id: string) => {
    setAudioProviderId(id);
    const defaults = getDefaultsForProvider(id);
    if (defaults) {
      setValues((v) => ({
        ...v,
        model: defaults.model,
        response_format: defaults.responseFormat,
      }));
    }
  };

  return (
    <NodeConfigPanel
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
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
            value={values.name}
            onChange={(e) => setField("name", e.target.value)}
            placeholder="e.g., Speech to Text"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="audio_source">Audio Source</Label>
          <DraggableTextArea
            id="audio_source"
            value={values.audio_source}
            onChange={(e) => setField("audio_source", e.target.value)}
            placeholder="Drag the audio output variable from a connected TTS node, e.g. {{source.output}}"
            className="h-20 font-mono text-sm"
            rows={3}
          />
        </div>

        {audioProvidersEnabled && (
          <div className="space-y-2">
            <Label htmlFor="audioProviderId">Audio Provider</Label>
            <Select value={audioProviderId} onValueChange={handleProviderChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select audio provider" />
              </SelectTrigger>
              <SelectContent>
                {audioProviders?.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name} ({p.provider_type})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="model">Model</Label>
          <Select
            value={values.model}
            onValueChange={(value) => setField("model", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="language">Language Code (Optional)</Label>
          <p className="text-xs text-muted-foreground mb-1">
            ISO 639-1 code (e.g., en, es, fr). Leave empty for auto-detect.
          </p>
          <RichInput
            id="language"
            value={values.language}
            onChange={(e) => setField("language", e.target.value)}
            placeholder="e.g., en, es, fr"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="response_format">Response Format</Label>
          <Select
            value={values.response_format}
            onValueChange={(value) => setField("response_format", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select format" />
            </SelectTrigger>
            <SelectContent>
              {responseFormats.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {supportsTemperature && (
          <div>
            <Label htmlFor="temperature">Temperature ({values.temperature})</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Sampling temperature (0.0 for deterministic)
            </p>
            <RichInput
              id="temperature"
              type="number"
              value={String(values.temperature)}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val >= 0.0 && val <= 1.0) {
                  setField("temperature", val);
                }
              }}
              min={0.0}
              max={1.0}
              step={0.1}
              className="w-full"
            />
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
