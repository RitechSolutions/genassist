import { useState, useRef, useCallback } from "react";
import { NodeData } from "../types/nodes";

interface UseAudioTestOptions {
  nodeType: string;
  nodeData: NodeData;
  setFormData: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setError: (error: string | null) => void;
}

export function useAudioTest({ nodeType, nodeData, setFormData, setError }: UseAudioTestOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isSTTNode = nodeType === "sttNode";
  const isTTSNode = nodeType === "ttsNode";

  const getSTTAudioKey = useCallback((): string => {
    const audioSource = (nodeData as unknown as Record<string, unknown>).audio_source;
    if (typeof audioSource === "string") {
      const match = audioSource.match(/\{\{(.+?)\}\}/);
      if (match) return match[1];
    }
    return "source.output";
  }, [nodeData]);

  const buildAudioPayload = useCallback((base64: string, format: string): string => {
    return JSON.stringify({
      type: "audio",
      format,
      encoding: "base64",
      data: base64,
    });
  }, []);

  const handleAudioFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAudioFileName(file.name);
    const ext = file.name.split(".").pop()?.toLowerCase() || "mp3";
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(",")[1];
      const key = getSTTAudioKey();
      setFormData((prev) => ({ ...prev, [key]: buildAudioPayload(base64, ext) }));
    };
    reader.readAsDataURL(file);
  }, [getSTTAudioKey, setFormData, buildAudioPayload]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        setAudioFileName("recording.webm");
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(",")[1];
          const key = getSTTAudioKey();
          setFormData((prev) => ({ ...prev, [key]: buildAudioPayload(base64, "webm") }));
        };
        reader.readAsDataURL(blob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      setError("Microphone access denied");
    }
  }, [getSTTAudioKey, setFormData, setError]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  return {
    isSTTNode,
    isTTSNode,
    isRecording,
    audioFileName,
    fileInputRef,
    getSTTAudioKey,
    handleAudioFileUpload,
    startRecording,
    stopRecording,
  };
}

export function getAudioUrl(outputData: unknown): string | null {
  if (!outputData || typeof outputData !== "object") return null;
  const obj = outputData as Record<string, unknown>;
  const out = obj.output;
  if (out && typeof out === "object") {
    const audioOut = out as Record<string, unknown>;
    if (audioOut.type === "audio" && audioOut.data && audioOut.encoding === "base64") {
      const fmt = (audioOut.format as string) || "mp3";
      return `data:audio/${fmt};base64,${audioOut.data}`;
    }
  }
  return null;
}
