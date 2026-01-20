import axios from "axios";
import {
  ChatMessage,
  StartConversationResponse,
  Attachment,
  AgentThinkingConfig,
  AgentWelcomeData,
} from "../types";
import {
  createWebSocket,
  createWebSocketDiagnostic,
} from "../utils/websocket";

export class ChatService {
  private baseUrl: string;
  private apiKey: string;
  private metadata: Record<string, any> | undefined;
  private conversationId: string | null = null;
  private conversationCreateTime: number | null = null; // Track conversation start time
  private guestToken: string | null = null; // Guest token for authorization
  private isFinalized: boolean = false;
  private webSocket: WebSocket | null = null;
  private messageHandler: ((message: ChatMessage) => void) | null = null;
  private takeoverHandler: (() => void) | null = null;
  private finalizedHandler: (() => void) | null = null;
  private connectionStateHandler:
    | ((state: "connecting" | "connected" | "disconnected") => void)
    | null = null;
  private welcomeDataHandler: ((data: AgentWelcomeData) => void) | null = null;
  private storageKeyBase = "genassist_conversation";
  private possibleQueries: string[] = [];
  private welcomeData: AgentWelcomeData = {};
  private thinkingConfig: AgentThinkingConfig = { phrases: [], delayMs: 1000 };
  private welcomeObjectUrl: string | null = null; // to revoke on reset
  private tenant: string | undefined;
  private agentId: string | undefined;

  constructor(
    baseUrl: string,
    apiKey: string,
    metadata?: Record<string, any>,
    tenant?: string
  ) {
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
    this.apiKey = apiKey;
    this.metadata = metadata;
    this.tenant = tenant;
    // Try to load a saved conversation for this apiKey from localStorage
    this.loadSavedConversation();
  }

  private getStorageKey(): string {
    // Pointer to current conversation metadata for this apiKey
    return `${this.storageKeyBase}:${this.apiKey}`;
  }

