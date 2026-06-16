import { useCallback } from "react";
import { NodeData } from "../types/nodes";
import { useAudioCapture } from "./useAudioCapture";

interface UseAudioTestOptions {
  nodeType: string;
  nodeData: NodeData;
  setFormData: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setError: (error: string | null) => void;
}

export function buildAudioPayload(base64: string, format: string): string {
  return JSON.stringify({
    type: "audio",
    format,
    encoding: "base64",
    data: base64,
  });
}

export function useAudioTest({ nodeType, nodeData, setFormData, setError }: UseAudioTestOptions) {
  const isSTTNode = nodeType === "sttNode";
  const isTTSNode = nodeType === "ttsNode";
  // The voice agent reads audio from the `audio_data` state key and requires
  // WAV input (the Live API has no webm decoder).
  const isVoiceAgentNode = nodeType === "voiceAgentNode";
  const isAudioInputNode = isSTTNode || isVoiceAgentNode;

  const getSTTAudioKey = useCallback((): string => {
    const audioSource = (nodeData as unknown as Record<string, unknown>).audio_source;
    if (typeof audioSource === "string") {
      const match = audioSource.match(/\{\{(.+?)\}\}/);
      if (match) return match[1];
    }
    return "source.output";
  }, [nodeData]);

  const getAudioKey = useCallback(
    (): string => (isVoiceAgentNode ? "audio_data" : getSTTAudioKey()),
    [isVoiceAgentNode, getSTTAudioKey]
  );

  const onAudio = useCallback(
    (base64: string, format: string) => {
      setFormData((prev) => ({ ...prev, [getAudioKey()]: buildAudioPayload(base64, format) }));
    },
    [getAudioKey, setFormData]
  );

  const { isRecording, audioFileName, fileInputRef, handleAudioFileUpload, startRecording, stopRecording } =
    useAudioCapture({ convertToWav: isVoiceAgentNode, onAudio, onError: setError });

  return {
    isSTTNode,
    isTTSNode,
    isVoiceAgentNode,
    isAudioInputNode,
    isRecording,
    audioFileName,
    fileInputRef,
    getSTTAudioKey,
    getAudioKey,
    handleAudioFileUpload,
    startRecording,
    stopRecording,
  };
}

// Find a base64 audio payload in a node/workflow result, handling all shapes:
//  - a bare audio dict (TTS node output IS the audio)
//  - nested under `audio` (Voice Agent output: { message, audio: {...} })
//  - wrapped under `output` (full test response: { status, output: {...} })
function findAudioPayload(value: unknown): { data: string; format: string } | null {
  if (!value || typeof value !== "object") return null;
  const obj = value as Record<string, unknown>;
  if (obj.type === "audio" && typeof obj.data === "string" && obj.encoding === "base64") {
    return { data: obj.data, format: (obj.format as string) || "mp3" };
  }
  return findAudioPayload(obj.audio) || findAudioPayload(obj.output);
}

export function getAudioUrl(outputData: unknown): string | null {
  const payload = findAudioPayload(outputData);
  return payload ? `data:audio/${payload.format};base64,${payload.data}` : null;
}

// Replace base64 audio blobs with a short placeholder so result JSON stays
// readable (the audio is surfaced via a player instead).
export function stripAudioDataForDisplay(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripAudioDataForDisplay);
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [key, v] of Object.entries(obj)) {
      if (key === "data" && obj.type === "audio" && typeof v === "string") {
        out[key] = `<${v.length} chars base64 audio>`;
      } else {
        out[key] = stripAudioDataForDisplay(v);
      }
    }
    return out;
  }
  return value;
}
