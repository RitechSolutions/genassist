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
import { useAudioProviderConfig } from "../hooks/useAudioProviderConfig";

type TTSDialogProps = BaseNodeDialogProps<TTSNodeData, TTSNodeData>;

export const TTSDialog: React.FC<TTSDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "Text to Speech");
  const [text, setText] = useState(data.text || "");
  const [audioProviderId, setAudioProviderId] = useState(data.audioProviderId || "");
  const [voice, setVoice] = useState(data.voice || "nova");
  const [model, setModel] = useState(data.model || "tts-1");
  const [outputFormat, setOutputFormat] = useState(data.output_format || "mp3");
  const [speed, setSpeed] = useState(data.speed ?? 1.0);

  const {
    providers: audioProviders,
    providerType,
    voices,
    models,
    formats,
    supportsSpeed,
    getDefaultsForProvider,
  } = useAudioProviderConfig({ capability: "tts", audioProviderId, enabled: isOpen });

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Text to Speech");
      setText(data.text || "");
      setAudioProviderId(data.audioProviderId || "");
      setVoice(data.voice || "nova");
      setModel(data.model || "tts-1");
      setOutputFormat(data.output_format || "mp3");
      setSpeed(data.speed ?? 1.0);
    }
  }, [isOpen, data]);

  const handleProviderChange = (id: string) => {
    setAudioProviderId(id);
    const defaults = getDefaultsForProvider(id);
    if (defaults) {
      setVoice(defaults.voice);
      setModel(defaults.model);
      setOutputFormat(defaults.outputFormat);
    }
  };

  const buildNodeData = (): TTSNodeData => ({
    ...data,
    name,
    text,
    provider: providerType || "openai",
    audioProviderId: audioProviderId || undefined,
    voice,
    model,
    output_format: outputFormat,
    speed,
  });

  const handleSave = () => {
    onUpdate(buildNodeData());
    onClose();
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
      data={buildNodeData()}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Text to Speech"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="text">Text Input</Label>
          <DraggableTextArea
            id="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Enter text or drag variables from the left panel, e.g. {{source.message}}"
            className="h-32 font-mono text-sm"
            rows={5}
          />
        </div>

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

        <div className="space-y-2">
          <Label htmlFor="voice">Voice</Label>
          <Select value={voice} onValueChange={setVoice}>
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
          <Select value={model} onValueChange={setModel}>
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
          <Select value={outputFormat} onValueChange={setOutputFormat}>
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
            <Label htmlFor="speed">Speed ({speed}x)</Label>
            <p className="text-xs text-muted-foreground mb-1">
              Speech speed (0.25 to 4.0)
            </p>
            <RichInput
              id="speed"
              type="number"
              value={String(speed)}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val >= 0.25 && val <= 4.0) {
                  setSpeed(val);
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