  /**
   * Get headers for API requests, including authorization if guest token is available
   */
  private getHeaders(contentType: string = "application/json"): Record<string, string> {
    const headers: Record<string, string> = {
      "x-api-key": this.apiKey,
      "Content-Type": contentType,
    };

    // Add tenant header if provided
    if (this.tenant) {
      headers["x-tenant-id"] = this.tenant;
    }

    // Add authorization header if guest token is available
    if (this.guestToken) {
      headers["Authorization"] = `Bearer ${this.guestToken}`;
    }

    return headers;
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

  setConnectionStateHandler(
    handler: (state: "connecting" | "connected" | "disconnected") => void
  ) {
    this.connectionStateHandler = handler;
  }

  setWelcomeDataHandler(handler: ((data: AgentWelcomeData) => void) | null) {
    this.welcomeDataHandler = handler;
  }

  getPossibleQueries(): string[] {
    return this.possibleQueries;
  }

  getWelcomeData(): AgentWelcomeData {
    return this.welcomeData;
  }

  getThinkingConfig(): AgentThinkingConfig {
    return this.thinkingConfig;
  }

  /**
   * Load a saved conversation ID from localStorage
   */
  private loadSavedConversation(): void {
    try {
      let savedConversation = localStorage.getItem(this.getStorageKey());
      // Backward-compat: check old unscoped key if scoped one missing
      if (!savedConversation) {
        savedConversation = localStorage.getItem(this.storageKeyBase);
      }
      if (savedConversation) {
        const {
          conversationId,
          createTime,
          isFinalized,
          possibleQueries,
          welcomeData,
          thinkingConfig,
          agentId,
          guestToken,
        } = JSON.parse(savedConversation);
        this.conversationId = conversationId;
        this.conversationCreateTime = createTime;
        this.isFinalized = isFinalized || false;
        this.guestToken = guestToken || null;
        this.possibleQueries = Array.isArray(possibleQueries)
          ? possibleQueries
          : [];
        this.welcomeData = welcomeData || {};
        if (!this.welcomeData.possibleQueries) {
          this.welcomeData.possibleQueries = this.possibleQueries;
        }
        this.thinkingConfig = {
          phrases: (thinkingConfig && thinkingConfig.phrases) || [],
          delayMs:
            thinkingConfig && typeof thinkingConfig.delayMs === "number"
              ? thinkingConfig.delayMs
              : 1000,
        };
        this.agentId = agentId;
        if (!this.welcomeData.imageUrl && this.agentId) {
          this.fetchWelcomeImage(this.agentId);
        }
        if (this.welcomeDataHandler) {
          this.welcomeDataHandler(this.welcomeData);
        }
      }
    } catch (error) {
      // ignore
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
          possibleQueries: this.possibleQueries,
          welcomeData: {
            ...this.welcomeData,
            imageUrl:
              this.welcomeObjectUrl &&
              this.welcomeData.imageUrl &&
              this.welcomeData.imageUrl.startsWith("blob:")
                ? null
                : this.welcomeData.imageUrl || null,
          },
          thinkingConfig: this.thinkingConfig,
          agentId: this.agentId,
          guestToken: this.guestToken,
        };
        localStorage.setItem(this.getStorageKey(), JSON.stringify(conversationData));
      }
    } catch (error) {
      // ignore
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
    this.guestToken = null;
    this.isFinalized = false;

    // Clear possible queries
    this.possibleQueries = [];
    this.welcomeData = {};
    this.thinkingConfig = { phrases: [], delayMs: 1000 };
    if (this.welcomeObjectUrl) {
      try {
        URL.revokeObjectURL(this.welcomeObjectUrl);
      } catch {}
      this.welcomeObjectUrl = null;
    }
    this.agentId = undefined;

    // Remove from local storage
    try {
      localStorage.removeItem(this.getStorageKey());
    } catch (error) {
      // ignore
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
      const requestBody: any = {
        messages: [],
        recorded_at: new Date().toISOString(),
        data_source_id: "00000000-0000-0000-0000-000000000000",
      };

      if (this.metadata) {
        requestBody.metadata = this.metadata;
      }

      const response = await axios.post<StartConversationResponse>(
        `${this.baseUrl}/api/conversations/in-progress/start`,
        requestBody,
        {
          headers: this.getHeaders(),
        }
      );

      this.conversationId = response.data.conversation_id;
      // Store conversation create time (use from response if available, otherwise current time)
      this.conversationCreateTime = response.data.create_time
        ? response.data.create_time / 1000
        : Date.now() / 1000;
      // Store guest token if provided
      this.guestToken = response.data.guest_token || null;
      this.isFinalized = false;

      // Store possible queries if available
      if (
        response.data.agent_possible_queries &&
        response.data.agent_possible_queries.length > 0
      ) {
        this.possibleQueries = response.data.agent_possible_queries.filter(
          (query) => typeof query === "string" && query.trim().length > 0
        );
      }

      const anyData: any = response.data as any;
      const agentId: string | undefined = anyData.agent_id;
      this.agentId = agentId;
      const welcomeTitle: string | undefined = anyData.agent_welcome_title;
      const welcomeImageUrl: string | undefined =
        anyData.agent_welcome_image_url;
      const thinkingPhrases: string[] | undefined =
        anyData.agent_thinking_phrases;
      const thinkingDelaySec: number | undefined =
        anyData.agent_thinking_phrase_delay;

      this.welcomeData = {
        title: welcomeTitle || null,
        message: null,
        imageUrl: welcomeImageUrl || null,
        possibleQueries: this.possibleQueries,
      };

      if (Array.isArray(thinkingPhrases) && thinkingPhrases.length > 0) {
        this.thinkingConfig.phrases = thinkingPhrases;
      }
      if (typeof thinkingDelaySec === "number" && thinkingDelaySec >= 0) {
        this.thinkingConfig.delayMs = Math.max(
          250,
          Math.round(thinkingDelaySec * 1000)
        );
      }

      if (!this.welcomeData.imageUrl && agentId) {
        await this.fetchWelcomeImage(agentId);
      }

      // Process agent welcome message if available
      if (response.data.agent_welcome_message && this.messageHandler) {
        const now = Date.now() / 1000;
        const welcomeMessage: ChatMessage = {
          create_time: now,
          start_time: now - this.conversationCreateTime, // Relative to conversation start
          end_time: now - this.conversationCreateTime + 0.01, // Relative to conversation start
          speaker: "agent",
          text: response.data.agent_welcome_message,
        };
        this.welcomeData.message = response.data.agent_welcome_message;
        this.messageHandler(welcomeMessage);
      }

      if (this.welcomeDataHandler) {
        this.welcomeDataHandler(this.welcomeData);
      }

      this.saveConversation();
      this.connectWebSocket();
      return response.data.conversation_id;
    } catch (error) {
      throw error;
    }
  }

