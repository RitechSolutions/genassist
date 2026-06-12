import { useState, useRef, useCallback } from "react";
import { blobToWav16k } from "../utils/audioWav";

interface UseAudioCaptureOptions {
  // Transcode recordings/uploads to 16 kHz WAV. Required for native voice
  // agents (the Live API can't decode webm/mp3).
  convertToWav: boolean;
  // Called with the captured audio as base64 (no data: prefix) and its format.
  onAudio: (base64: string, format: string) => void;
  onError?: (message: string) => void;
}

/**
 * Shared microphone-record / file-upload capture for node and workflow test
 * dialogs. Encapsulates MediaRecorder lifecycle, optional WAV transcoding, and
 * base64 encoding so callers only deal with the resulting audio.
 */
export function useAudioCapture({ convertToWav, onAudio, onError }: UseAudioCaptureOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const commit = useCallback(
    async (blob: Blob, fallbackFormat: string, fileName: string) => {
      let finalBlob = blob;
      let format = fallbackFormat;
      if (convertToWav) {
        try {
          finalBlob = await blobToWav16k(blob);
          format = "wav";
        } catch {
          onError?.("Could not convert audio to WAV. Try uploading a WAV file.");
          return;
        }
      }
      setAudioFileName(fileName);
      const reader = new FileReader();
      reader.onload = () => onAudio((reader.result as string).split(",")[1], format);
      reader.readAsDataURL(finalBlob);
    },
    [convertToWav, onAudio, onError]
  );

  const handleAudioFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const ext = file.name.split(".").pop()?.toLowerCase() || "mp3";
      void commit(file, ext, file.name);
    },
    [commit]
  );

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
        void commit(blob, "webm", convertToWav ? "recording.wav" : "recording.webm");
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch {
      onError?.("Microphone access denied");
    }
  }, [commit, convertToWav, onError]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  return {
    isRecording,
    audioFileName,
    fileInputRef,
    handleAudioFileUpload,
    startRecording,
    stopRecording,
  };
}
