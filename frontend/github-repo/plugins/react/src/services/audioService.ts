import axios from 'axios';

interface AudioServiceConfig {
  baseUrl: string;
  apiKey: string;
}

export class AudioService {
  private baseUrl: string;
  private apiKey: string;
  private ws: WebSocket | null = null;
  private audioChunks: Blob[] = [];
  private resolvePromise: ((value: Blob) => void) | null = null;
  private rejectPromise: ((reason?: any) => void) | null = null;

  constructor(config: AudioServiceConfig) {
    this.baseUrl = config.baseUrl;
    this.apiKey = config.apiKey;
  }

  async textToSpeech(text: string, voice: string = 'alloy'): Promise<Blob> {
    return new Promise((resolve, reject) => {
      this.resolvePromise = resolve;
      this.rejectPromise = reject;
      this.audioChunks = [];

      // Create WebSocket connection
      const wsUrl = `${this.baseUrl.replace('http', 'ws')}/api/voice/audio/tts?api_key=${this.apiKey}`;
      this.ws = new WebSocket(wsUrl);

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