  async sendMessage(
    message: string,
    attachments?: Attachment[],
    extraMetadata?: Record<string, any>
  ): Promise<void> {
    if (!this.conversationId || !this.conversationCreateTime) {
      throw new Error("Conversation not started");
    }

    const now = Date.now() / 1000;
    const chatMessage: ChatMessage = {
      create_time: now,
      start_time: now - this.conversationCreateTime, // Relative to conversation start
      end_time: now - this.conversationCreateTime + 0.01, // Relative to conversation start
      speaker: "customer",
      text: message,
      attachments: attachments,
    };

    if (this.messageHandler) {
      this.messageHandler(chatMessage);
    }

    try {
      const requestBody: any = {
        messages: [chatMessage],
        recorded_at: new Date().toISOString(),
      };

      // Include metadata
      const mergedMetadata = {
        ...(this.metadata || {}),
        ...(extraMetadata || {}),
      };
      if (Object.keys(mergedMetadata).length > 0) {
        requestBody.metadata = mergedMetadata;
      }

      await axios.patch(
        `${this.baseUrl}/api/conversations/in-progress/update/${this.conversationId}`,
        requestBody,
        {
          headers: this.getHeaders(),
        }
      );
    } catch (error: any) {
      // Check if this is the agent inactive error
      if (
        error.response &&
        error.response.data &&
        error.response.data.error_key === "AGENT_INACTIVE"
      ) {
        // Create a custom message for the agent inactive error
        if (this.messageHandler) {
          const errorMessage: ChatMessage = {
            create_time: now,
            start_time: now - this.conversationCreateTime,
            end_time: now - this.conversationCreateTime + 0.01,
            speaker: "special",
            text: "The agent is currently offline, please check back later. Thank you!",
          };
          this.messageHandler(errorMessage);
        }
        // Don't throw the error since we handled it with a message
        return;
      }

      throw error;
    }
  }

