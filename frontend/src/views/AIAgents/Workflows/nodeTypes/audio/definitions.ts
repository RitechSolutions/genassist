import { NodeProps } from "reactflow";
import {
  NodeData,
  NodeTypeDefinition,
  TTSNodeData,
  STTNodeData,
} from "../../types/nodes";
import TTSNode from "./ttsNode";
import STTNode from "./sttNode";
import { TTS_HELP_CONTENT, STT_HELP_CONTENT } from "./helperDefinition";

export const TTS_NODE_DEFINITION: NodeTypeDefinition<TTSNodeData> = {
  type: "ttsNode",
  label: "Text to Speech",
  description:
    "Converts text input to audio using a TTS provider.",
  shortDescription: "Convert text to audio",
  helpContent: TTS_HELP_CONTENT,
  configSubtitle: "Configure voice, model, and output format.",
  category: "audio",
  icon: "Volume2",
  defaultData: {
    name: "Text to Speech",
    text: "{{source.message}}",
    provider: "openai",
    audioProviderId: "",
    voice: "nova",
    model: "tts-1",
    output_format: "mp3",
    speed: 1.0,
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "text",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "audio",
        position: "right",
      },
    ],
  },
  component: TTSNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "ttsNode",
    position,
    data: { ...data },
  }),
};

export const STT_NODE_DEFINITION: NodeTypeDefinition<STTNodeData> = {
  type: "sttNode",
  label: "Speech to Text",
  description:
    "Transcribes audio input to text using an STT provider.",
  shortDescription: "Transcribe audio to text",
  helpContent: STT_HELP_CONTENT,
  configSubtitle: "Configure model, language, and transcription options.",
  category: "audio",
  icon: "Mic",
  defaultData: {
    name: "Speech to Text",
    audio_source: "{{source.output}}",
    provider: "openai",
    audioProviderId: "",
    model: "whisper-1",
    response_format: "text",
    temperature: 0.0,
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "audio",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "text",
        position: "right",
      },
    ],
  },
  component: STTNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "sttNode",
    position,
    data: { ...data },
  }),
};
