import axios from 'axios';
import { w3cwebsocket as WebSocket, IMessageEvent, ICloseEvent } from 'websocket';
import { ChatMessage, StartConversationResponse } from '../types';

export class ChatService {
  private baseUrl: string;
  private apiKey: string;
  private conversationId: string | null = null;
  private conversationCreateTime: number | null = null; // Track conversation start time
  private isFinalized: boolean = false;
  private webSocket: WebSocket | null = null;
  private messageHandler: ((message: ChatMessage) => void) | null = null;
  private takeoverHandler: (() => void) | null = null;
  private finalizedHandler: (() => void) | null = null;
  private connectionStateHandler: ((state: 'connecting' | 'connected' | 'disconnected') => void) | null = null;
  private storageKey = 'genassist_conversation';
  private possibleQueries: string[] = [];

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    this.apiKey = apiKey;
    // Try to load a saved conversation ID from localStorage
    this.loadSavedConversation();
  }

  setMessageHandler(handler: (message: ChatMessage) => void) {
    this.messageHandler = handler;
  }

  setTakeoverHandler(handler: () => void) {
    this.takeoverHandler = handler;
  }

  setFinalizedHandler(handler: () => void) {
    this.finalizedHandler = handler;
  }

  setConnectionStateHandler(handler: (state: 'connecting' | 'connected' | 'disconnected') => void) {
    this.connectionStateHandler = handler;
  }

  getPossibleQueries(): string[] {
    return this.possibleQueries;
  }

  /**
   * Load a saved conversation ID from localStorage
   */
  private loadSavedConversation(): void {
    try {
      const savedConversation = localStorage.getItem(this.storageKey);
      if (savedConversation) {
        const { conversationId, createTime, isFinalized } = JSON.parse(savedConversation);
        this.conversationId = conversationId;
        this.conversationCreateTime = createTime;
        this.isFinalized = isFinalized || false;
        console.log('Loaded saved conversation:', this.conversationId, 'Finalized:', this.isFinalized);
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
      if (this.conversationId && this.conversationCreateTime) {
        const conversationData = {
          conversationId: this.conversationId,
          createTime: this.conversationCreateTime,
          isFinalized: this.isFinalized,
        };
        localStorage.setItem(this.storageKey, JSON.stringify(conversationData));
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
    this.conversationCreateTime = null;
    this.isFinalized = false;

    // Clear possible queries
    this.possibleQueries = [];
    
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

  isConversationFinalized(): boolean {
    return this.isFinalized;
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
      // Store conversation create time (use from response if available, otherwise current time)
      this.conversationCreateTime = response.data.create_time ? response.data.create_time / 1000 : Date.now() / 1000;
      this.isFinalized = false;
      this.saveConversation();
      this.connectWebSocket();

      // Store possible queries if available
      if (response.data.agent_possible_queries && response.data.agent_possible_queries.length > 0) {
        this.possibleQueries = response.data.agent_possible_queries;
      }
      
      // Process agent welcome message if available
      if (response.data.agent_welcome_message && this.messageHandler) {
        const now = Date.now() / 1000;
        const welcomeMessage: ChatMessage = {
          create_time: now,
          start_time: now - this.conversationCreateTime, // Relative to conversation start
          end_time: (now - this.conversationCreateTime) + 0.01, // Relative to conversation start
          speaker: 'agent',
          text: response.data.agent_welcome_message
        };
        this.messageHandler(welcomeMessage);
      }
      return response.data.conversation_id;
    } catch (error) {
      console.error('Error starting conversation:', error);
      throw error;
    }
  }

  async sendMessage(message: string): Promise<void> {
    if (!this.conversationId || !this.conversationCreateTime) {
      throw new Error('Conversation not started');
    }

    const now = Date.now() / 1000;
    const chatMessage: ChatMessage = {
      create_time: now,
      start_time: now - this.conversationCreateTime, // Relative to conversation start
      end_time: (now - this.conversationCreateTime) + 0.01, // Relative to conversation start
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

  connectWebSocket(): void {
    if (this.webSocket) {
      this.webSocket.close();
    }
    
    if (!this.conversationId) {
      throw new Error('Conversation ID is required for WebSocket connection');
    }

    if (this.connectionStateHandler) this.connectionStateHandler('connecting');
    const wsUrl = `${this.baseUrl.replace('http', 'ws')}/api/conversations/ws/${this.conversationId}?api_key=${this.apiKey}&lang=en&topics=message&topics=takeover&topics=finalize`;
    this.webSocket = new WebSocket(wsUrl);

    this.webSocket.onopen = () => {
      console.log('WebSocket connected');
      if (this.connectionStateHandler) this.connectionStateHandler('connected');
    };

    this.webSocket.onmessage = (event: IMessageEvent) => {
      console.log('WebSocket message:', event.data);
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === 'message' && this.messageHandler) {
          if(Array.isArray(data.payload)) {
            const messages = data.payload as ChatMessage[]
            // Adjust timestamps to be relative to conversation start
            const adjustedMessages = messages.map(msg => this.adjustMessageTimestamps(msg));
            adjustedMessages.forEach(this.messageHandler);
          } else {
            const adjustedMessage = this.adjustMessageTimestamps(data.payload as ChatMessage);
            this.messageHandler(adjustedMessage);
          }
        } else if (data.type === 'takeover') {
          // Handle takeover event
          console.log('Takeover event received');
          
          // Create special message for the takeover indicator
          if (this.messageHandler) {
            const now = Date.now() / 1000;
            const takeoverMessage: ChatMessage = {
              create_time: now,
              start_time: this.conversationCreateTime ? now - this.conversationCreateTime : 0,
              end_time: this.conversationCreateTime ? (now - this.conversationCreateTime) + 0.01 : 0.01,
              speaker: 'special',
              text: 'Supervisor took over'
            };
            this.messageHandler(takeoverMessage);
          }
          
          // Call the takeover handler if provided
          if (this.takeoverHandler) {
            this.takeoverHandler();
          }
        } else if (data.type === 'finalize') {
          // Handle finalized event
          console.log('Finalized event received');
          
          // Create special message for the finalized indicator
          if (this.messageHandler) {
            const now = Date.now() / 1000;
            const finalizedMessage: ChatMessage = {
              create_time: now,
              start_time: this.conversationCreateTime ? now - this.conversationCreateTime : 0,
              end_time: this.conversationCreateTime ? (now - this.conversationCreateTime) + 0.01 : 0.01,
              speaker: 'special',
              text: 'Conversation Finalized'
            };
            this.messageHandler(finalizedMessage);
          }
          
          // Call the finalized handler if provided
          if (this.finalizedHandler) {
            this.finalizedHandler();
          }
          this.isFinalized = true;
          this.saveConversation();
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.webSocket.onerror = (error: Error) => {
      console.error('WebSocket error:', error);
      if (this.connectionStateHandler) this.connectionStateHandler('disconnected');
    };

    this.webSocket.onclose = (event: ICloseEvent) => {
      console.log('WebSocket closed:', event.code, event.reason);
      if (this.connectionStateHandler) this.connectionStateHandler('disconnected');
    };
  }

  disconnect(): void {
    if (this.webSocket) {
      this.webSocket.close();
      this.webSocket = null;
    }
  }

  // Helper method to adjust message timestamps relative to conversation start
  private adjustMessageTimestamps(message: ChatMessage): ChatMessage {
    if (!this.conversationCreateTime) {
      return message;
    }

    return {
      ...message,
      start_time: message.start_time - this.conversationCreateTime,
      end_time: message.end_time - this.conversationCreateTime
    };
  }
} 