  async uploadFile(chatId: string, file: File): Promise<{ fileUrl: string }> {
    if (!this.conversationId) {
      throw new Error("Conversation not started");
    }

    const formData = new FormData();
    formData.append("chat_id", chatId);
    formData.append("file", file);

    try {
      const response = await axios.post<{ fileUrl: string }>(
        `${this.baseUrl}/api/genagent/knowledge/upload-chat-file`,
        formData,
        {
          headers: this.getHeaders("multipart/form-data"),
        }
      );
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  connectWebSocket(): void {
    if (this.webSocket) {
      this.webSocket.close();
    }

    if (!this.conversationId) {
      throw new Error("Conversation ID is required for WebSocket connection");
    }

    if (this.connectionStateHandler) this.connectionStateHandler("connecting");
    let wsUrl = `${this.baseUrl.replace("http", "ws")}/api/conversations/ws/${
      this.conversationId
    }?api_key=${
      this.apiKey
    }&lang=en&topics=message&topics=takeover&topics=finalize`;
    
    // Add tenant as query parameter if provided
    if (this.tenant) {
      wsUrl += `&x-tenant-id=${encodeURIComponent(this.tenant)}`;
    }
    
    // Use native browser WebSocket factory
    this.webSocket = createWebSocket(wsUrl);


    this.webSocket.onopen = () => {
      if (this.connectionStateHandler) this.connectionStateHandler("connected");
    };

    this.webSocket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === "message" && this.messageHandler) {
          if (Array.isArray(data.payload)) {
            const messages = data.payload as ChatMessage[];
            // Adjust timestamps to be relative to conversation start
            // Also normalize message_id field (backend might send 'id' instead of 'message_id')
            const adjustedMessages = messages
              .map((msg) => {
                const adjusted = this.adjustMessageTimestamps(msg);
                // Normalize: if backend sends 'id', use it as 'message_id'
                if (!adjusted.message_id && (msg as any).id) {
                  adjusted.message_id = (msg as any).id;
                }
                return adjusted;
              })
              .filter((msg) => msg.speaker !== "customer");
            adjustedMessages.forEach(this.messageHandler);
          } else {
            const adjustedMessage = this.adjustMessageTimestamps(
              data.payload as ChatMessage
            );
            // Normalize: if backend sends 'id', use it as 'message_id'
            if (!adjustedMessage.message_id && (data.payload as any).id) {
              adjustedMessage.message_id = (data.payload as any).id;
            }
            if (adjustedMessage.speaker !== "customer") {
              this.messageHandler(adjustedMessage);
            }
          }
        } else if (data.type === "takeover") {
          // Handle takeover event
          // Create special message for the takeover indicator
          if (this.messageHandler) {
            const now = Date.now() / 1000;
            const takeoverMessage: ChatMessage = {
              create_time: now,
              start_time: this.conversationCreateTime
                ? now - this.conversationCreateTime
                : 0,
              end_time: this.conversationCreateTime
                ? now - this.conversationCreateTime + 0.01
                : 0.01,
              speaker: "special",
              text: "Supervisor took over",
            };
            this.messageHandler(takeoverMessage);
          }

          // Call the takeover handler if provided
          if (this.takeoverHandler) {
            this.takeoverHandler();
          }
        } else if (data.type === "finalize") {
          // Handle finalized event
          // Create special message for the finalized indicator
          if (this.messageHandler) {
            const now = Date.now() / 1000;
            const finalizedMessage: ChatMessage = {
              create_time: now,
              start_time: this.conversationCreateTime
                ? now - this.conversationCreateTime
                : 0,
              end_time: this.conversationCreateTime
                ? now - this.conversationCreateTime + 0.01
                : 0.01,
              speaker: "special",
              text: "Conversation Finalized",
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
        // ignore
      }
    };

    this.webSocket.onerror = (error: Event) => {
      if (this.connectionStateHandler)
        this.connectionStateHandler("disconnected");
      
      // Log diagnostic
      const diagnostic = createWebSocketDiagnostic(error, wsUrl);
      console.error(`[GenAssist Chat] ${diagnostic}`);
    };

    this.webSocket.onclose = (event: CloseEvent) => {
      if (this.connectionStateHandler)
        this.connectionStateHandler("disconnected");
      
      // Log diagnostic
      if (!event.wasClean) {
        const diagnostic = createWebSocketDiagnostic(event, wsUrl);
        console.warn(`[GenAssist Chat] ${diagnostic}`);
      }
    };
  }

  disconnect(): void {
    if (this.webSocket) {
      this.webSocket.close();
      this.webSocket = null;
    }
  }

  private async fetchWelcomeImage(agentId: string): Promise<void> {
    try {
      const imageResponse = await axios.get(
        `${this.baseUrl}/api/genagent/agents/configs/${agentId}/welcome-image`,
        {
          headers: this.getHeaders(),
          responseType: "blob",
        }
      );
      const blobUrl = URL.createObjectURL(imageResponse.data);
      this.welcomeObjectUrl = blobUrl;
      this.welcomeData.imageUrl = blobUrl;
      if (this.welcomeDataHandler) {
        this.welcomeDataHandler(this.welcomeData);
      }
    } catch (err) {
      // ignore
    }
  }

  // Add feedback to a specific agent message in the conversation
  async addFeedback(
    messageId: string,
    feedback: "good" | "bad",
    feedback_message?: string
  ): Promise<void> {
    if (!messageId) {
      throw new Error("Message ID is required for feedback");
    }

    try {
      // Use message ID in the URL path, not conversation ID
      const url = `${this.baseUrl}/api/conversations/message/add-feedback/${messageId}`;
      // Body should only contain feedback and feedback_message (no message_id)
      const payload: {
        feedback: "good" | "bad";
        feedback_message?: string;
      } = {
        feedback,
      };
      
      if (feedback_message) {
        payload.feedback_message = feedback_message;
      }
      
      await axios.patch(url, payload, {
        headers: this.getHeaders(),
      });
      
    } catch (error: any) {
      console.error('Feedback API call failed:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      });
      throw error;
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
      end_time: message.end_time - this.conversationCreateTime,
    };
  }
}
