import { useCallback, useEffect, useRef, useState } from 'react';
import { createWebSocket } from '../utils/websocket';

const LIVE_INPUT_SAMPLE_RATE = 16000; // Gemini Live expects 16 kHz mono PCM in
const LIVE_OUTPUT_SAMPLE_RATE = 24000; // Gemini Live emits 24 kHz mono PCM out
const CAPTURE_BUFFER_SIZE = 4096;

export type LiveVoiceStatus =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'speaking'
  | 'error';

interface UseLiveVoiceOptions {
  // Backend base URL (http/https). Live voice is a stateful 1:1 audio stream
  // held by the backend, so the plugin connects there directly (the fan-out
  // websocket service is not involved).
  baseUrl: string;
  apiKey: string;
  guestToken?: string | null;
  tenant?: string;
  agentId?: string | null;
  conversationId?: string | null;
  language?: string;
  onError?: (error: Error) => void;
  onInputTranscript?: (text: string) => void;
  onOutputTranscript?: (text: string) => void;
  onTurnComplete?: (turn: { transcript: string; response: string }) => void;
}

interface UseLiveVoiceReturn {
  isActive: boolean;
  status: LiveVoiceStatus;
  start: () => Promise<void>;
  stop: () => void;
}

/** Downsample a mono Float32 buffer to 16 kHz Int16 PCM (little-endian). */
function floatTo16kPcm(input: Float32Array, inputRate: number): ArrayBuffer {
  const ratio = inputRate / LIVE_INPUT_SAMPLE_RATE;
  const outLength = Math.floor(input.length / ratio);
  const out = new Int16Array(outLength);
  for (let i = 0; i < outLength; i++) {
    const sample = input[Math.floor(i * ratio)] || 0;
    const clamped = Math.max(-1, Math.min(1, sample));
    out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return out.buffer;
}

function buildLiveUrl(opts: UseLiveVoiceOptions, threadId: string): string {
  // Live voice is a stateful 1:1 audio stream held by the backend, so the plugin
  // connects directly to the backend (not the fan-out websocket service).
  const wsBase = opts.baseUrl.replace(/^http/, 'ws').replace(/\/$/, '');
  const auth = opts.guestToken
    ? `access_token=${encodeURIComponent(opts.guestToken)}`
    : `api_key=${encodeURIComponent(opts.apiKey)}`;
  const params = [auth, `thread_id=${encodeURIComponent(threadId)}`];
  if (opts.tenant) params.push(`x-tenant-id=${encodeURIComponent(opts.tenant)}`);
  if (opts.language) params.push(`lang=${encodeURIComponent(opts.language)}`);
  return `${wsBase}/api/voice/live/${opts.agentId}?${params.join('&')}`;
}

/**
 * Continuous, two-way voice conversation with a Voice Agent node.
 *
 * Streams 16 kHz mic PCM up a WebSocket to a persistent Gemini Live session and
 * plays the 24 kHz reply audio back as it arrives (no record/stop/send). Supports
 * barge-in: when the agent is interrupted, queued playback is flushed instantly.
 */
export function useLiveVoice(opts: UseLiveVoiceOptions): UseLiveVoiceReturn {
  const [isActive, setIsActive] = useState(false);
  const [status, setStatus] = useState<LiveVoiceStatus>('idle');

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playheadRef = useRef<number>(0);
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const speakingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mirror `isActive` into a ref so async callbacks (e.g. the speaking timer)
  // can read the latest value without being re-created.
  const isActiveRef = useRef(false);
  isActiveRef.current = isActive;

  // Keep the latest callbacks without re-creating start/stop.
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const flushPlayback = useCallback(() => {
    sourcesRef.current.forEach((src) => {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
    });
    sourcesRef.current = [];
    if (playbackCtxRef.current) {
      playheadRef.current = playbackCtxRef.current.currentTime;
    }
  }, []);

  const stop = useCallback(() => {
    if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current);
    flushPlayback();
    processorRef.current?.disconnect();
    processorRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    captureCtxRef.current?.close().catch(() => undefined);
    captureCtxRef.current = null;
    playbackCtxRef.current?.close().catch(() => undefined);
    playbackCtxRef.current = null;
    if (wsRef.current) {
      wsRef.current.onclose = null;
      try {
        wsRef.current.close();
      } catch {
        /* noop */
      }
      wsRef.current = null;
    }
    setIsActive(false);
    setStatus('idle');
  }, [flushPlayback]);

  const playPcmChunk = useCallback((pcm: ArrayBuffer) => {
    const ctx = playbackCtxRef.current;
    if (!ctx) return;
    const ints = new Int16Array(pcm);
    if (ints.length === 0) return;
    const floats = new Float32Array(ints.length);
    for (let i = 0; i < ints.length; i++) floats[i] = ints[i] / 0x8000;

    const buffer = ctx.createBuffer(1, floats.length, LIVE_OUTPUT_SAMPLE_RATE);
    buffer.copyToChannel(floats, 0);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const startAt = Math.max(ctx.currentTime, playheadRef.current);
    source.start(startAt);
    playheadRef.current = startAt + buffer.duration;
    sourcesRef.current.push(source);
    source.onended = () => {
      sourcesRef.current = sourcesRef.current.filter((s) => s !== source);
    };

    // Reflect "speaking" until the scheduled audio drains.
    setStatus('speaking');
    if (speakingTimerRef.current) clearTimeout(speakingTimerRef.current);
    const remainingMs = (playheadRef.current - ctx.currentTime) * 1000 + 150;
    speakingTimerRef.current = setTimeout(() => {
      if (isActiveRef.current) setStatus('listening');
    }, remainingMs);
  }, []);

  const handleEvent = useCallback((data: Record<string, unknown>) => {
    const cb = optsRef.current;
    switch (data.type) {
      case 'ready':
        setStatus('listening');
        break;
      case 'input_transcript':
        if (typeof data.text === 'string') cb.onInputTranscript?.(data.text);
        break;
      case 'output_transcript':
        if (typeof data.text === 'string') cb.onOutputTranscript?.(data.text);
        break;
      case 'interrupted':
        flushPlayback();
        setStatus('listening');
        break;
      case 'turn_complete':
        cb.onTurnComplete?.({
          transcript: String(data.transcript ?? ''),
          response: String(data.response ?? ''),
        });
        break;
      case 'error':
        cb.onError?.(new Error(String(data.message ?? 'Live voice error')));
        setStatus('error');
        break;
      default:
        break;
    }
  }, [flushPlayback]);

  const start = useCallback(async () => {
    const cb = optsRef.current;
    if (!cb.agentId) {
      cb.onError?.(new Error('Live voice unavailable: agent is still loading'));
      return;
    }
    if (wsRef.current) return; // already active

    setStatus('connecting');
    // Persistence (transcript/dashboard) keys off an existing conversation UUID.
    // Without one the call still works, but the backend skips saving the turns.
    if (!cb.conversationId) {
      console.warn(
        '[useLiveVoice] No conversationId yet — the live call will run but its ' +
          'transcripts will not be persisted.',
      );
    }
    const threadId =
      cb.conversationId ||
      (typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `live-${Date.now()}`);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const captureCtx = new AudioCtx();
      captureCtxRef.current = captureCtx;
      playbackCtxRef.current = new AudioCtx();
      playheadRef.current = playbackCtxRef.current.currentTime;

      const ws = createWebSocket(buildLiveUrl(cb, threadId));
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        const source = captureCtx.createMediaStreamSource(stream);
        // TODO: migrate to AudioWorklet — ScriptProcessorNode is deprecated and
        // runs the downsample on the main thread (can jank on slow devices).
        const processor = captureCtx.createScriptProcessor(CAPTURE_BUFFER_SIZE, 1, 1);
        processorRef.current = processor;
        processor.onaudioprocess = (e) => {
          if (ws.readyState !== ws.OPEN) return;
          const pcm = floatTo16kPcm(e.inputBuffer.getChannelData(0), captureCtx.sampleRate);
          ws.send(pcm);
        };
        source.connect(processor);
        processor.connect(captureCtx.destination); // required to drive onaudioprocess
        setIsActive(true);
        setStatus('listening');
      };

      ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          playPcmChunk(event.data);
        } else if (typeof event.data === 'string') {
          try {
            handleEvent(JSON.parse(event.data));
          } catch {
            /* ignore malformed event */
          }
        }
      };

      ws.onerror = () => {
        cb.onError?.(new Error('Live voice connection error'));
      };

      ws.onclose = () => {
        stop();
      };
    } catch (err) {
      cb.onError?.(err instanceof Error ? err : new Error(String(err)));
      stop();
    }
  }, [handleEvent, playPcmChunk, stop]);

  // Tear down on unmount.
  useEffect(() => () => stop(), [stop]);

  return { isActive, status, start, stop };
}
