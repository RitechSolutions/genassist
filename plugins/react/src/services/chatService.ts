import axios from 'axios';
import { w3cwebsocket as WebSocket, IMessageEvent, ICloseEvent } from 'websocket';
import { ChatMessage, StartConversationResponse } from '../types';

export class ChatService {
  private baseUrl: string;
  private apiKey: string;
  private conversationId: string | null = null;
  private webSocket: WebSocket | null = null;
  private messageHandler: ((message: ChatMessage) => void) | null = null;
  private storageKey = 'genassist_conversation_id';

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    this.apiKey = apiKey;
    // Try to load a saved conversation ID from localStorage
    this.loadSavedConversation();
  }

  setMessageHandler(handler: (message: ChatMessage) => void) {
    this.messageHandler = handler;
  }

  /**
   * Load a saved conversation ID from localStorage
   */
  private loadSavedConversation(): void {
    try {
      const savedConversationId = localStorage.getItem(this.storageKey);
      if (savedConversationId) {
        this.conversationId = savedConversationId;
        console.log('Loaded saved conversation:', this.conversationId);
      }
    } catch (error) {
      console.error('Error loading saved conversation:', error);
    }
  }

  /**
   * Save the current conversation ID to localStorage
   */
  private saveConversation(): void {
    try {
      if (this.conversationId) {
        localStorage.setItem(this.storageKey, this.conversationId);
        console.log('Saved conversation:', this.conversationId);
      }
    } catch (error) {
      console.error('Error saving conversation:', error);
    }
  }

  /**
   * Reset the current conversation by clearing the ID and websocket
   */
  resetConversation(): void {
    // Close the current websocket connection if it exists
    if (this.webSocket) {
      this.webSocket.close();
      this.webSocket = null;
    }
    
    // Clear the conversation ID
    this.conversationId = null;
    
    // Remove from local storage
    try {
      localStorage.removeItem(this.storageKey);
    } catch (error) {
      console.error('Error removing conversation from storage:', error);
    }
  }

  /**
   * Check if there's a current conversation
   */
  hasActiveConversation(): boolean {
    return !!this.conversationId;
  }

  /**
   * Get the current conversation ID
   */
  getConversationId(): string | null {
    return this.conversationId;
  }

  /**
   * Initialize conversation - either connect to existing one or start a new one
   */
  async initializeConversation(): Promise<string> {
    // If we already have a conversation ID, connect to that
    if (this.conversationId) {
      this.connectWebSocket();
      return this.conversationId;
    }
    
    // Otherwise start a new conversation
    return this.startConversation();
  }

  async startConversation(): Promise<string> {
    try {
      const response = await axios.post<StartConversationResponse>(
        `${this.baseUrl}/api/conversations/in-progress/start`,
        {
          messages: [],
          recorded_at: new Date().toISOString(),
          operator_id: "00000196-02d3-603c-994a-b616f314b0ba",
          data_source_id: "00000196-02d3-6026-a041-ec8564d4a316"
        },
        {
          headers: {
            'x-api-key': this.apiKey,
            'Content-Type': 'application/json'
          }
        }
      );

      this.conversationId = response.data.conversation_id;
      this.saveConversation();
      this.connectWebSocket();
      return response.data.conversation_id;
    } catch (error) {
      console.error('Error starting conversation:', error);
      throw error;
    }
  }

  async sendMessage(message: string): Promise<void> {
    if (!this.conversationId) {
      throw new Error('Conversation not started');
    }

    const now = Date.now();
    const chatMessage: ChatMessage = {
      create_time: now,
      start_time: now / 1000,
      end_time: now / 1000 + 0.01, // Just a small difference
      speaker: 'customer',
      text: message
    };

    try {
      await axios.patch(
        `${this.baseUrl}/api/conversations/in-progress/update/${this.conversationId}`,
        {
          messages: [chatMessage]
        },
        {
          headers: {
            'x-api-key': this.apiKey,
            'Content-Type': 'application/json'
          }
        }
      );
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  private connectWebSocket(): void {
    if (!this.conversationId) {
      throw new Error('Conversation ID is required for WebSocket connection');
    }

    const wsUrl = `${this.baseUrl.replace('http', 'ws')}/api/conversations/ws/${this.conversationId}?api_key=${this.apiKey}&lang=en&topics=message`;
    this.webSocket = new WebSocket(wsUrl);

    this.webSocket.onopen = () => {
      console.log('WebSocket connected');
    };

    this.webSocket.onmessage = (event: IMessageEvent) => {
      console.log('WebSocket message:', event.data);
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === 'message' && this.messageHandler) {
          if(Array.isArray(data.payload)) {
            const messages = data.payload as ChatMessage[]
            messages.forEach(this.messageHandler);
          } else {
            this.messageHandler(data.payload as ChatMessage);
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.webSocket.onerror = (error: Error) => {
      console.error('WebSocket error:', error);
    };

    this.webSocket.onclose = (event: ICloseEvent) => {
      console.log('WebSocket closed:', event.code, event.reason);
    };
  }

  disconnect(): void {
    if (this.webSocket) {
      this.webSocket.close();
      this.webSocket = null;
    }
  }
} 