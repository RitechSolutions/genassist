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

type TTSDialogProps = BaseNodeDialogProps<TTSNodeData, TTSNodeData>;

export const TTSDialog: React.FC<TTSDialogProps> = (props) => {
  const { isOpen, onClose, data, onUpdate } = props;

  const [name, setName] = useState(data.name || "Text to Speech");
  const [text, setText] = useState(data.text || "");
  const [provider, setProvider] = useState(data.provider || "openai");
  const [voice, setVoice] = useState(data.voice || "nova");
  const [model, setModel] = useState(data.model || "tts-1");
  const [outputFormat, setOutputFormat] = useState(
    data.output_format || "mp3",
  );
  const [speed, setSpeed] = useState(data.speed ?? 1.0);

  useEffect(() => {
    if (isOpen) {
      setName(data.name || "Text to Speech");
      setText(data.text || "");
      setProvider(data.provider || "openai");
      setVoice(data.voice || "nova");
      setModel(data.model || "tts-1");
      setOutputFormat(data.output_format || "mp3");
      setSpeed(data.speed ?? 1.0);
    }
  }, [isOpen, data]);

  const handleSave = () => {
    onUpdate({
      ...data,
      name,
      text,
      provider,
      voice,
      model,
      output_format: outputFormat,
      speed,
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
        text,
        provider,
        voice,
        model,
        output_format: outputFormat,
        speed,
      }}
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
          <Label htmlFor="voice">Voice</Label>
          <Select value={voice} onValueChange={setVoice}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select voice" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="alloy">Alloy</SelectItem>
              <SelectItem value="echo">Echo</SelectItem>
              <SelectItem value="fable">Fable</SelectItem>
              <SelectItem value="onyx">Onyx</SelectItem>
              <SelectItem value="nova">Nova</SelectItem>
              <SelectItem value="shimmer">Shimmer</SelectItem>
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
              <SelectItem value="tts-1">TTS-1 (Fast)</SelectItem>
              <SelectItem value="tts-1-hd">TTS-1 HD (Quality)</SelectItem>
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
              <SelectItem value="mp3">MP3</SelectItem>
              <SelectItem value="opus">Opus</SelectItem>
              <SelectItem value="aac">AAC</SelectItem>
              <SelectItem value="flac">FLAC</SelectItem>
              <SelectItem value="wav">WAV</SelectItem>
              <SelectItem value="pcm">PCM</SelectItem>
            </SelectContent>
          </Select>
        </div>

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
      </div>
    </NodeConfigPanel>
  );
};
