import { createWebSocket } from '../utils/websocket';

interface AudioServiceConfig {
  baseUrl: string;
  apiKey: string;
  guestToken?: string;
}

export class AudioService {
  private baseUrl: string;
  private apiKey: string;
  private guestToken: string | null = null;
  private ws: WebSocket | null = null;
  private audioChunks: Blob[] = [];
  private resolvePromise: ((value: Blob) => void) | null = null;
  private rejectPromise: ((reason?: any) => void) | null = null;

  constructor(config: AudioServiceConfig) {
    this.baseUrl = config.baseUrl;
    this.apiKey = config.apiKey;
    this.guestToken = config.guestToken || null;
  }

  /**
   * Set the guest token for WebSocket authentication
   */
  setGuestToken(token: string | null): void {
    this.guestToken = token;
  }

  async textToSpeech(text: string, voice: string = 'alloy'): Promise<Blob> {
    return new Promise((resolve, reject) => {
      this.resolvePromise = resolve;
      this.rejectPromise = reject;
      this.audioChunks = [];

      // Build WebSocket URL with proper authentication
      const wsBase = this.baseUrl.replace('http', 'ws');
      // Use guest_token if available, otherwise fall back to api_key
      const authParam = this.guestToken 
        ? `access_token=${encodeURIComponent(this.guestToken)}`
        : `api_key=${encodeURIComponent(this.apiKey)}`;
      const wsUrl = `${wsBase}/api/voice/audio/tts?${authParam}`;
      this.ws = createWebSocket(wsUrl);

      this.ws.onopen = () => {
        this.ws?.send(JSON.stringify({ text }));
      };

      this.ws.onmessage = (event) => {
        if (event.data instanceof Blob) {
          this.audioChunks.push(event.data);
        }
      };

      this.ws.onclose = () => {
        if (this.audioChunks.length > 0) {
          const audioBlob = new Blob(this.audioChunks, { type: 'audio/mp3' });
          this.resolvePromise?.(audioBlob);
        } else {
          this.rejectPromise?.(new Error('No audio data received'));
        }
        this.cleanup();
      };

      this.ws.onerror = (error) => {
        this.rejectPromise?.(error);
        this.cleanup();
      };
    });
  }

  private cleanup() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.resolvePromise = null;
    this.rejectPromise = null;
  }

  async playAudio(audioBlob: Blob): Promise<void> {
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    
    return new Promise((resolve, reject) => {
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        resolve();
      };
      
      audio.onerror = (error) => {
        URL.revokeObjectURL(audioUrl);
        reject(error);
      };
      
      audio.play().catch(reject);
    });
  }
} 