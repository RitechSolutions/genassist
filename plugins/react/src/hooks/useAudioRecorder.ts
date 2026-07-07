import { useCallback, useRef, useState } from 'react';

interface UseAudioRecorderReturn {
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  cancelRecording: () => void;
}

const WAV_SAMPLE_RATE = 16000;

function getMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return '';
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm';
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4';
  return '';
}

function formatFromMime(mimeType: string): string {
  if (mimeType.includes('webm')) return 'webm';
  if (mimeType.includes('mp4')) return 'mp4';
  return 'webm';
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeString = (offset: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
  };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeString(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: 'audio/wav' });
}

/**
 * Convert a compressed recording (webm/mp4) to 16 kHz mono WAV so the backend
 * can consume it without an audio decoder (required for native voice agents).
 */
async function blobToWav16k(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const decodeCtx = new AudioCtx();
  try {
    const decoded = await decodeCtx.decodeAudioData(arrayBuffer);
    const length = Math.max(1, Math.ceil(decoded.duration * WAV_SAMPLE_RATE));
    const offline = new OfflineAudioContext(1, length, WAV_SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = decoded;
    source.connect(offline.destination);
    source.start();
    const rendered = await offline.startRendering();
    return encodeWav(rendered.getChannelData(0), WAV_SAMPLE_RATE);
  } finally {
    decodeCtx.close();
  }
}

export function useAudioRecorder(
  onAudioReady: (blob: Blob, format: string) => void,
  onError?: (error: Error) => void,
): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const cancelledRef = useRef(false);

  const startRecording = useCallback(async () => {
    try {
      const mimeType = getMimeType();
      if (!mimeType) {
        throw new Error('Audio recording is not supported in this browser');
      }

      cancelledRef.current = false;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const wasCancelled = cancelledRef.current;
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const format = formatFromMime(mimeType);
        chunksRef.current = [];

        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        if (!wasCancelled) {
          blobToWav16k(blob)
            .then((wavBlob) => onAudioReady(wavBlob, 'wav'))
            .catch(() => {
              // Decoding failed — fall back to the original recording
              onAudioReady(blob, format);
            });
        }
      };

      recorder.start();
      setIsRecording(true);
    } catch (err) {
      onError?.(err instanceof Error ? err : new Error(String(err)));
    }
  }, [onAudioReady, onError]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const cancelRecording = useCallback(() => {
    cancelledRef.current = true;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  return { isRecording, startRecording, stopRecording, cancelRecording };
}
