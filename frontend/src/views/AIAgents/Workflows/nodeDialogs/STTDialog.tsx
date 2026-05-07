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

type STTDialogProps = BaseNodeDialogProps<STTNodeData, STTNodeData>;

export const STTDialog: React.FC<STTDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "Speech to Text");
  const [audioSource, setAudioSource] = useState(data.audio_source || "");
  const [provider, setProvider] = useState(data.provider || "openai");
  const [model, setModel] = useState(data.model || "whisper-1");
  const [language, setLanguage] = useState(data.language ?? "");
  const [responseFormat, setResponseFormat] = useState(
    data.response_format || "text",
  );
  const [temperature, setTemperature] = useState(data.temperature ?? 0.0);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Speech to Text");
      setAudioSource(data.audio_source || "");
      setProvider(data.provider || "openai");
      setModel(data.model || "whisper-1");
      setLanguage(data.language ?? "");
      setResponseFormat(data.response_format || "text");
      setTemperature(data.temperature ?? 0.0);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      audio_source: audioSource,
      provider,
      model,
      language: language || undefined,
      response_format: responseFormat,
      temperature,
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
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </>
      }
      {...props}
      data={{
        ...data,
        name,
        audio_source: audioSource,
        provider,
        model,
        language: language || undefined,
        response_format: responseFormat,
        temperature,
      }}
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">Node Name</Label>
          <RichInput
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Speech to Text"
            className="w-full"
          />
        </div>

        <div>
          <Label htmlFor="audio_source">Audio Source</Label>
          <DraggableTextArea
            id="audio_source"
            value={audioSource}
            onChange={(e) => setAudioSource(e.target.value)}
            placeholder="Drag the audio output variable from a connected TTS node, e.g. {{source.output}}"
            className="h-20 font-mono text-sm"
            rows={3}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="provider">Provider</Label>
          <Select value={provider} onValueChange={setProvider}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="openai">OpenAI</SelectItem>
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
              <SelectItem value="whisper-1">Whisper-1</SelectItem>
              <SelectItem value="gpt-4o-transcribe">
                GPT-4o Transcribe
              </SelectItem>
              <SelectItem value="gpt-4o-mini-transcribe">
                GPT-4o Mini Transcribe
              </SelectItem>
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
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            placeholder="e.g., en, es, fr"
            className="w-full"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="response_format">Response Format</Label>
          <Select value={responseFormat} onValueChange={setResponseFormat}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select format" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="text">Plain Text</SelectItem>
              <SelectItem value="json">JSON</SelectItem>
              <SelectItem value="verbose_json">Verbose JSON</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="temperature">Temperature ({temperature})</Label>
          <p className="text-xs text-muted-foreground mb-1">
            Sampling temperature (0.0 for deterministic)
          </p>
          <RichInput
            id="temperature"
            type="number"
            value={String(temperature)}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val) && val >= 0.0 && val <= 1.0) {
                setTemperature(val);
              }
            }}
            min={0.0}
            max={1.0}
            step={0.1}
            className="w-full"
          />
        </div>
      </div>
    </NodeConfigPanel>
  );
};
