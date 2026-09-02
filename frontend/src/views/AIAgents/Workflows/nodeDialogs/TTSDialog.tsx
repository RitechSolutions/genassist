import React, { useState, useEffect } from "react";
import { TTSNodeData } from "../types/nodes";
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

type TTSDialogProps = BaseNodeDialogProps<TTSNodeData, TTSNodeData>;

export const TTSDialog: React.FC<TTSDialogProps> = (props) => {
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
    voices,
    models,
    formats,
    supportsSpeed,
    getDefaultsForProvider,
  } = useAudioProviderConfig({ capability: "tts", audioProviderId, enabled: isOpen });

  // Without the feature the provider list is never fetched, so hide the picker and
  // let the node run on the built-in defaults instead of showing an empty select.
  const audioProvidersEnabled = useAudioProvidersEnabled();

  const { values, setField, setValues, merged, handleSave } =
    useNodeDialogState(
      props,
      () => ({
        name: data.name || "Text to Speech",
        text: data.text || "",
        voice: data.voice || "nova",
        model: data.model || "tts-1",
        output_format: data.output_format || "mp3",
        speed: data.speed ?? 1.0,
      }),
      (v) => ({
        name: v.name,
        text: v.text,
        provider: providerType || "openai",
        audioProviderId: audioProviderId || undefined,
        voice: v.voice,
        model: v.model,
        output_format: v.output_format,
        speed: v.speed,
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
        voice: defaults.voice,
        model: defaults.model,
        output_format: defaults.outputFormat,
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
            placeholder="e.g., Text to Speech"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="text">Text Input</Label>
          <DraggableTextArea
            id="text"
            value={values.text}
            onChange={(e) => setField("text", e.target.value)}
            placeholder="Enter text or drag variables from the left panel, e.g. {{source.message}}"
            className="h-32 font-mono text-sm"
            rows={5}
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
          <Label htmlFor="voice">Voice</Label>
          <Select
            value={values.voice}
            onValueChange={(value) => setField("voice", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select voice" />
            </SelectTrigger>
            <SelectContent>
              {voices.map((v) => (
                <SelectItem key={v.value} value={v.value}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

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

        <div className="space-y-2">
          <Label htmlFor="output_format">Output Format</Label>
          <Select
            value={values.output_format}
            onValueChange={(value) => setField("output_format", value)}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select format" />
            </SelectTrigger>
            <SelectContent>
              {formats.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {supportsSpeed && (
          <div>
            <Label htmlFor="speed">Speed ({values.speed}x)</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Speech speed (0.25 to 4.0)
            </p>
            <RichInput
              id="speed"
              type="number"
              value={String(values.speed)}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val >= 0.25 && val <= 4.0) {
                  setField("speed", val);
                }
              }}
              min={0.25}
              max={4.0}
              step={0.25}
              className="w-full"
            />
          </div>
        )}
      </div>
    </NodeConfigPanel>
  );
};
